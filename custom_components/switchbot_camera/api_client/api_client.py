"""SwitchBot API Client."""

from __future__ import annotations

import base64
from collections.abc import Callable
import json
import logging
import time
from typing import Any

from aiohttp import ClientSession
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.serialization import pkcs12

from .exceptions import ApiError
from .model.devices import Device, DeviceDetail, Devices, Remote
from .model.group import Group
from .model.kvs_credential import KvsCredential
from .model.kvs_preset import KVSPreset

LOGGER = logging.getLogger(__package__)


class SwitchBotApiClient:
    """SwitchBotClient class."""

    def __init__(
        self,
        device_id: str | None = None,
        device_name: str | None = None,
        model: str | None = None,
        http_client_session: ClientSession | None = None,
        api_credential: ApiCredential | None = None,
        save_refreshed_token: Callable[[], None] | None = None,
    ) -> None:
        """Initialize."""
        self.device_id = device_id
        self.device_name = device_name
        self.model = model
        self._local_session: ClientSession | None = None
        self.http_client_session = http_client_session
        self.api_credential = api_credential
        self.save_refreshed_token = save_refreshed_token

    @property
    def _session(self) -> ClientSession:
        if self.http_client_session:
            return self.http_client_session
        if self._local_session is None:
            self._local_session = ClientSession()
        return self._local_session

    async def login(self, username: str, password: str) -> ApiCredential:
        """Login,Get userinfo,Get endpoints."""
        api_credentials = await self.__user_login(username, password)
        user_info = await self.__get_user_info(api_credentials.access_token)
        api_credentials.bot_region = user_info["botRegion"]
        api_credentials.user_id = user_info["userID"]
        api_credentials.email = user_info["email"]
        endpoints = await self.__get_endpoints(
            api_credentials.access_token, api_credentials.bot_region
        )
        api_credentials.wonderlab_endpoint = next(
            (v["host"] for v in endpoints if v["name"] == "wonderlabs"), None
        )
        api_credentials.mqtt_self_signed_endpoint = next(
            (v["host"] for v in endpoints if v["name"] == "MQTTSelfSigned"), None
        )
        private_key_pem_b64, public_key_pem_b64 = await self.__get_policy_cert(
            api_credentials.access_token, api_credentials.wonderlab_endpoint
        )
        api_credentials.mqtt_self_signed_cert_private_key_pem = private_key_pem_b64
        api_credentials.mqtt_self_signed_cert_public_key_pem = public_key_pem_b64
        return api_credentials

    async def __user_login(self, username: str, password: str) -> ApiCredential:
        """Login SwitchBot."""

        url = "https://account.api.switchbot.net/account/api/v1/user/login"
        headers = {"Content-Type": "application/json"}
        data = {
            "clientId": "5nnwmhmsa9xxskm14hd85lm9bm",
            "deviceInfo": {
                "deviceId": self.device_id,
                "deviceName": self.device_name,
                "model": self.model,
            },
            "grantType": "password",
            "password": password,
            "username": username,
            "verifyCode": "",
        }

        async with self._session.post(
            url, headers=headers, data=json.dumps(data)
        ) as response:
            if response.status != 200:
                LOGGER.warning("URL:%s Status:%s", url, response.status)
                raise ApiError(f"Server error. http status code {response.status}")

            resp = await response.json()
            if not resp.get("statusCode") or resp["statusCode"] != 100:
                LOGGER.warning("URL:%s Response:%s", url, resp)
                raise ApiError(f"Server error. status code {resp.get('statusCode')}")

            LOGGER.debug("URL:%s Response:%s", url, resp)
            access_token = resp["body"]["access_token"]
            refresh_token = resp["body"]["refresh_token"]
            jwt_payload = json.loads(
                base64.b64decode(access_token.split(".")[1] + "==").decode()
            )
            return self.ApiCredential(
                self.device_id, access_token, refresh_token, jwt_payload
            )

    async def __get_user_info(self, access_token: str) -> dict[str, Any]:
        """Get UserInfo."""
        url = "https://account.api.switchbot.net/account/api/v1/user/userinfo"
        headers = {
            "Content-Type": "application/json",
            "authorization": access_token,
        }
        async with self._session.post(url, headers=headers) as response:
            if response.status != 200:
                LOGGER.warning("URL:%s Status:%s", url, response.status)
                raise ApiError(f"Server error. http status code {response.status}")

            resp = await response.json()
            if not resp.get("statusCode") or resp["statusCode"] != 100:
                LOGGER.warning("URL:%s Response:%s", url, resp)
                raise ApiError(f"Server error. status code {resp.get('statusCode')}")

            LOGGER.debug("URL:%s Response:%s", url, resp)
            return resp["body"]

    async def __get_endpoints(
        self, access_token: str, bot_region: str
    ) -> dict[str, Any]:
        """Get endpoints."""
        url = "https://account.api.switchbot.net/admin/admin/api/v1/botregion/endpoint"
        headers = {
            "Content-Type": "application/json",
            "authorization": access_token,
        }
        data = {"botRegion": bot_region}
        async with self._session.post(
            url, headers=headers, data=json.dumps(data)
        ) as response:
            if response.status != 200:
                LOGGER.warning("URL:%s Status:%s", url, response.status)
                raise ApiError(f"Server error. http status code {response.status}")

            resp = await response.json()
            if not resp.get("resultCode") or resp["resultCode"] != 100:
                LOGGER.warning("URL:%s Response:%s", url, resp)
                raise ApiError(f"Server error. result code {resp.get('resultCode')}")

            LOGGER.debug("URL:%s Response:%s", url, resp)
            return resp["data"]

    async def __get_policy_cert(
        self, access_token: str, wonderlab_endpoint: str
    ) -> tuple[str, str]:
        """Get endpoints."""
        url = f"{wonderlab_endpoint}/wonder/user/policyCer"
        headers = {
            "Content-Type": "application/json",
            "authorization": access_token,
        }
        data = {"MQTTSelfSigned": True}
        async with self._session.post(
            url, headers=headers, data=json.dumps(data)
        ) as response:
            if response.status != 200:
                LOGGER.warning("URL:%s Status:%s", url, response.status)
                raise ApiError(f"Server error. http status code {response.status}")

            resp = await response.json()
            if not resp.get("statusCode") or resp["statusCode"] != 100:
                LOGGER.warning("URL:%s Response:%s", url, resp)
                raise ApiError(f"Server error. status code {resp.get('statusCode')}")

            LOGGER.debug("URL:%s Response:%s", url, resp)

            pkcs12_key_and_certificates = pkcs12.load_pkcs12(
                base64.b64decode(resp["body"]), b"12345678"
            )
            private_key_pem = pkcs12_key_and_certificates.key.private_bytes(
                serialization.Encoding.PEM,
                format=serialization.PrivateFormat.TraditionalOpenSSL,
                encryption_algorithm=serialization.NoEncryption(),
            )
            public_key_pem = pkcs12_key_and_certificates.cert.certificate.public_bytes(
                serialization.Encoding.PEM
            )
            return base64.b64encode(private_key_pem).decode(), base64.b64encode(
                public_key_pem
            ).decode()

    class ApiCredential:
        """Api Credential."""

        def __init__(
            self,
            device_id: str,
            access_token: str,
            refresh_token: str,
            jwt_payload: Any,
            bot_region: str | None = None,
            user_id: str | None = None,
            email: str | None = None,
            wonderlab_endpoint: str | None = None,
            mqtt_self_signed_endpoint: str | None = None,
            mqtt_self_signed_cert_private_key_pem: str | None = None,
            mqtt_self_signed_cert_public_key_pem: str | None = None,
        ) -> None:
            """Initialize."""
            self.device_id = device_id
            self.access_token = access_token
            self.refresh_token = refresh_token
            self.jwt_payload = jwt_payload
            self.bot_region = bot_region
            self.user_id = user_id
            self.email = email
            self.wonderlab_endpoint = wonderlab_endpoint
            self.mqtt_self_signed_endpoint = mqtt_self_signed_endpoint
            self.mqtt_self_signed_cert_private_key_pem = (
                mqtt_self_signed_cert_private_key_pem
            )
            self.mqtt_self_signed_cert_public_key_pem = (
                mqtt_self_signed_cert_public_key_pem
            )

    async def check_token_refresh(self) -> None:
        """Token refresh if needed."""

        if self.api_credential.jwt_payload["exp"] >= time.time():
            return

        url = "https://account.api.switchbot.net/account/api/v1/user/token/refresh"
        headers = {"Content-Type": "application/json"}
        data = {
            "clientId": "5nnwmhmsa9xxskm14hd85lm9bm",
            "clientSecret": "vzxjw7rvmduka4rlysdcv0bfke70icql33ol1pvr",
            "deviceId": self.device_id,
            "refreshToken": self.api_credential.refresh_token,
            "userId": self.api_credential.jwt_payload["userID"],
        }

        async with self._session.post(
            url, headers=headers, data=json.dumps(data)
        ) as response:
            if response.status != 200:
                LOGGER.warning("URL:%s Status:%s", url, response.status)
                raise ApiError(f"Server error. http status code {response.status}")

            resp = await response.json()
            if not resp.get("statusCode") or resp["statusCode"] != 100:
                LOGGER.warning("URL:%s Response:%s", url, resp)
                raise ApiError(f"Server error. status code {resp.get('statusCode')}")

            LOGGER.debug("URL:%s Response:%s", url, resp)
            self.api_credential.access_token = resp["body"]["access_token"]
            self.api_credential.jwt_payload = json.loads(
                base64.b64decode(
                    self.api_credential.access_token.split(".")[1] + "=="
                ).decode()
            )
            if self.save_refreshed_token is not None:
                self.save_refreshed_token()

    async def __get_all_groups(self) -> list[Group]:
        """Get groups."""
        await self.check_token_refresh()
        url = f"{self.api_credential.wonderlab_endpoint}/homepage/v1/group/getall"
        headers = {
            "Content-Type": "application/json",
            "authorization": self.api_credential.access_token,
        }
        async with self._session.post(url, headers=headers) as response:
            if response.status != 200:
                LOGGER.warning("URL:%s Status:%s", url, response.status)
                raise ApiError(f"Server error. http status code {response.status}")

            resp = await response.json()
            if not resp.get("resultCode") or resp["resultCode"] != 100:
                LOGGER.warning("URL:%s Response:%s", url, resp)
                raise ApiError(f"Server error. result code {resp.get('resultCode')}")
            LOGGER.debug("URL:%s Response:%s", url, resp)
            data = list[Group]()
            for groupDict in resp["data"]["groups"]:
                group = Group()
                group.__dict__.update(groupDict)
                data.append(group)
            return data

    async def get_all_devices(self) -> Devices:
        """Get devices."""
        await self.check_token_refresh()
        url = f"{self.api_credential.wonderlab_endpoint}/homepage/v1/device/getall"
        headers = {
            "Content-Type": "application/json",
            "authorization": self.api_credential.access_token,
        }
        devices: list[Device] = []
        remotes: list[Remote] = []
        groups = await self.__get_all_groups()
        for group in groups:
            requestBody = {"groupID": group.groupID}
            async with self._session.post(
                url, headers=headers, data=json.dumps(requestBody)
            ) as response:
                if response.status != 200:
                    LOGGER.warning("URL:%s Status:%s", url, response.status)
                    raise ApiError(f"Server error. http status code {response.status}")

                resp = await response.json()
                if not resp.get("resultCode") or resp["resultCode"] != 100:
                    LOGGER.warning("URL:%s Response:%s", url, resp)
                    raise ApiError(
                        f"Server error. result code {resp.get('resultCode')}"
                    )
                LOGGER.debug("URL:%s Response:%s", url, resp)
                data = Devices([], [])
                data.__dict__.update(resp["data"])
                for deviceDict in data.devices:
                    device = Device()
                    device.__dict__.update(deviceDict)
                    device.device_detail = DeviceDetail()
                    device.device_detail.__dict__.update(deviceDict["device_detail"])
                    devices.append(device)
                for remoteDict in data.remotes:
                    remote = Remote()
                    remote.__dict__.update(remoteDict)
                    remotes.append(remote)
        return Devices(devices, remotes)

    async def connect_as_viewer(self, device_id_list: list[str]) -> KvsCredential:
        """Get kvs credential."""
        await self.check_token_refresh()
        url = f"{self.api_credential.wonderlab_endpoint}/kvs/v1/connectAsViewer"
        headers = {
            "Content-Type": "application/json",
            "authorization": self.api_credential.access_token,
        }
        data = {"deviceList": device_id_list}
        async with self._session.post(
            url, headers=headers, data=json.dumps(data)
        ) as response:
            if response.status != 200:
                LOGGER.warning("URL:%s Status:%s", url, response.status)
                raise ApiError(f"Server error. http status code {response.status}")

            resp = await response.json()
            if not resp.get("resultCode") or resp["resultCode"] != 100:
                LOGGER.warning("URL:%s Response:%s", url, resp)
                raise ApiError(f"Server error. result code {resp.get('resultCode')}")
            LOGGER.debug("URL:%s Response:%s", url, resp)
            return KvsCredential(
                resp["data"]["channels"],
                resp["data"]["credential"]["access"],
                resp["data"]["credential"]["secret"],
                resp["data"]["credential"]["token"],
                resp["data"]["credential"]["expiration"],
            )

    async def list_kvs_preset(self, device_id: str, group_id: str) -> list[KVSPreset]:
        """list_kvs_preset."""
        await self.check_token_refresh()
        url = f"{self.api_credential.wonderlab_endpoint}/kvs/v1/listPreset"
        headers = {
            "Content-Type": "application/json",
            "authorization": self.api_credential.access_token,
        }
        data = {"deviceID": device_id, "groupID": group_id}
        async with self._session.post(
            url, headers=headers, data=json.dumps(data)
        ) as response:
            if response.status != 200:
                raise ApiError(f"Server error. http status code {response.status}")

            resp = await response.json()
            if not resp.get("resultCode") or resp["resultCode"] != 100:
                raise ApiError(f"Server error. result code {resp.get('resultCode')}")
            LOGGER.debug("URL:%s Response:%s", url, resp)
            data = list[KVSPreset]()
            for presetDict in resp["data"]["presetList"]:
                preset = KVSPreset()
                preset.__dict__.update(presetDict)
                data.append(preset)
            return data

    async def update_kvs_preset(
        self, device_id: str, group_id: str, is_favorite: bool, name: str, id: str
    ) -> None:
        """list_kvs_preset."""
        await self.check_token_refresh()
        url = f"{self.api_credential.wonderlab_endpoint}/kvs/v1/updatePreset"
        headers = {
            "Content-Type": "application/json",
            "authorization": self.api_credential.access_token,
        }
        data = {
            "deviceID": device_id,
            "groupID": group_id,
            "isFavorite": is_favorite,
            "name": name,
            "presetPointID": id,
        }
        async with self._session.post(
            url, headers=headers, data=json.dumps(data)
        ) as response:
            if response.status != 200:
                raise ApiError(f"Server error. http status code {response.status}")

            resp = await response.json()
            if not resp.get("resultCode") or resp["resultCode"] != 100:
                raise ApiError(f"Server error. result code {resp.get('resultCode')}")
            LOGGER.debug("URL:%s Response:%s", url, resp)
