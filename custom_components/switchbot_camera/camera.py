"""Interfaces with the Switch Bot Cameras."""

from datetime import UTC, datetime, timedelta
import functools
from functools import partial
import json
import logging
from pathlib import Path
import re

import boto3
from botocore.auth import SigV4QueryAuth
from botocore.awsrequest import AWSRequest
from botocore.credentials import Credentials
from go2rtc_client import Go2RtcRestClient
from go2rtc_client.ws import (
    Go2RtcWsClient,
    ReceiveMessages,
    WebRTCAnswer,
    WebRTCCandidate,
    WebRTCOffer,
    WsError,
)
from webrtc_models import RTCIceCandidateInit

from homeassistant.components import ffmpeg
from homeassistant.components.camera import (
    Camera as CameraEntity,
    CameraEntityFeature,
    WebRTCAnswer as HAWebRTCAnswer,
    WebRTCCandidate as HAWebRTCCandidate,
    WebRTCError,
    WebRTCMessage,
    WebRTCSendMessage,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import SwitchBotKVSCameraConfigEntry
from .api_client.api_client import Device, KvsCredential
from .base_entity import SwitchBotKVSEntity
from .const import RESOLUTION, RESOLUTION_HD, SNAPSHOT_ENABLE, SNAPSHOT_INTERVAL
from .coordinator import SwitchBotKVSCameraCoordinator

_LOGGER = logging.getLogger(__name__)

PLACEHOLDER = Path(__file__).parent / "placeholder.png"


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: SwitchBotKVSCameraConfigEntry,
    async_add_entities: AddEntitiesCallback,
):
    """Set up the Cameras."""
    coordinator: SwitchBotKVSCameraCoordinator = config_entry.runtime_data.coordinator
    cameras = [
        SwitchBotKVSCameraEntity(
            hass,
            config_entry.unique_id,
            config_entry.options.get(RESOLUTION, RESOLUTION_HD),
            config_entry.options.get(SNAPSHOT_ENABLE, False),
            config_entry.options.get(SNAPSHOT_INTERVAL, 120),
            coordinator,
            device,
            kvs_credential=await coordinator.api_client.connect_as_viewer(
                [device.device_mac]
            ),
        )
        for device in coordinator.data.devices.devices
        if device.device_detail.device_type in ("WoCamKvs5mp", "WoCamKvs")
    ]
    async_add_entities(cameras)


