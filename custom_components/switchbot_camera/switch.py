"""Support for SwitchBot KVS Camera Switches."""

from collections.abc import Callable
from dataclasses import dataclass
import logging
from typing import Any

from homeassistant.components.switch import (
    SwitchDeviceClass,
    SwitchEntity,
    SwitchEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import SwitchBotKVSCameraConfigEntry
from .api_client.api_client import Device
from .base_entity import SwitchBotKVSEntity
from .coordinator import SwitchBotKVSCameraCoordinator

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class SwitchDefinition:
    """Switch definition."""

    key: str
    is_on_func: Callable[[str, SwitchBotKVSCameraCoordinator], bool]
    turn_on_func: Callable[
        [str, SwitchBotKVSCameraCoordinator],
        None,
    ]
    turn_off_func: Callable[[str, SwitchBotKVSCameraCoordinator], None]
    device_class: SwitchDeviceClass | None = None
    icon: str | None = None


SWITCHES: list[SwitchDefinition] = [
    SwitchDefinition(
        key="auto_upgrade",
        is_on_func=lambda device_mac, coordinator: coordinator.data.kvs_statuses[
            device_mac
        ].autoUpgrade
        if device_mac in coordinator.data.kvs_statuses
        else None,
        turn_on_func=lambda device_mac, coordinator: coordinator.mqtt_kvs_cams[
            device_mac
        ].set_auto_upgrade(True),
        turn_off_func=lambda device_mac, coordinator: coordinator.mqtt_kvs_cams[
            device_mac
        ].set_auto_upgrade(False),
    ),
    SwitchDefinition(
        key="cruise_mode",
        is_on_func=lambda device_mac, coordinator: coordinator.data.kvs_statuses[
            device_mac
        ].isCruiseOpen
        if device_mac in coordinator.data.kvs_statuses
        else None,
        turn_on_func=lambda device_mac, coordinator: coordinator.mqtt_kvs_cams[
            device_mac
        ].set_cruise_open(True),
        turn_off_func=lambda device_mac, coordinator: coordinator.mqtt_kvs_cams[
            device_mac
        ].set_cruise_open(False),
    ),
    SwitchDefinition(
        key="privacy_mode",
        is_on_func=lambda device_mac, coordinator: coordinator.data.kvs_statuses[
            device_mac
        ].isInPrivateMode
        if device_mac in coordinator.data.kvs_statuses
        else None,
        turn_on_func=lambda device_mac, coordinator: coordinator.mqtt_kvs_cams[
            device_mac
        ].set_privacy(True),
        turn_off_func=lambda device_mac, coordinator: coordinator.mqtt_kvs_cams[
            device_mac
        ].set_privacy(False),
    ),
    SwitchDefinition(
        key="night_full_color",
        is_on_func=lambda device_mac, coordinator: coordinator.data.kvs_statuses[
            device_mac
        ].isOpenDarkFullColor
        if device_mac in coordinator.data.kvs_statuses
        else None,
        turn_on_func=lambda device_mac, coordinator: coordinator.mqtt_kvs_cams[
            device_mac
        ].set_dark_full_color(True),
        turn_off_func=lambda device_mac, coordinator: coordinator.mqtt_kvs_cams[
            device_mac
        ].set_dark_full_color(False),
    ),
    SwitchDefinition(
        key="flipview",
        is_on_func=lambda device_mac, coordinator: coordinator.data.kvs_statuses[
            device_mac
        ].isOpenFlipScreen
        if device_mac in coordinator.data.kvs_statuses
        else None,
        turn_on_func=lambda device_mac, coordinator: coordinator.mqtt_kvs_cams[
            device_mac
        ].set_flipview(True),
        turn_off_func=lambda device_mac, coordinator: coordinator.mqtt_kvs_cams[
            device_mac
        ].set_flipview(False),
    ),
    SwitchDefinition(
        key="detect_human",
        is_on_func=lambda device_mac, coordinator: coordinator.data.kvs_statuses[
            device_mac
        ].isOpenHumamFilter
        if device_mac in coordinator.data.kvs_statuses
        else None,
        turn_on_func=lambda device_mac, coordinator: coordinator.mqtt_kvs_cams[
            device_mac
        ].set_human_filter(True),
        turn_off_func=lambda device_mac, coordinator: coordinator.mqtt_kvs_cams[
            device_mac
        ].set_human_filter(False),
    ),
    SwitchDefinition(
        key="indicator_light",
        is_on_func=lambda device_mac, coordinator: coordinator.data.kvs_statuses[
            device_mac
        ].isOpenIndicatorLight
        if device_mac in coordinator.data.kvs_statuses
        else None,
        turn_on_func=lambda device_mac, coordinator: coordinator.mqtt_kvs_cams[
            device_mac
        ].set_indicator_light(True),
        turn_off_func=lambda device_mac, coordinator: coordinator.mqtt_kvs_cams[
            device_mac
        ].set_indicator_light(False),
    ),
    SwitchDefinition(
        key="motion_tracking",
        is_on_func=lambda device_mac, coordinator: coordinator.data.kvs_statuses[
            device_mac
        ].isOpenMobileTracking
        if device_mac in coordinator.data.kvs_statuses
        else None,
        turn_on_func=lambda device_mac, coordinator: coordinator.mqtt_kvs_cams[
            device_mac
        ].set_mobile_tracking(True),
        turn_off_func=lambda device_mac, coordinator: coordinator.mqtt_kvs_cams[
            device_mac
        ].set_mobile_tracking(False),
    ),
    SwitchDefinition(
        key="motion_detection",
        is_on_func=lambda device_mac, coordinator: coordinator.data.kvs_statuses[
            device_mac
        ].isOpenMotionDetection
        if device_mac in coordinator.data.kvs_statuses
        else None,
        turn_on_func=lambda device_mac, coordinator: coordinator.mqtt_kvs_cams[
            device_mac
        ].set_move_detection(True),
        turn_off_func=lambda device_mac, coordinator: coordinator.mqtt_kvs_cams[
            device_mac
        ].set_move_detection(False),
    ),
    SwitchDefinition(
        key="local_recording",
        is_on_func=lambda device_mac, coordinator: coordinator.data.kvs_statuses[
            device_mac
        ].isOpenRecord
        if device_mac in coordinator.data.kvs_statuses
        else None,
        turn_on_func=lambda device_mac, coordinator: coordinator.mqtt_kvs_cams[
            device_mac
        ].set_sd_card_storage(
            coordinator.data.kvs_statuses[device_mac].recordMode, True
        )
        if device_mac in coordinator.data.kvs_statuses
        else None,
        turn_off_func=lambda device_mac, coordinator: coordinator.mqtt_kvs_cams[
            device_mac
        ].set_sd_card_storage(
            coordinator.data.kvs_statuses[device_mac].recordMode, False
        )
        if device_mac in coordinator.data.kvs_statuses
        else None,
    ),
    SwitchDefinition(
        key="time_watermark",
        is_on_func=lambda device_mac, coordinator: coordinator.data.kvs_statuses[
            device_mac
        ].isOpenTimeWatermark
        if device_mac in coordinator.data.kvs_statuses
        else None,
        turn_on_func=lambda device_mac, coordinator: coordinator.mqtt_kvs_cams[
            device_mac
        ].set_time_watermark(True),
        turn_off_func=lambda device_mac, coordinator: coordinator.mqtt_kvs_cams[
            device_mac
        ].set_time_watermark(False),
    ),
    SwitchDefinition(
        key="mute_recording",
        is_on_func=lambda device_mac, coordinator: coordinator.data.kvs_statuses[
            device_mac
        ].muteRecord
        if device_mac in coordinator.data.kvs_statuses
        else None,
        turn_on_func=lambda device_mac, coordinator: coordinator.mqtt_kvs_cams[
            device_mac
        ].set_mute_record(True),
        turn_off_func=lambda device_mac, coordinator: coordinator.mqtt_kvs_cams[
            device_mac
        ].set_mute_record(False),
    ),
    SwitchDefinition(
        key="rstp_open",
        is_on_func=lambda device_mac, coordinator: coordinator.data.kvs_statuses[
            device_mac
        ].rtsp["open"]
        if device_mac in coordinator.data.kvs_statuses
        else None,
        turn_on_func=lambda device_mac, coordinator: coordinator.mqtt_kvs_cams[
            device_mac
        ].set_rstp(True),
        turn_off_func=lambda device_mac, coordinator: coordinator.mqtt_kvs_cams[
            device_mac
        ].set_rstp(False),
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: SwitchBotKVSCameraConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Switches."""
    coordinator: SwitchBotKVSCameraCoordinator = config_entry.runtime_data.coordinator
    entities: list[SwitchBotKVSSwitchEntity] = []
    for kvsCam in (
        device
        for device in coordinator.data.devices.devices
        if device.device_detail.device_type in ("WoCamKvs5mp", "WoCamKvs")
    ):
        entities.extend(
            [
                SwitchBotKVSSwitchEntity(
                    coordinator=coordinator,
                    device=kvsCam,
                    switch_definition=switch_definition,
                )
                for switch_definition in SWITCHES
            ]
        )

    async_add_entities(entities)


class SwitchBotKVSSwitchEntity(SwitchBotKVSEntity, SwitchEntity):
    """SwitchBot KVS Switch Device."""

    def __init__(
        self,
        coordinator: SwitchBotKVSCameraCoordinator,
        device: Device,
        switch_definition: SwitchDefinition,
    ) -> None:
        """Init switch."""
        SwitchBotKVSEntity.__init__(self, coordinator, device)
        SwitchEntity.__init__(self)
        self.entity_description = SwitchEntityDescription(
            key=switch_definition.key,
            translation_key=switch_definition.key,
            entity_category=EntityCategory.CONFIG,
        )
        self._attr_icon = switch_definition.icon
        self._attr_has_entity_name = True
        self.entity_id = (
            f"switch.switchbot_camera_{device.device_mac}_{switch_definition.key}"
        )
        self.unique_id = (
            f"switch.switchbot_camera_{device.device_mac}_{switch_definition.key}"
        )
        self._attr_device_class = switch_definition.device_class
        self.is_on_func = switch_definition.is_on_func
        self.turn_on_func = switch_definition.turn_on_func
        self.turn_off_func = switch_definition.turn_off_func

    @property
    def is_on(self) -> bool:
        """Return true if switch is on."""
        return self.is_on_func(self.device.device_mac, self.coordinator)

    def turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        return self.turn_on_func(self.device.device_mac, self.coordinator)

    def turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        return self.turn_off_func(self.device.device_mac, self.coordinator)
