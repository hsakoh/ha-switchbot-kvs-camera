"""MqttClient class."""

import base64
from collections.abc import Callable
import gzip
import json
import logging
from pathlib import Path
import ssl
from tempfile import TemporaryDirectory
import threading
import time
from urllib.parse import urlsplit

from paho.mqtt import client as paho_mqtt_client
from paho.mqtt.client import MQTTMessage as paho_mqtt_message

LOGGER = logging.getLogger(__package__)

CONNECT_FAILED_NOT_AUTHORISED = 5


class SwitchBotMqttClient(threading.Thread):
    """MqttClient class."""

    def __init__(
        self,
        device_id: str,
        mqtt_self_signed_endpoint: str,
        mqtt_self_signed_cert_public_key_pem: str,
        mqtt_self_signed_cert_private_key_pem: str,
        subscribe_topics: list[str] | None = None,
    ) -> None:
        """Initialize."""
        super().__init__()
        self._stop_event = threading.Event()
        self.device_id = device_id
        self.mqtt_self_signed_endpoint = mqtt_self_signed_endpoint
        self.mqtt_self_signed_cert_public_key_pem = mqtt_self_signed_cert_public_key_pem
        self.mqtt_self_signed_cert_private_key_pem = (
            mqtt_self_signed_cert_private_key_pem
        )
        self._mqtt_client: paho_mqtt_client.Client | None = None
        if subscribe_topics is not None:
            self._subscribe_topics = subscribe_topics
        else:
            self._subscribe_topics = []
        self.message_listeners = set()
        self.allow_chars = bytes(
            "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz -_|;:",
            "utf-8",
        )

    def _on_disconnect(self, client, userdata, rc):
        if rc != 0:
            LOGGER.error("Unexpected disconnection. %s", rc)
        else:
            LOGGER.debug("disconnect")

    def _on_connect(
        self, mqtt_client: paho_mqtt_client.Client, user_data: any, flags, rc
    ):
        LOGGER.debug("connect flags->%s, rc->%s", flags, rc)
        if rc == 0:
            for topic in self._subscribe_topics:
                mqtt_client.subscribe(topic)

        elif rc == CONNECT_FAILED_NOT_AUTHORISED:
            self.__run_mqtt()

    def _on_message(
        self,
        mqtt_client: paho_mqtt_client.Client,
        user_data: any,
        msg: paho_mqtt_message,
    ):
        try:
            processed_payload = self.process_common_payload(msg.payload)
            if msg.topic.startswith("v1_1/") and msg.topic.endswith(
                "/all/notifyAllProperty"
            ):
                # v1_1/{user_id}/all/notifyAllProperty
                temp = json.loads(processed_payload)
                temp["messages"] = json.loads(
                    gzip.decompress(base64.b64decode(temp["messages"])).decode("utf-8")
                )
                processed_payload = json.dumps(temp, ensure_ascii=False)

            if msg.topic.startswith("switchlink/") and msg.topic.endswith(
                "/link_to_device_status"
            ):
                # switchlink/{user_id}/link_to_device_status
                temp = json.loads(processed_payload)
                if isinstance(temp["messages"], str):
                    temp["messages"] = json.loads(
                        gzip.decompress(base64.b64decode(temp["messages"])).decode(
                            "utf-8"
                        )
                    )
                    processed_payload = json.dumps(temp, ensure_ascii=False)
            LOGGER.debug("on_message: %s %s", msg.topic, processed_payload)

            for listener in self.message_listeners:
                listener(msg.topic, processed_payload)
        except Exception as ex:  # noqa: BLE001
            LOGGER.error("Error processing message: %s", ex)
            LOGGER.debug("Error processing message: %s", ex, exc_info=True)

    def _on_subscribe(
        self, mqtt_client: paho_mqtt_client.Client, user_data: any, mid, granted_qos
    ):
        LOGGER.debug("_on_subscribe: %s", mid)

    def _on_log(
        self, mqtt_client: paho_mqtt_client.Client, user_data: any, level, string
    ):
        LOGGER.debug("_on_log: %s", string)

    def run(self):
        """Run mqtt client."""
        backoff_seconds = 1
        while not self._stop_event.is_set():
            try:
                self.__run_mqtt()
                backoff_seconds = 1

                # reconnect every 2 hours required.
                if self._stop_event.wait(60 * 60 * 2 - 60):
                    break
            except Exception:
                LOGGER.exception("Failed to refresh mqtt server")
                LOGGER.error(
                    "Failed to refresh mqtt server, retrying in %s seconds",
                    backoff_seconds,
                )

                time.sleep(backoff_seconds)
                backoff_seconds = min(
                    backoff_seconds * 2, 60
                )  # Try at most every 60 seconds to refresh
        LOGGER.debug("run complete")

    def __run_mqtt(self):
        LOGGER.debug("connecting")
        new_mqtt_client = self._start()

        if self._mqtt_client:
            self._mqtt_client.disconnect()
        self._mqtt_client = new_mqtt_client

    def _start(self) -> paho_mqtt_client.Client:
        client = paho_mqtt_client.Client(client_id=self.device_id)
        with TemporaryDirectory() as temp_dir:
            with Path.open(f"{temp_dir}/cert.pem", mode="wb") as cert_file:  # pylint: disable=unspecified-encoding
                cert_file.write(
                    base64.b64decode(self.mqtt_self_signed_cert_public_key_pem)
                )
            with Path.open(f"{temp_dir}/key.pem", mode="wb") as key_file:  # pylint: disable=unspecified-encoding
                key_file.write(
                    base64.b64decode(self.mqtt_self_signed_cert_private_key_pem)
                )

            # ssl_context = ssl.create_no_verify_ssl_context()
            ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
            ssl_context.check_hostname = False
            ssl_context.options |= ssl.OP_NO_COMPRESSION
            ssl_context.verify_mode = ssl.CERT_NONE

            ssl_context.load_cert_chain(cert_file.name, key_file.name)
        client.on_connect = self._on_connect
        client.on_disconnect = self._on_disconnect
        client.on_message = self._on_message
        client.on_subscribe = self._on_subscribe
        client.on_log = self._on_log

        client.tls_set_context(ssl_context)
        url = urlsplit(self.mqtt_self_signed_endpoint)
        client.connect(url.hostname, url.port)

        client.loop_start()
        return client

    def start(self):
        """Start mqtt.

        Start mqtt thread
        """
        LOGGER.debug("start")
        super().start()

    def stop(self):
        """Stop mqtt.

        Stop mqtt thread
        """
        LOGGER.debug("stop")
        self.message_listeners = set()
        try:
            self._mqtt_client.disconnect()
        except Exception:
            LOGGER.exception("Mqtt disconnect error")
        self._mqtt_client = None
        self._stop_event.set()

    def is_connected(self) -> bool:
        """Check if mqtt is connected."""
        if self._mqtt_client is None:
            return False
        return self._mqtt_client.is_connected()

    def subscribe(self, topic: str, listener: Callable[[str, str], None]):
        """Subscribe to a topic."""

        if topic not in self._subscribe_topics:
            self._subscribe_topics.append(topic)
            self._mqtt_client.subscribe(topic)
        self.message_listeners.add(listener)

    def unsubscribe(self, topic: str, listener: Callable[[str, str], None]):
        """Unsubscribe from a topic."""
        if topic in self._subscribe_topics:
            self._subscribe_topics.remove(topic)
            self._mqtt_client.unsubscribe(topic)
        self.message_listeners.discard(listener)

    def publish(self, topic: str, payload: str):
        """Publish to a topic."""
        self._mqtt_client.publish(topic, payload)

    def process_common_payload(self, payload: bytes) -> str:
        """Process payload."""
        if len(payload) == 0:
            return ""

        if len(payload) > 1 and payload[0] == ord("{") and payload[-1] == ord("}"):
            # json
            json_object = json.loads(bytes(payload).decode("utf-8"))
            return json.dumps(json_object, ensure_ascii=False)

        if all(b in self.allow_chars for b in payload):
            return bytes(payload).decode("utf-8")

        try:
            index = payload.index(ord(" "), payload.index(ord(" ")) + 1)
            return f"{bytes(payload[:index]).decode('utf-8')} HEX({bytes(payload[index:]).hex().upper()})"
        except ValueError:
            return f"HEX({bytes(payload).hex().upper()})"
