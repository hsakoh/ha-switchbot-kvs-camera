"""Support for SwitchBot KVS Camera Selectes."""

from collections.abc import Callable
from dataclasses import dataclass
import logging

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import SwitchBotKVSCameraConfigEntry
from .api_client.api_client import Device
from .base_entity import SwitchBotKVSEntity
from .coordinator import SwitchBotKVSCameraCoordinator
from .mqtt_client.mqtt_kvs_cam import (
    AntiFlickerLevel,
    IntercomWay,
    NightVisionLevel,
    RecordMode,
    SensitivityLevel,
)

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class SelectDefinition:
    """Select definition."""

    key: str
    enum_options_func: Callable[[str, SwitchBotKVSCameraCoordinator], list[str]]
    current_option_func: Callable[
        [
            str,
            SwitchBotKVSCameraCoordinator,
        ],
        str | None,
    ]
    select_option_func: Callable[[str, SwitchBotKVSCameraCoordinator, str], None]
    icon: str | None = None


SWITCHES: list[SelectDefinition] = [
    SelectDefinition(
        key="anti_flicker",
        enum_options_func=lambda device_mac, coordinator: ["60hz", "50hz"],
        current_option_func=lambda device_mac, coordinator,: (
            "60hz"
            if coordinator.data.kvs_statuses[device_mac].antiFlicker
            == AntiFlickerLevel.L60Hz
            else "50hz"
        )
        if device_mac in coordinator.data.kvs_statuses
        else None,
        select_option_func=lambda device_mac,
        coordinator,
        value: coordinator.mqtt_kvs_cams[device_mac].set_anti_flicker(
            AntiFlickerLevel.L60Hz if value == "60hz" else AntiFlickerLevel.L50Hz
        ),
    ),
    SelectDefinition(
        key="night_vision",
        enum_options_func=lambda device_mac, coordinator: ["off", "auto", "allways_on"],
        current_option_func=lambda device_mac, coordinator,: (
            "off"
            if coordinator.data.kvs_statuses[device_mac].isOpenNightVision
            == NightVisionLevel.OFF
            else "auto"
            if coordinator.data.kvs_statuses[device_mac].isOpenNightVision
            == NightVisionLevel.AUTO
            else "allways_on"
        )
        if device_mac in coordinator.data.kvs_statuses
        else None,
        select_option_func=lambda device_mac,
        coordinator,
        value: coordinator.mqtt_kvs_cams[device_mac].set_night_vision(
            NightVisionLevel.OFF
            if value == "off"
            else NightVisionLevel.AUTO
            if value == "auto"
            else NightVisionLevel.ALLWAYS_ON
        ),
    ),
    SelectDefinition(
        key="intercom_mode",
        enum_options_func=lambda device_mac, coordinator: ["oneway", "twoway"],
        current_option_func=lambda device_mac, coordinator,: (
            "oneway"
            if coordinator.data.kvs_statuses[device_mac].isOpenSingleIntercom
            == IntercomWay.ONEWAY
            else "twoway"
        )
        if device_mac in coordinator.data.kvs_statuses
        else None,
        select_option_func=lambda device_mac,
        coordinator,
        value: coordinator.mqtt_kvs_cams[device_mac].set_intercom_way(
            IntercomWay.ONEWAY if value == "ONEWAY" else IntercomWay.TWOWAY
        ),
    ),
    SelectDefinition(
        key="sensitivity_level",
        enum_options_func=lambda device_mac, coordinator: ["low", "medium", "high"],
        current_option_func=lambda device_mac, coordinator,: (
            "low"
            if coordinator.data.kvs_statuses[device_mac].sensitivityLevel
            == SensitivityLevel.LOW
            else "medium"
            if coordinator.data.kvs_statuses[device_mac].sensitivityLevel
            == SensitivityLevel.MEDIUM
            else "high"
        )
        if device_mac in coordinator.data.kvs_statuses
        else None,
        select_option_func=lambda device_mac,
        coordinator,
        value: coordinator.mqtt_kvs_cams[device_mac].set_sensitive_level(
            SensitivityLevel.LOW
            if value == "medium"
            else SensitivityLevel.MEDIUM
            if value == "high"
            else SensitivityLevel.HIGH
        ),
    ),
    SelectDefinition(
        key="recording_mode",
        enum_options_func=lambda device_mac, coordinator: ["event", "continues"],
        current_option_func=lambda device_mac, coordinator,: (
            "event"
            if coordinator.data.kvs_statuses[device_mac].recordMode == RecordMode.EVENT
            else "continues"
        )
        if device_mac in coordinator.data.kvs_statuses
        else None,
        select_option_func=lambda device_mac, coordinator, value: (
            coordinator.mqtt_kvs_cams[device_mac].set_sd_card_storage(
                (RecordMode.EVENT if value == "event" else RecordMode.CONTINUES),
                coordinator.data.kvs_statuses[device_mac].isOpenRecord,
            )
        )
        if device_mac in coordinator.data.kvs_statuses
        else None,
    ),
    SelectDefinition(
        key="preset_list",
        enum_options_func=lambda device_mac, coordinator,: (
            [""] + [preset.name for preset in coordinator.data.kvs_presets[device_mac]]
        )
        if device_mac in coordinator.data.kvs_presets
        else None,
        current_option_func=lambda device_mac,
        coordinator,: coordinator.data.kvs_preset_selects.get(device_mac, None),
        select_option_func=lambda device_mac, coordinator, value: (
            coordinator.data.kvs_preset_selects.update({device_mac: value})
        )
        if device_mac in coordinator.data.kvs_presets
        and value != ""
        and value
        in (preset.name for preset in coordinator.data.kvs_presets[device_mac])
        else None,
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: SwitchBotKVSCameraConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Selects."""
    coordinator: SwitchBotKVSCameraCoordinator = config_entry.runtime_data.coordinator
    entities: list[SwitchBotKVSSelectEntity] = []
    for kvsCam in (
        device
        for device in coordinator.data.devices.devices
        if device.device_detail.device_type in ("WoCamKvs5mp", "WoCamKvs")
    ):
        entities.extend(
            [
                SwitchBotKVSSelectEntity(
                    coordinator=coordinator,
                    device=kvsCam,
                    select_definition=select_definition,
                )
                for select_definition in SWITCHES
            ]
        )

    async_add_entities(entities)


class SwitchBotKVSSelectEntity(SwitchBotKVSEntity, SelectEntity):
    """SwitchBot KVS Select Device."""

    def __init__(
        self,
        coordinator: SwitchBotKVSCameraCoordinator,
        device: Device,
        select_definition: SelectDefinition,
    ) -> None:
        """Init select."""
        SwitchBotKVSEntity.__init__(self, coordinator, device)
        SelectEntity.__init__(self)
        self.entity_description = SelectEntityDescription(
            key=select_definition.key,
            translation_key=select_definition.key,
            entity_category=EntityCategory.CONFIG,
        )
        self._attr_icon = select_definition.icon
        self._attr_has_entity_name = True
        self.entity_id = (
            f"select.switchbot_camera_{device.device_mac}_{select_definition.key}"
        )
        self.unique_id = (
            f"select.switchbot_camera_{device.device_mac}_{select_definition.key}"
        )
        self._attr_options = select_definition.enum_options_func(
            device.device_mac, coordinator
        )
        self.enum_options_func = select_definition.enum_options_func
        self.current_option_func = select_definition.current_option_func
        self.select_option_func = select_definition.select_option_func

    @callback
    def _handle_coordinator_update(self) -> None:
        """Update camera with latest data from coordinator."""
        self._attr_options = self.enum_options_func(
            self.device.device_mac, self.coordinator
        )
        super()._handle_coordinator_update()

    @property
    def current_option(self) -> str | None:
        """Return the selected entity option to represent the entity state."""
        return self.current_option_func(self.device.device_mac, self.coordinator)

    def select_option(self, option: str) -> None:
        """Change the selected option."""
        return self.select_option_func(self.device.device_mac, self.coordinator, option)
