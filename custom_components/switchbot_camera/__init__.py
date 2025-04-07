"""The SwitchBot KVSCamera integration."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntry

from .coordinator import SwitchBotKVSCameraCoordinator

_PLATFORMS: list[Platform] = [
    Platform.BUTTON,
    Platform.CAMERA,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.TEXT,
]

type SwitchBotKVSCameraConfigEntry = ConfigEntry[RuntimeData]


@dataclass
class RuntimeData:
    """Class to hold your data."""

    coordinator: SwitchBotKVSCameraCoordinator


async def async_setup_entry(
    hass: HomeAssistant, config_entry: SwitchBotKVSCameraConfigEntry
) -> bool:
    """Set up SwitchBot KVSCamera from a config entry."""

    coordinator = SwitchBotKVSCameraCoordinator(hass, config_entry)

    await coordinator.async_config_entry_first_refresh()

    config_entry.async_on_unload(
        config_entry.add_update_listener(_async_update_listener)
    )

    config_entry.runtime_data = RuntimeData(coordinator)

    await hass.config_entries.async_forward_entry_setups(config_entry, _PLATFORMS)

    return True


async def _async_update_listener(hass: HomeAssistant, config_entry):
    """Handle config options update."""
    await hass.config_entries.async_reload(config_entry.entry_id)


async def async_remove_config_entry_device(
    hass: HomeAssistant, config_entry: ConfigEntry, device_entry: DeviceEntry
) -> bool:
    """Delete device if selected from UI."""
    return True


async def async_unload_entry(
    hass: HomeAssistant, config_entry: SwitchBotKVSCameraConfigEntry
) -> bool:
    """Unload a config entry."""

    # Unload platforms and return result
    if unload_ok := await hass.config_entries.async_unload_platforms(
        config_entry, _PLATFORMS
    ):
        config_entry.runtime_data.coordinator.unload()
    return unload_ok
