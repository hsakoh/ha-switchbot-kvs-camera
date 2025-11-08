"""Support for SwitchBot KVS Camera Sensors."""

from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api_client.api_client import Device
from .const import DOMAIN
from .coordinator import SwitchBotKVSCameraCoordinator


class SwitchBotKVSEntity(CoordinatorEntity):
    """Base class for SwitchBot KVS entities."""

    def __init__(
        self, coordinator: SwitchBotKVSCameraCoordinator, device: Device
    ) -> None:
        """Init entity."""
        super().__init__(coordinator)
        self.coordinator = coordinator
        self.device = device
        self._attr_model = device.device_detail.device_type

    @callback
    def _handle_coordinator_update(self) -> None:
        """Update camera with latest data from coordinator."""
        self.async_write_ha_state()

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        if self.device.device_detail.device_type in ("", ""):
            byte1 = (self.device.mcu_version >> 24) & 0xFF
            byte2 = (self.device.mcu_version >> 16) & 0xFF
            byte3 = (self.device.mcu_version >> 8) & 0xFF
            byte4 = self.device.mcu_version & 0xFF
            fw_version = f"{byte1}.{byte2}.{byte3}.{byte4}"
        else:
            fw_version = None
        return DeviceInfo(
            name=self.device.device_name,
            manufacturer="SwitchBot",
            model=self.device.device_detail.device_type,
            sw_version=fw_version,
            identifiers={
                (
                    DOMAIN,
                    self.device.device_mac,
                )
            },
        )
