"""SwitchBot KVSCamera coordinator."""

import asyncio
from dataclasses import dataclass
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import APPLICATION_NAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api_client.api_client import (
    Device,
    Devices,
    KvsCredential,
    KVSPreset,
    SwitchBotApiClient,
)
from .api_client.exceptions import ApiError
from .const import DOMAIN, LOGGER
from .mqtt_client.mqtt_client import SwitchBotMqttClient
from .mqtt_client.mqtt_kvs_cam import (
    KvsStatus,
    SdCardCapacity,
    SwitchBotMqttKVSCam,
    WiFiInfo,
)

CONNECT_FAILED_NOT_AUTHORISED = 5


@dataclass
class CoordinatorData:
    """Class to hold api data."""

    devices: Devices | None = None
    kvs_statuses: dict[str, KvsStatus] | None = None
    kvs_sd_card_capacities: dict[str, SdCardCapacity] | None = None
    kvs_wifi_infos: dict[str, WiFiInfo] | None = None
    kvs_presets: dict[str, list[KVSPreset]] | None = None
    kvs_preset_selects: dict[str, str] | None = None
    kvs_preset_texts: dict[str, str] | None = None


class SwitchBotKVSCameraCoordinator(DataUpdateCoordinator):
    """SwitchBot KVSCamera coordinator."""

    data: CoordinatorData
    mqtt_kvs_cams: dict[str, SwitchBotMqttKVSCam]

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        """Initialize coordinator."""

        self.api_credential = SwitchBotApiClient.ApiCredential(
            config_entry.data["device_id"],
            config_entry.data["access_token"],
            config_entry.data["refresh_token"],
            config_entry.data["jwt_payload"],
            config_entry.data["bot_region"],
            config_entry.data["user_id"],
            config_entry.data["email"],
            config_entry.data["wonderlab_endpoint"],
            config_entry.data["mqtt_self_signed_endpoint"],
            config_entry.data["mqtt_self_signed_cert_private_key_pem"],
            config_entry.data["mqtt_self_signed_cert_public_key_pem"],
        )

        super().__init__(
            hass,
            LOGGER,
            name=f"{DOMAIN} ({config_entry.unique_id})",
            setup_method=self._async_setup,
            update_method=self._async_update_data,
            update_interval=timedelta(seconds=259),
        )

        self.api_client = SwitchBotApiClient(
            http_client_session=async_get_clientsession(hass),
            device_id=config_entry.data["device_id"],
            device_name=APPLICATION_NAME,
            model=f"{DOMAIN}-integration",
            api_credential=self.api_credential,
            save_refreshed_token=self.save_refreshed_token,
        )
        self.mqtt_client = SwitchBotMqttClient(
            device_id=config_entry.data["device_id"],
            mqtt_self_signed_endpoint=config_entry.data["mqtt_self_signed_endpoint"],
            mqtt_self_signed_cert_public_key_pem=config_entry.data[
                "mqtt_self_signed_cert_public_key_pem"
            ],
            mqtt_self_signed_cert_private_key_pem=config_entry.data[
                "mqtt_self_signed_cert_private_key_pem"
            ],
            subscribe_topics=[
                f"switchlink/{config_entry.data['user_id']}/#",
                f"v1_1/{config_entry.data['user_id']}/#",
            ],
        )

    def save_refreshed_token(self) -> None:
        """Save the refreshed token."""
        new_data = self.config_entry.data.copy()
        new_data["access_token"] = self.api_client.api_credential.access_token
        new_data["jwt_payload"] = self.api_client.api_credential.jwt_payload

        @callback
        def async_update_entry() -> None:
            """Update config entry."""
            self.hass.config_entries.async_update_entry(
                self.config_entry, data=new_data
            )

        self.hass.add_job(async_update_entry)

    def unload(self) -> None:
        """Unload the coordinator."""
        self.mqtt_client.stop()

    async def _async_setup(self) -> None:
        """Do initialization logic."""
        try:
            self.data = CoordinatorData()
            self.data.devices = await self.api_client.get_all_devices()
        except ApiError as err:
            LOGGER.error(err)
            raise UpdateFailed(err) from err
        except Exception as err:
            raise UpdateFailed(f"Error communicating with API: {err}") from err
        self.mqtt_client.start()

        while not self.mqtt_client.is_connected():
            await asyncio.sleep(1)

        parts = self.config_entry.unique_id.split("-")
        self.mqtt_kvs_cams = {}
        self.data.kvs_statuses = {}
        self.data.kvs_sd_card_capacities = {}
        self.data.kvs_wifi_infos = {}
        self.data.kvs_presets = {}
        self.data.kvs_preset_texts = {}
        self.data.kvs_preset_selects = {}
        for kvsCam in (
            device
            for device in self.data.devices.devices
            if device.device_detail.device_type in ("WoCamKvs5mp", "WoCamKvs")
        ):
            mqtt_kvs_cam = SwitchBotMqttKVSCam(
                mqtt_client=self.mqtt_client,
                device=kvsCam,
                identifier=f"android_{kvsCam.device_mac.lower()}_{parts[3]}{parts[4][:4]}_{parts[4][4:]}",
                update_kvs_status=self.on_kvs_status_update,
                update_sd_card_capacity=self.update_sd_card_capacity,
                update_wifi_info=self.update_wifi_info,
                complete_create_preset=self.complete_create_preset,
            )
            self.mqtt_kvs_cams[kvsCam.device_mac] = mqtt_kvs_cam
            # Update the KVS status
            mqtt_kvs_cam.request_device_status()
            # Update the SD card capacity
            mqtt_kvs_cam.request_sd_card_capacity()
            # Update the WiFi info
            mqtt_kvs_cam.request_wifi_info()
            # Update the KVS presets
            self.data.kvs_presets[
                kvsCam.device_mac
            ] = await self.api_client.list_kvs_preset(kvsCam.device_mac, kvsCam.groupID)
            self.data.kvs_preset_texts[kvsCam.device_mac] = ""
            self.data.kvs_preset_selects[kvsCam.device_mac] = ""

    def on_kvs_status_update(self, device_mac: str, kvs_status: KvsStatus) -> None:
        """Handle kvs status update."""
        self.data.kvs_statuses[device_mac] = kvs_status

        # Notify the coordinator that the data has changed
        self.hass.loop.call_soon_threadsafe(self.async_set_updated_data, self.data)

    def complete_create_preset(self, device_mac: str, group_id: str) -> None:
        """Handle complete create preset."""
        self.data.kvs_preset_texts[device_mac] = ""
        self.reload_preset(device_mac, group_id)

    def reload_preset(self, device_mac: str, group_id: str) -> None:
        """Reload preset."""
        self.data.kvs_presets[device_mac] = asyncio.run_coroutine_threadsafe(
            self.api_client.list_kvs_preset(device_mac, group_id), self.hass.loop
        ).result()
        self.hass.loop.call_soon_threadsafe(self.async_set_updated_data, self.data)

    def update_sd_card_capacity(
        self, device_mac: str, sd_card_capacity: SdCardCapacity
    ) -> None:
        """Handle sd card capacity update."""
        self.data.kvs_sd_card_capacities[device_mac] = sd_card_capacity

        # Notify the coordinator that the data has changed
        self.hass.loop.call_soon_threadsafe(self.async_set_updated_data, self.data)

    def update_wifi_info(self, device_mac: str, wifi_info: WiFiInfo) -> None:
        """Handle wifi info update."""
        self.data.kvs_wifi_infos[device_mac] = wifi_info
        # Notify the coordinator that the data has changed
        self.hass.loop.call_soon_threadsafe(self.async_set_updated_data, self.data)

    async def _async_update_data(self):
        """Fetch data from API endpoint."""
        try:
            self.data.devices = await self.api_client.get_all_devices()
        except ApiError as err:
            LOGGER.error(err)
            raise UpdateFailed(err) from err
        except Exception as err:
            raise UpdateFailed(f"Error communicating with API: {err}") from err

        for mqtt_kvs_cam in self.mqtt_kvs_cams.values():
            # Update the KVS status
            mqtt_kvs_cam.request_device_status()
            # Update the SD card capacity
            mqtt_kvs_cam.request_sd_card_capacity()
            # Update the WiFi info
            mqtt_kvs_cam.request_wifi_info()
            # Update the KVS presets
            self.data.kvs_presets[
                mqtt_kvs_cam.device.device_mac
            ] = await self.api_client.list_kvs_preset(
                mqtt_kvs_cam.device.device_mac, mqtt_kvs_cam.device.groupID
            )

        # What is returned here is stored in self.data by the DataUpdateCoordinator
        return self.data

    def get_device_by_id(self, device_mac: str) -> Device | None:
        """Return device by device id."""
        # Called by the binary sensors and sensors to get their updated data from self.data
        try:
            return [
                device
                for device in self.data.devices
                if device.device_mac == device_mac
            ][0]
        except IndexError:
            return None

    def get_kvs_credential(self, device_mac: str) -> KvsCredential | None:
        """Return KvsCredential."""
        return self.api_client.connect_as_viewer([device_mac])
