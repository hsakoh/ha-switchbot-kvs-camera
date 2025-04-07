"""SwitchBotMqttDevice class."""

import logging

from ..api_client.model.devices import Device  # noqa: TID252
from .mqtt_client import SwitchBotMqttClient

LOGGER = logging.getLogger(__package__)

CONNECT_FAILED_NOT_AUTHORISED = 5


class MqttDevice:
    """SwitchBotMqttDevice class."""

    def __init__(
        self,
        mqtt_client: SwitchBotMqttClient,
        device: Device,
    ) -> None:
        """Initialize."""
        self._mqtt_client = mqtt_client
        self.device = device
        if self.device.device_detail.pubtopic not in [
            "",
            "no_data",
            "no_subtopic",
            "no_pubtopic",
        ]:
            self._mqtt_client.subscribe(
                self.device.device_detail.subtopic,
                self.on_message,
            )
        if self.device.device_detail.subtopic not in [
            "",
            "no_data",
            "no_subtopic",
            "no_pubtopic",
        ]:
            self._mqtt_client.subscribe(
                self.device.device_detail.subtopic,
                self.on_message,
            )

    def on_message(self, topic: str, payload: str) -> None:
        """Handle incoming messages."""
        if topic in (
            self.device.device_detail.subtopic,
            self.device.device_detail.pubtopic,
        ):
            LOGGER.debug(
                "MqttDevice %s %s receive-> %s,%s",
                self.device.device_mac,
                self.device.device_detail.device_type,
                topic,
                payload,
            )
