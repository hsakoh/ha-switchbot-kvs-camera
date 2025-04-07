"""SwitchBot KVS Camera MQTT Client."""

from collections.abc import Callable
from enum import IntEnum, StrEnum, auto
import json
import logging
import time

from ..api_client.model.devices import Device  # noqa: TID252
from .mqtt_client import SwitchBotMqttClient
from .mqtt_device import MqttDevice

LOGGER = logging.getLogger(__package__)


class Detectalarm:
    """Detect Alarm."""

    duration: int
    volume: int
    tone: int
    open: bool


class KvsStatus:
    """Status."""

    antiFlicker: str  # noqa: N815
    autoUpgrade: bool  # noqa: N815
    cpu_version: str
    detectAlarm: Detectalarm  # noqa: N815
    doubleSpeedRatio: str  # noqa: N815
    doubleSpeedType: str  # noqa: N815
    hardware_version: int
    ipAddress: str  # noqa: N815
    isCruiseOpen: bool  # noqa: N815
    isHaveSdCard: bool  # noqa: N815
    isInPrivateMode: bool  # noqa: N815
    isOpenArea: bool  # noqa: N815
    isOpenDarkFullColor: bool  # noqa: N815
    isOpenFlipScreen: bool  # noqa: N815
    isOpenHumamFilter: bool  # noqa: N815
    isOpenIndicatorLight: bool  # noqa: N815
    isOpenMobileTracking: bool  # noqa: N815
    isOpenMotionDetection: bool  # noqa: N815
    isOpenNightVision: str  # noqa: N815
    isOpenRecord: bool  # noqa: N815
    isOpenSingleIntercom: str  # noqa: N815
    isOpenTimeWatermark: bool  # noqa: N815
    mcu_version: str
    muteRecord: bool  # noqa: N815
    recordMode: int  # noqa: N815
    reslution: str
    sdcardFormateTime: int  # noqa: N815
    sdcardStatus: int  # noqa: N815
    sensitivityLevel: str  # noqa: N815
    setK20Bind: int  # noqa: N815
    soundAlarm: bool  # noqa: N815
    timeZoneID: str  # noqa: N815
    timeZonePosix: str  # noqa: N815
    timestamp: int
    type: str
    volumeLevel: str  # noqa: N815
    wifiSignal: str  # noqa: N815


class SdCardCapacity:
    """SdCardCapacity."""

    free: float
    isOpenRecord: bool  # noqa: N815
    muteRecord: bool  # noqa: N815
    recordMode: int  # noqa: N815
    timestamp: int
    total: float
    type: str
    used: float


class WiFiInfo:
    """WiFiInfo."""

    ipAddress: str  # noqa: N815
    timestamp: int
    type: str
    wifiName: str  # noqa: N815
    wifiSignal: str  # noqa: N815


class MotorDirection(StrEnum):
    """MotorDirection class."""

    RIGHT = auto()
    LEFT = auto()
    UP = auto()
    DOWN = auto()


class MotorAction(StrEnum):
    """MotorAction class."""

    ON = auto()
    OFF = auto()
    CLICK = auto()


class AntiFlickerLevel(StrEnum):
    """AntiFlickerLevel class."""

    L60Hz = "2"
    L50Hz = "1"


class NightVisionLevel(StrEnum):
    """NightVisionLevel class."""

    OFF = "1"
    ALLWAYS_ON = "2"
    AUTO = "0"


class RecordMode(IntEnum):
    """RecordMode class."""

    EVENT = 2
    CONTINUES = 1


class IntercomWay(StrEnum):
    """IntercomWay class."""

    ONEWAY = "0"
    TWOWAY = "1"


class SensitivityLevel(StrEnum):
    """SensitivityLevel class."""

    LOW = "0"
    MEDIUM = "1"
    HIGH = "2"


