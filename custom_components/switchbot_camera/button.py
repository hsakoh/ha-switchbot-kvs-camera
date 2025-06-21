"""Support for SwitchBot KVS Camera buttons."""

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
import logging

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import SwitchBotKVSCameraConfigEntry
from .api_client.api_client import Device
from .base_entity import SwitchBotKVSEntity
from .coordinator import SwitchBotKVSCameraCoordinator
from .mqtt_client.mqtt_kvs_cam import MotorAction, MotorDirection

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class ButtonDefinition:
    """Button definition."""

    key: str
    action: Callable[
        [str, SwitchBotKVSCameraCoordinator],
        None,
    ]
    icon: str


def preset_remove(
    device_mac: str,
    coordinator: SwitchBotKVSCameraCoordinator,
) -> None:
    """Remove a preset."""
    group_id = next(
        device.groupID
        for device in coordinator.data.devices.devices
        if device_mac == device.device_mac
    )
    preset_id = next(
        preset.id
        for preset in coordinator.data.kvs_presets[device_mac]
        if preset.name == coordinator.data.kvs_preset_selects[device_mac]
    )
    preset_name = coordinator.data.kvs_preset_selects[device_mac]
    asyncio.run_coroutine_threadsafe(
        coordinator.api_client.update_kvs_preset(
            device_mac, group_id, False, preset_name, preset_id
        ),
        coordinator.hass.loop,
    )
    coordinator.reload_preset(device_mac, group_id)


BUTTONS: list[ButtonDefinition] = [
    ButtonDefinition(
        key="motor_left",
        action=lambda device_mac, coordinator: coordinator.mqtt_kvs_cams[
            device_mac
        ].motor(MotorDirection.LEFT, MotorAction.CLICK),
        icon="mdi:pan-left",
    ),
    ButtonDefinition(
        key="motor_right",
        action=lambda device_mac, coordinator: coordinator.mqtt_kvs_cams[
            device_mac
        ].motor(MotorDirection.RIGHT, MotorAction.CLICK),
        icon="mdi:pan-right",
    ),
    ButtonDefinition(
        key="motor_up",
        action=lambda device_mac, coordinator: coordinator.mqtt_kvs_cams[
            device_mac
        ].motor(MotorDirection.UP, MotorAction.CLICK),
        icon="mdi:pan-up",
    ),
    ButtonDefinition(
        key="motor_down",
        action=lambda device_mac, coordinator: coordinator.mqtt_kvs_cams[
            device_mac
        ].motor(MotorDirection.DOWN, MotorAction.CLICK),
        icon="mdi:pan-down",
    ),
    ButtonDefinition(
        key="camera_calibration",
        action=lambda device_mac, coordinator: coordinator.mqtt_kvs_cams[
            device_mac
        ].set_camera_calibration(),
        icon="mdi:camera-control",
    ),
    ButtonDefinition(
        key="preset_create",
        action=lambda device_mac, coordinator: coordinator.mqtt_kvs_cams[
            device_mac
        ].create_preset(coordinator.data.kvs_preset_texts.get(device_mac, None)),
        icon=None,
    ),
    ButtonDefinition(
        key="update_rtsp_account",
        action=lambda device_mac, coordinator: coordinator.mqtt_kvs_cams[
            device_mac
        ].update_rtsp_account(
            coordinator.data.kvs_rtsp_username.get(device_mac, None),
            coordinator.data.kvs_rtsp_password.get(device_mac, None),
        ),
        icon=None,
    ),
    ButtonDefinition(
        key="preset_move",
        action=lambda device_mac, coordinator: (
            coordinator.mqtt_kvs_cams[device_mac].trigger_preset(
                next(
                    preset.id
                    for preset in coordinator.data.kvs_presets[device_mac]
                    if preset.name == coordinator.data.kvs_preset_selects[device_mac]
                )
            )
        ),
        icon=None,
    ),
    ButtonDefinition(
        key="preset_remove",
        action=preset_remove,
        icon=None,
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: SwitchBotKVSCameraConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Buttons."""
    coordinator: SwitchBotKVSCameraCoordinator = config_entry.runtime_data.coordinator
    entities: list[SwitchBotKVSButtonEntity] = []
    for kvsCam in (
        device
        for device in coordinator.data.devices.devices
        if device.device_detail.device_type in ("WoCamKvs5mp", "WoCamKvs")
    ):
        entities.extend(
            [
                SwitchBotKVSButtonEntity(
                    coordinator=coordinator,
                    device=kvsCam,
                    button_definition=button_definition,
                )
                for button_definition in BUTTONS
            ]
        )

    async_add_entities(entities)


class SwitchBotKVSButtonEntity(SwitchBotKVSEntity, ButtonEntity):
    """SwitchBot KVS Button Device."""

    def __init__(
        self,
        coordinator: SwitchBotKVSCameraCoordinator,
        device: Device,
        button_definition: ButtonDefinition,
    ) -> None:
        """Init button."""
        SwitchBotKVSEntity.__init__(self, coordinator, device)
        ButtonEntity.__init__(self)
        self.entity_description = ButtonEntityDescription(
            key=button_definition.key,
            translation_key=button_definition.key,
            entity_category=EntityCategory.CONFIG,
        )
        self._attr_icon = button_definition.icon
        self._attr_has_entity_name = True
        self.entity_id = (
            f"button.switchbot_camera_{device.device_mac}_{button_definition.key}"
        )
        self.unique_id = (
            f"button.switchbot_camera_{device.device_mac}_{button_definition.key}"
        )
        self.action = button_definition.action

    def press(self) -> None:
        """Press the button."""
        self.action(self.device.device_mac, self.coordinator)
