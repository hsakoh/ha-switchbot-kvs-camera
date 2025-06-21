"""Support for SwitchBot KVS Camera texts."""

from collections.abc import Callable
from dataclasses import dataclass
import logging

from homeassistant.components.text import TextEntity, TextEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import SwitchBotKVSCameraConfigEntry
from .api_client.api_client import Device
from .base_entity import SwitchBotKVSEntity
from .coordinator import SwitchBotKVSCameraCoordinator

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class TextDefinition:
    """Text definition."""

    key: str
    native_value_func: Callable[[str, SwitchBotKVSCameraCoordinator], str | None]
    set_value_func: Callable[[str, SwitchBotKVSCameraCoordinator, str], None]
    icon: str


TEXTS: list[TextDefinition] = [
    TextDefinition(
        key="create_preset_name",
        native_value_func=lambda device_mac,
        coordinator: coordinator.data.kvs_preset_texts.get(device_mac, None),
        set_value_func=lambda device_mac, coordinator, value,: (
            coordinator.data.kvs_preset_texts.update({device_mac: value})
        )
        if device_mac in coordinator.data.kvs_preset_texts
        else None,
        icon=None,
    ),
    TextDefinition(
        key="rstp_password",
        native_value_func=lambda device_mac,
        coordinator: coordinator.data.kvs_rtsp_password.get(device_mac, None),
        set_value_func=lambda device_mac, coordinator, value,: (
            coordinator.data.kvs_rtsp_password.update({device_mac: value})
        )
        if device_mac in coordinator.data.kvs_rtsp_password
        else None,
        icon=None,
    ),
    TextDefinition(
        key="rstp_user_name",
        native_value_func=lambda device_mac,
        coordinator: coordinator.data.kvs_rtsp_username.get(device_mac, None),
        set_value_func=lambda device_mac, coordinator, value,: (
            coordinator.data.kvs_rtsp_username.update({device_mac: value})
        )
        if device_mac in coordinator.data.kvs_rtsp_username
        else None,
        icon=None,
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: SwitchBotKVSCameraConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Texts."""
    coordinator: SwitchBotKVSCameraCoordinator = config_entry.runtime_data.coordinator
    entities: list[SwitchBotKVSTextEntity] = []
    for kvsCam in (
        device
        for device in coordinator.data.devices.devices
        if device.device_detail.device_type in ("WoCamKvs5mp", "WoCamKvs")
    ):
        entities.extend(
            [
                SwitchBotKVSTextEntity(
                    coordinator=coordinator,
                    device=kvsCam,
                    text_definition=text_definition,
                )
                for text_definition in TEXTS
            ]
        )

    async_add_entities(entities)


class SwitchBotKVSTextEntity(SwitchBotKVSEntity, TextEntity):
    """SwitchBot KVS Text Device."""

    def __init__(
        self,
        coordinator: SwitchBotKVSCameraCoordinator,
        device: Device,
        text_definition: TextDefinition,
    ) -> None:
        """Init text."""
        SwitchBotKVSEntity.__init__(self, coordinator, device)
        TextEntity.__init__(self)
        self.entity_description = TextEntityDescription(
            key=text_definition.key,
            translation_key=text_definition.key,
            entity_category=EntityCategory.CONFIG,
        )
        self._attr_icon = text_definition.icon
        self._attr_has_entity_name = True
        self.entity_id = (
            f"text.switchbot_camera_{device.device_mac}_{text_definition.key}"
        )
        self.unique_id = (
            f"text.switchbot_camera_{device.device_mac}_{text_definition.key}"
        )
        self.native_value_func = text_definition.native_value_func
        self.set_value_func = text_definition.set_value_func

    @property
    def native_value(self) -> str | None:
        """Return the value reported by the text."""
        return self.native_value_func(self.device.device_mac, self.coordinator)

    def set_value(self, value: str) -> None:
        """Set the text value."""
        self.set_value_func(self.device.device_mac, self.coordinator, value)