class VolumeLevel(StrEnum):
    """VolumeLevel class."""

    _0 = "0"
    _1 = "1"
    _2 = "2"
    _3 = "3"
    _4 = "4"
    _5 = "5"
    _6 = "6"
    _7 = "7"
    _8 = "8"
    _9 = "9"
    _10 = "10"


class SwitchBotMqttKVSCam(MqttDevice):
    """SwitchBotMqttDevice class."""

    def __init__(
        self,
        mqtt_client: SwitchBotMqttClient,
        device: Device,
        identifier: str,
        update_kvs_status: Callable[[str, KvsStatus], None],
        update_sd_card_capacity: Callable[[str, KvsStatus], None],
        update_wifi_info: Callable[[str, KvsStatus], None],
        complete_create_preset: Callable[[str, str], None],
    ) -> None:
        """Initialize."""
        super().__init__(mqtt_client, device)
        self.control_topic = f"$aws/rules/kvs_user_message_route_rule/switchlink/{device.userID}/{device.device_mac}/{device.device_detail.device_type}/appToKvsBack"
        self.identifier = identifier

        self.kvs_back_to_app_topic = f"switchlink/{device.userID}/{device.device_mac}/{device.device_detail.device_type}/kvsBackToApp"
        self._mqtt_client.subscribe(
            self.kvs_back_to_app_topic,
            self.on_kvs_back_to_app,
        )
        self.update_kvs_status = update_kvs_status
        self.update_sd_card_capacity = update_sd_card_capacity
        self.update_wifi_info = update_wifi_info
        self.complete_create_preset = complete_create_preset

    def on_kvs_back_to_app(self, topic: str, payload_str: str) -> None:
        """Handle incoming messages."""
        if topic == self.kvs_back_to_app_topic:
            LOGGER.debug(
                "SwitchBotMqttKVSCam %s %s kvsBackToApp -> %s",
                self.device.device_mac,
                self.device.device_detail.device_type,
                payload_str,
            )
            payload = json.loads(payload_str)
            if payload["type"] == "status":
                kvs_status = KvsStatus()
                kvs_status.__dict__.update(payload)
                self.update_kvs_status(self.device.device_mac, kvs_status)
            elif payload["type"] == "sdCardCapacity":
                sd_card_capacity = SdCardCapacity()
                sd_card_capacity.__dict__.update(payload)
                self.update_sd_card_capacity(self.device.device_mac, sd_card_capacity)
            elif payload["type"] == "requestWiFiInfo":
                wifi_info = WiFiInfo()
                wifi_info.__dict__.update(payload)
                self.update_wifi_info(self.device.device_mac, wifi_info)
            elif (
                payload["type"]
                in [
                    # button
                    "autoUpgrade",
                    "setCruiseOpen",
                    "setPrivacy",
                    "setDarkFullColor",
                    "setFlipView",
                    "setHumanFilter",
                    "setIndicatorLight",
                    "isOpenMobileTracking",
                    "setMoveDetect",
                    "setSdCardStorage",
                    "setTimeWatermark",
                    "setSensitive",
                    "muteRecord",
                    "createPreset",
                    # select
                    "setAntiFlicker",
                    "set_night_vision",
                    "set_intercom_way",
                    "set_sensitive_level",
                    "triggerPreset",
                    # number
                    "setVolumeLevel",
                ]
                and payload["ack"] == 0
            ):
                # reload the status
                self.request_device_status()
                if payload["type"] == "createPreset":
                    self.complete_create_preset(
                        self.device.device_mac, self.device.groupID
                    )

    def request_device_status(self) -> None:
        """request_device_status."""
        self._mqtt_client.publish(
            self.control_topic,
            json.dumps(
                {
                    "type": "updateDeviceStatus",
                    "timestamp": int(time.time()),
                    "identifier": self.identifier,
                }
            ),
        )

    def request_sd_card_capacity(self) -> None:
        """request_sd_card_capacity."""
        self._mqtt_client.publish(
            self.control_topic,
            json.dumps(
                {
                    "type": "requestSdCardCapacity",
                    "timestamp": int(time.time()),
                    "identifier": self.identifier,
                }
            ),
        )

    def request_wifi_info(self) -> None:
        """request_wifi_info."""
        self._mqtt_client.publish(
            self.control_topic,
            json.dumps(
                {
                    "type": "requestWiFiInfo",
                    "timestamp": int(time.time()),
                    "identifier": self.identifier,
                }
            ),
        )

    def request_alarm_program(self) -> None:
        """request_alarm_program."""
        self._mqtt_client.publish(
            self.control_topic,
            json.dumps(
                {
                    "type": "alarmProgram",
                    "timestamp": int(time.time()),
                    "action": "get",
                    "identifier": self.identifier,
                }
            ),
        )

    def motor(self, direction: MotorDirection, action: MotorAction) -> None:
        """Motor."""
        self._mqtt_client.publish(
            self.control_topic,
            json.dumps(
                {
                    "type": "motor",
                    "direction": direction,
                    "action": action,
                    "identifier": self.identifier,
                }
            ),
        )

    def set_flipview(self, open: bool) -> None:
        """set_flipview."""
        self._mqtt_client.publish(
            self.control_topic,
            json.dumps(
                {
                    "type": "setFlipView",
                    "open": open,
                    "identifier": self.identifier,
                }
            ),
        )

    def set_camera_calibration(self) -> None:
        """set_camera_calibration."""
        self._mqtt_client.publish(
            self.control_topic,
            json.dumps(
                {
                    "type": "setCameraCalibration",
                    "open": True,
                    "identifier": self.identifier,
                }
            ),
        )

    def set_privacy(self, open: bool) -> None:
        """set_privacy."""
        self._mqtt_client.publish(
            self.control_topic,
            json.dumps(
                {
                    "type": "setPrivacy",
                    "open": open,
                    "identifier": self.identifier,
                }
            ),
        )

    def set_time_watermark(self, open: bool) -> None:
        """set_time_watermark."""
        self._mqtt_client.publish(
            self.control_topic,
            json.dumps(
                {
                    "type": "setTimeWatermark",
                    "open": open,
                    "identifier": self.identifier,
                }
            ),
        )

    def set_anti_flicker(self, level: AntiFlickerLevel) -> None:
        """set_anti_flicker."""
        self._mqtt_client.publish(
            self.control_topic,
            json.dumps(
                {
                    "type": "setAntiFlicker",
                    "level": level,
                    "identifier": self.identifier,
                }
            ),
        )

    def set_night_vision(self, level: NightVisionLevel) -> None:
        """set_night_vision."""
        self._mqtt_client.publish(
            self.control_topic,
            json.dumps(
                {
                    "type": "setNightVision",
                    "level": level,
                    "identifier": self.identifier,
                }
            ),
        )

    def set_dark_full_color(self, open: bool) -> None:
        """set_dark_full_color."""
        self._mqtt_client.publish(
            self.control_topic,
            json.dumps(
                {
                    "type": "setDarkFullColor",
                    "open": open,
                    "identifier": self.identifier,
                }
            ),
        )

    def trigger_preset(self, target: str) -> None:
        """trigger_preset."""
        self._mqtt_client.publish(
            self.control_topic,
            json.dumps(
                {
                    "type": "triggerPreset",
                    "target": target,
                    "identifier": self.identifier,
                }
            ),
        )

    def create_preset(self, name: str) -> None:
        """create_preset."""
        self._mqtt_client.publish(
            self.control_topic,
            json.dumps(
                {
                    "type": "createPreset",
                    "name": name,
                    "identifier": self.identifier,
                }
            ),
        )

    def set_auto_upgrade(self, open: bool) -> None:
        """set_auto_upgrade."""
        self._mqtt_client.publish(
            self.control_topic,
            json.dumps(
                {
                    "type": "autoUpgrade",
                    "open": open,
                    "identifier": self.identifier,
                }
            ),
        )

    def set_cruise_open(self, open: bool) -> None:
        """set_cruise_open."""
        self._mqtt_client.publish(
            self.control_topic,
            json.dumps(
                {
                    "type": "setCruiseOpen",
                    "open": open,
                    "timestamp": int(time.time()),
                    "identifier": self.identifier,
                }
            ),
        )

    def set_human_filter(self, open: bool) -> None:
        """set_human_filter."""
        self._mqtt_client.publish(
            self.control_topic,
            json.dumps(
                {
                    "type": "setHumanFilter",
                    "open": open,
                    "timestamp": int(time.time()),
                    "identifier": self.identifier,
                }
            ),
        )

    def set_indicator_light(self, open: bool) -> None:
        """set_indicator_light."""
        self._mqtt_client.publish(
            self.control_topic,
            json.dumps(
                {
                    "type": "setIndicatorLight",
                    "open": open,
                    "timestamp": int(time.time()),
                    "identifier": self.identifier,
                }
            ),
        )

    def set_mute_record(self, open: bool) -> None:
        """set_mute_record."""
        self._mqtt_client.publish(
            self.control_topic,
            json.dumps(
                {
                    "type": "muteRecord",
                    "open": open,
                    "timestamp": int(time.time()),
                    "identifier": self.identifier,
                }
            ),
        )

    def set_sd_card_storage(self, mode: RecordMode, open: bool) -> None:
        """set_sd_card_storage."""
        self._mqtt_client.publish(
            self.control_topic,
            json.dumps(
                {
                    "type": "setSdCardStorage",
                    "mode": str(mode),
                    "record": "1" if open else "0",
                    "timestamp": int(time.time()),
                    "identifier": self.identifier,
                }
            ),
        )

    def set_intercom_way(self, intercom_way: IntercomWay) -> None:
        """set_intercom_way."""
        self._mqtt_client.publish(
            self.control_topic,
            json.dumps(
                {
                    "type": "setIntercomWay",
                    "level": intercom_way,
                    "timestamp": int(time.time()),
                    "identifier": self.identifier,
                }
            ),
        )

    def set_sensitive_level(self, level: SensitivityLevel) -> None:
        """set_sensitive_level."""
        self._mqtt_client.publish(
            self.control_topic,
            json.dumps(
                {
                    "type": "setSensitive",
                    "level": level,
                    "timestamp": int(time.time()),
                    "identifier": self.identifier,
                }
            ),
        )

    def set_sound_alarm(self, open: bool) -> None:
        """set_sound_alarm."""
        self._mqtt_client.publish(
            self.control_topic,
            json.dumps(
                {
                    "type": "soundAlarm",
                    "open": open,
                    "timestamp": int(time.time()),
                    "identifier": self.identifier,
                }
            ),
        )

    def set_volume_level(self, level: VolumeLevel) -> None:
        """set_volume_level."""
        self._mqtt_client.publish(
            self.control_topic,
            json.dumps(
                {
                    "type": "setVolumeLevel",
                    "level": level,
                    "timestamp": int(time.time()),
                    "identifier": self.identifier,
                }
            ),
        )

    def set_mobile_tracking(self, open: bool) -> None:
        """set_mobile_tracking."""
        self._mqtt_client.publish(
            self.control_topic,
            json.dumps(
                {
                    "type": "isOpenMobileTracking",
                    "open": open,
                    "timestamp": int(time.time()),
                    "identifier": self.identifier,
                }
            ),
        )

    def set_move_detection(self, open: bool) -> None:
        """set_move_detection."""
        self._mqtt_client.publish(
            self.control_topic,
            json.dumps(
                {
                    "type": "setMoveDetect",
                    "open": open,
                    "timestamp": int(time.time()),
                    "identifier": self.identifier,
                }
            ),
        )
