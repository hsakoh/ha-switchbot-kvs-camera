"""Support for SwitchBot KVS Camera Numberes."""

from collections.abc import Callable
from dataclasses import dataclass
import logging

from homeassistant.components.number import (
    NumberEntity,
    NumberEntityDescription,
    NumberMode,
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
class NumberDefinition:
    """Number definition."""

    key: str
    native_value_func: Callable[
        [
            str,
            SwitchBotKVSCameraCoordinator,
        ],
        float | None,
    ]
    set_native_value_func: Callable[[str, SwitchBotKVSCameraCoordinator, float], None]
    icon: str | None = None
    number_mode: NumberMode
    max_value: float
    min_value: float
    step: float


NUMBERS: list[NumberDefinition] = [
    NumberDefinition(
        key="volume_level",
        min_value=0,
        max_value=10,
        step=1,
        number_mode=NumberMode.SLIDER,
        native_value_func=lambda device_mac, coordinator,: (
            int(coordinator.data.kvs_statuses[device_mac].volumeLevel)
        )
        if device_mac in coordinator.data.kvs_statuses
        else None,
        set_native_value_func=lambda device_mac,
        coordinator,
        value: coordinator.mqtt_kvs_cams[device_mac].set_volume_level(str(int(value))),
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: SwitchBotKVSCameraConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Numbers."""
    coordinator: SwitchBotKVSCameraCoordinator = config_entry.runtime_data.coordinator
    entities: list[SwitchBotKVSNumberEntity] = []
    for kvsCam in (
        device
        for device in coordinator.data.devices.devices
        if device.device_detail.device_type in ("WoCamKvs5mp", "WoCamKvs")
    ):
        entities.extend(
            [
                SwitchBotKVSNumberEntity(
                    coordinator=coordinator,
                    device=kvsCam,
                    number_definition=number_definition,
                )
                for number_definition in NUMBERS
            ]
        )

    async_add_entities(entities)


class SwitchBotKVSNumberEntity(SwitchBotKVSEntity, NumberEntity):
    """SwitchBot KVS Number Device."""

    def __init__(
        self,
        coordinator: SwitchBotKVSCameraCoordinator,
        device: Device,
        number_definition: NumberDefinition,
    ) -> None:
        """Init number."""
        SwitchBotKVSEntity.__init__(self, coordinator, device)
        NumberEntity.__init__(self)
        self.entity_description = NumberEntityDescription(
            key=number_definition.key,
            translation_key=number_definition.key,
            entity_category=EntityCategory.CONFIG,
        )
        self._attr_icon = number_definition.icon
        self._attr_has_entity_name = True
        self.entity_id = (
            f"number.switchbot_camera_{device.device_mac}_{number_definition.key}"
        )
        self.unique_id = (
            f"number.switchbot_camera_{device.device_mac}_{number_definition.key}"
        )
        self._attr_mode = number_definition.number_mode
        self._attr_native_max_value = number_definition.max_value
        self._attr_native_min_value = number_definition.min_value
        self._attr_native_step = number_definition.step
        self.native_value_func = number_definition.native_value_func
        self.set_native_value_func = number_definition.set_native_value_func

    @property
    def native_value(self) -> float | None:
        """Return the entity value to represent the entity state."""
        return self.native_value_func(self.device.device_mac, self.coordinator)

    def set_native_value(self, value: float) -> None:
        """Set new value."""
        return self.set_native_value_func(
            self.device.device_mac, self.coordinator, value
        )
