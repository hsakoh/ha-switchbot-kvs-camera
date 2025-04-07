"""Support for SwitchBot KVS Camera Sensors."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
import logging

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType

from . import SwitchBotKVSCameraConfigEntry
from .api_client.api_client import Device
from .base_entity import SwitchBotKVSEntity
from .coordinator import SwitchBotKVSCameraCoordinator

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class SensorDefinition:
    """Sensor definition."""

    key: str
    native_value_func: Callable[
        [str, SwitchBotKVSCameraCoordinator], StateType | date | datetime | Decimal
    ]
    device_class: SensorDeviceClass | None = None
    state_class: SensorStateClass | None = None
    icon: str | None = None


SENSORS: list[SensorDefinition] = [
    SensorDefinition(
        key="ip_address",
        native_value_func=lambda device_mac,
        coordinator: coordinator.data.kvs_wifi_infos[device_mac].ipAddress
        if device_mac in coordinator.data.kvs_wifi_infos
        else None,
        icon="mdi:ip",
    ),
    SensorDefinition(
        key="wifi_signal",
        native_value_func=lambda device_mac,
        coordinator: coordinator.data.kvs_wifi_infos[device_mac].wifiSignal
        if device_mac in coordinator.data.kvs_wifi_infos
        else None,
        icon="mdi:wifi",
    ),
    SensorDefinition(
        key="wifi_name",
        native_value_func=lambda device_mac,
        coordinator: coordinator.data.kvs_wifi_infos[device_mac].wifiName
        if device_mac in coordinator.data.kvs_wifi_infos
        else None,
        icon="mdi:wifi",
    ),
    SensorDefinition(
        key="sd_free",
        native_value_func=lambda device_mac,
        coordinator: coordinator.data.kvs_sd_card_capacities[device_mac].free
        if device_mac in coordinator.data.kvs_sd_card_capacities
        else None,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:micro-sd",
    ),
    SensorDefinition(
        key="sd_total",
        native_value_func=lambda device_mac,
        coordinator: coordinator.data.kvs_sd_card_capacities[device_mac].total
        if device_mac in coordinator.data.kvs_sd_card_capacities
        else None,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:micro-sd",
    ),
    SensorDefinition(
        key="sd_used",
        native_value_func=lambda device_mac,
        coordinator: coordinator.data.kvs_sd_card_capacities[device_mac].used
        if device_mac in coordinator.data.kvs_sd_card_capacities
        else None,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:micro-sd",
    ),
    SensorDefinition(
        key="time_zone_id",
        native_value_func=lambda device_mac, coordinator: coordinator.data.kvs_statuses[
            device_mac
        ].timeZoneID
        if device_mac in coordinator.data.kvs_statuses
        else None,
    ),
    SensorDefinition(
        key="time_zone_posix",
        native_value_func=lambda device_mac, coordinator: coordinator.data.kvs_statuses[
            device_mac
        ].timeZonePosix
        if device_mac in coordinator.data.kvs_statuses
        else None,
    ),
    SensorDefinition(
        key="lastupdate",
        native_value_func=lambda device_mac, coordinator: datetime.fromtimestamp(
            coordinator.data.kvs_statuses[device_mac].timestamp, tz=UTC
        )
        if device_mac in coordinator.data.kvs_statuses
        else None,
        device_class=SensorDeviceClass.TIMESTAMP,
    ),
    SensorDefinition(
        key="device_mac",
        native_value_func=lambda device_mac, data: device_mac,
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: SwitchBotKVSCameraConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Sensors."""
    coordinator: SwitchBotKVSCameraCoordinator = config_entry.runtime_data.coordinator
    entities: list[SwitchBotKVSSensorEntity] = []
    for kvsCam in (
        device
        for device in coordinator.data.devices.devices
        if device.device_detail.device_type in ("WoCamKvs5mp", "WoCamKvs")
    ):
        entities.extend(
            [
                SwitchBotKVSSensorEntity(
                    coordinator=coordinator,
                    device=kvsCam,
                    sensor_definition=sensor_definition,
                )
                for sensor_definition in SENSORS
            ]
        )

    async_add_entities(entities)


class SwitchBotKVSSensorEntity(SwitchBotKVSEntity, SensorEntity):
    """SwitchBot KVS Sensor Device."""

    def __init__(
        self,
        coordinator: SwitchBotKVSCameraCoordinator,
        device: Device,
        sensor_definition: SensorDefinition,
    ) -> None:
        """Init sensor."""
        SwitchBotKVSEntity.__init__(self, coordinator, device)
        SensorEntity.__init__(self)
        self.entity_description = SensorEntityDescription(
            key=sensor_definition.key,
            translation_key=sensor_definition.key,
            entity_category=EntityCategory.DIAGNOSTIC,
        )
        self._attr_icon = sensor_definition.icon
        self._attr_has_entity_name = True
        self.entity_id = (
            f"sensor.switchbot_camera_{device.device_mac}_{sensor_definition.key}"
        )
        self.unique_id = (
            f"sensor.switchbot_camera_{device.device_mac}_{sensor_definition.key}"
        )
        self._attr_device_class = sensor_definition.device_class
        self._attr_state_class = sensor_definition.state_class
        self.native_value_func = sensor_definition.native_value_func

    @property
    def native_value(self) -> StateType | date | datetime | Decimal:
        """Return the state of the entity."""
        return self.native_value_func(self.device.device_mac, self.coordinator)