class SwitchBotKVSCameraEntity(SwitchBotKVSEntity, CameraEntity):
    """Implementation of a camera."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry_unique_id: str,
        resolution: str,
        snapshot_enable: str,
        snapshot_interval: int,
        coordinator: SwitchBotKVSCameraCoordinator,
        device: Device,
        kvs_credential: KvsCredential,
    ) -> None:
        """Initialise camera."""
        SwitchBotKVSEntity.__init__(self, coordinator, device)
        CameraEntity.__init__(self)
        self.hass = hass
        self.entry_unique_id = entry_unique_id
        self.resolution = resolution
        self.snapshot_enable = snapshot_enable
        self.kvs_credential = kvs_credential
        self._attr_supported_features = CameraEntityFeature.STREAM
        self._attr_brand = "SwitchBot"
        self._attr_name = "Camera Stream(WebRTC)"
        self.ice_servers: list[dict[str, str]] | None = None
        self.channel_arn: str | None = None
        self.endpoints_by_protocol: dict | None = None
        self._sessions: dict[str, Go2RtcWsClient] = {}
        self.camera_image_interval = timedelta(seconds=snapshot_interval)
        self.camera_image_cache: dict[tuple[int, int], tuple[datetime, bytes]] = {}
        self.entity_id = f"camera.switchbot_camera_{device.device_mac}"
        self.unique_id = f"camera.switchbot_camera_{device.device_mac}"

    async def async_camera_image(
        self, width: int | None = None, height: int | None = None
    ) -> bytes | None:
        """Return a still image response from the camera."""

        isDownload = width is None and height is None
        if not self.snapshot_enable and not isDownload:
            return await self.hass.async_add_executor_job(self.placeholder_image)
        cacheKey = (width, height)

        if (
            cacheKey in self.camera_image_cache
            and self.camera_image_cache[cacheKey][0] + self.camera_image_interval
            > datetime.now(UTC)
            and len(self.camera_image_cache[cacheKey][1]) != 0
            and not isDownload
        ):
            return self.camera_image_cache[cacheKey][1]

        rtsp_port = await self._regist_go2rtc_stream_if_not_exists(isDownload)
        domain = re.search(r"http://([^:/]+)", self.hass.data["go2rtc"]).group(1)
        stream_source = f"rtsp://{domain}{rtsp_port}/{self.entity_id}"

        camera_image_latest = await ffmpeg.async_get_image(
            self.hass, stream_source, width=width, height=height, extra_cmd="-ss 2"
        )
        self.camera_image_cache[cacheKey] = (
            datetime.now(UTC),
            camera_image_latest,
        )
        return camera_image_latest

    @classmethod
    @functools.cache
    def placeholder_image(cls) -> bytes:
        """Return placeholder image to use when no stream is available."""
        return PLACEHOLDER.read_bytes()

    async def __get_signed_url(self) -> str:
        region = self.device.device_detail.awsRegion
        expiration_date = datetime.fromtimestamp(
            self.kvs_credential.expiration / 1000, tz=UTC
        )
        current_time = datetime.now(UTC)
        if expiration_date < current_time or self.channel_arn is None:
            (
                channel_arn,
                endpoints_by_protocol,
                ice_servers,
            ) = await self.__get_ice_servers(region)
            self.ice_servers = ice_servers
            self.channel_arn = channel_arn
            self.endpoints_by_protocol = endpoints_by_protocol

        auth_credentials = Credentials(
            access_key=self.kvs_credential.access,
            secret_key=self.kvs_credential.secret,
            token=self.kvs_credential.token,
        )
        SigV4 = SigV4QueryAuth(auth_credentials, "kinesisvideo", region, 299)
        parts = self.entry_unique_id.split("-")
        clientId = f"android_{self.device.device_mac.lower()}_{parts[3]}{parts[4][:4]}_{parts[4][4:]}"
        aws_request = AWSRequest(
            method="GET",
            url=self.endpoints_by_protocol["WSS"],
            params={
                "X-Amz-ChannelARN": self.channel_arn,
                "X-Amz-ClientId": clientId,
            },
        )
        SigV4.add_auth(aws_request)
        preparedRequest = aws_request.prepare()

        return (
            "webrtc:"
            + preparedRequest.url
            + "#format=switchbot"
            + "#resolution="
            + self.resolution.lower()
            + "#client_id="
            + clientId
            + "#ice_servers="
            + json.dumps(self.ice_servers, separators=(",", ":"))
        )

    async def __get_ice_servers(self, region) -> tuple[str, dict, list[dict[str, str]]]:
        self.kvs_credential = await self.coordinator.get_kvs_credential(
            self.device.device_mac
        )
        # Create a Kinesis Video client
        kwargs_boto3_client_kinesisvideo = {}
        kwargs_boto3_client_kinesisvideo["region_name"] = region
        kwargs_boto3_client_kinesisvideo["aws_access_key_id"] = (
            self.kvs_credential.access
        )
        kwargs_boto3_client_kinesisvideo["aws_secret_access_key"] = (
            self.kvs_credential.secret
        )
        kwargs_boto3_client_kinesisvideo["aws_session_token"] = (
            self.kvs_credential.token
        )
        kinesis_video_client = await self.hass.async_add_executor_job(
            partial(
                boto3.client,
                "kinesisvideo",
                **kwargs_boto3_client_kinesisvideo,
            )
        )

        # Describe the signaling channel
        kwargs_describe_signaling_channel = {}
        kwargs_describe_signaling_channel["ChannelName"] = self.kvs_credential.channels[
            self.device.device_mac
        ]
        describe_signaling_channel_response = await self.hass.async_add_executor_job(
            partial(
                kinesis_video_client.describe_signaling_channel,
                **kwargs_describe_signaling_channel,
            )
        )

        # Get the signaling channel endpoint
        channel_arn = describe_signaling_channel_response["ChannelInfo"]["ChannelARN"]
        kwargs_get_signaling_channel_endpoint = {}
        kwargs_get_signaling_channel_endpoint["ChannelARN"] = channel_arn
        kwargs_get_signaling_channel_endpoint[
            "SingleMasterChannelEndpointConfiguration"
        ] = {
            "Protocols": ["WSS", "HTTPS"],
            "Role": "VIEWER",
        }
        get_signaling_channel_endpoint_response = (
            await self.hass.async_add_executor_job(
                partial(
                    kinesis_video_client.get_signaling_channel_endpoint,
                    **kwargs_get_signaling_channel_endpoint,
                )
            )
        )
        endpoints_by_protocol = {
            endpoint["Protocol"]: endpoint["ResourceEndpoint"]
            for endpoint in get_signaling_channel_endpoint_response[
                "ResourceEndpointList"
            ]
        }
        # Create a Kinesis Video Signaling Channels client
        kwargs_boto3_client_kinesis_video_signaling = {}
        kwargs_boto3_client_kinesis_video_signaling["region_name"] = region
        kwargs_boto3_client_kinesis_video_signaling["aws_access_key_id"] = (
            self.kvs_credential.access
        )
        kwargs_boto3_client_kinesis_video_signaling["aws_secret_access_key"] = (
            self.kvs_credential.secret
        )
        kwargs_boto3_client_kinesis_video_signaling["aws_session_token"] = (
            self.kvs_credential.token
        )
        kwargs_boto3_client_kinesis_video_signaling["endpoint_url"] = (
            endpoints_by_protocol["HTTPS"]
        )
        kinesis_video_signaling_channels_client = (
            await self.hass.async_add_executor_job(
                partial(
                    boto3.client,
                    "kinesis-video-signaling",
                    **kwargs_boto3_client_kinesis_video_signaling,
                )
            )
        )
        # Get ICE server configuration
        kwargs_get_ice_server_config = {}
        kwargs_get_ice_server_config["ChannelARN"] = channel_arn
        get_ice_server_config_response = await self.hass.async_add_executor_job(
            partial(
                kinesis_video_signaling_channels_client.get_ice_server_config,
                **kwargs_get_ice_server_config,
            )
        )
        ice_servers = [{"urls": f"stun:stun.kinesisvideo.{region}.amazonaws.com:443"}]
        ice_servers.extend(
            {
                "urls": ice_server["Uris"],
                "username": ice_server["Username"],
                "credential": ice_server["Password"],
            }
            for ice_server in get_ice_server_config_response["IceServerList"]
        )

        return channel_arn, endpoints_by_protocol, ice_servers

    async def _regist_go2rtc_stream_if_not_exists(self, isDownload: bool) -> str:
        rest_client = Go2RtcRestClient(
            async_get_clientsession(self.hass), self.hass.data["go2rtc"]
        )
        resp = await rest_client._client.request("GET", "/api")  # noqa: SLF001
        respJson = await resp.json()
        rtsp_port: str = respJson["rtsp"]["listen"]
        if isDownload:
            return rtsp_port

        signed_url = await self.__get_signed_url()

        streams = await rest_client.streams.list()

        if (stream := streams.get(self.entity_id)) is None or not any(
            signed_url == producer.url for producer in stream.producers
        ):
            await rest_client.streams.add(
                self.entity_id + "-internal",
                [signed_url],
            )
            await rest_client.streams.add(
                self.entity_id,
                [
                    f"ffmpeg:{self.entity_id}-internal#video=h264#query=log_level=debug",
                ],
            )

        return rtsp_port

    async def async_handle_async_webrtc_offer(
        self, offer_sdp: str, session_id: str, send_message: WebRTCSendMessage
    ) -> None:
        """Handle the async WebRTC offer."""
        self._sessions[session_id] = ws_client = Go2RtcWsClient(
            async_get_clientsession(self.hass),
            self.hass.data["go2rtc"],
            source=self.entity_id,
        )
        await self._regist_go2rtc_stream_if_not_exists(False)

        @callback
        def on_messages(message: ReceiveMessages) -> None:
            """Handle messages."""
            value: WebRTCMessage
            match message:
                case WebRTCCandidate():
                    value = HAWebRTCCandidate(RTCIceCandidateInit(message.candidate))
                case WebRTCAnswer():
                    value = HAWebRTCAnswer(message.sdp)
                case WsError():
                    value = WebRTCError("go2rtc_webrtc_offer_failed", message.error)

            send_message(value)

        ws_client.subscribe(on_messages)
        config = self.async_get_webrtc_client_configuration()
        await ws_client.send(WebRTCOffer(offer_sdp, config.configuration.ice_servers))

    async def async_on_webrtc_candidate(
        self, session_id: str, candidate: RTCIceCandidateInit
    ) -> None:
        """Handle the WebRTC candidate."""

        if ws_client := self._sessions.get(session_id):
            await ws_client.send(WebRTCCandidate(candidate.candidate))
        else:
            _LOGGER.debug("Unknown session %s. Ignoring candidate", session_id)

    @callback
    def async_close_session(self, session_id: str) -> None:
        """Close the session."""
        ws_client = self._sessions.pop(session_id)
        self._hass.async_create_task(ws_client.close())
