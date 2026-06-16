"""Helpers that derive the official app's two ClientId schemes exactly as the app does.

Everything is derived from ``device_id`` (= the official app's ``PhoneUtils.d()``; in this
integration it is the value sent as login body ``deviceInfo.deviceId``, which is also the
``deviceID`` claim baked into the JWT).

- **MQTT CONNECT ClientId** = ``APP_Android_{user_id}_{device_id}``
  (official app ``UserUtil.d()``; separator is "_"; device_id is used as-is, not CRC32'd)
- **KVS WebRTC identifier** = ``android_{mac}_{CRC32(device_id)}_{time}``
  (official app ``KvsCamUtils.b0()`` + ``WebRtcTool.c()`` = CRC32)

Aligning these with the device session declared at login lets the server-side presence
deliver kvsBackToApp acks (even when the official app is not running).
"""

from __future__ import annotations

import re
import time
import zlib


def normalize_device_id(raw: str) -> str:
    """Normalize the stored value (a UUID4 etc.) to the official ``PhoneUtils.d()`` 4-4-4-4 form.

    The official app's deviceId is an android_id (16 hex chars) joined with "-" every 4 chars
    (``xxxx-xxxx-xxxx-xxxx``). This integration stores ``uuid.uuid4()`` (8-4-4-4-12, 32 hex),
    so we take the first 16 hex chars and regroup them as 4-4-4-4.

    The UUID is kept as-is in config_entry (for backward compatibility with existing users);
    unifying the login body deviceId, the MQTT ClientId and the KVS identifier on this
    normalized value is what makes the server treat the session as an official-app-style device.

    Already-4-4-4-4 (16 hex) input is returned unchanged. If fewer than 16 hex chars are
    available the input is passed through unchanged (fail-safe so login never breaks).
    """
    hex_only = re.sub(r"[^0-9a-fA-F]", "", raw or "")
    if len(hex_only) < 16:
        return raw
    head16 = hex_only[:16].lower()
    return "-".join(head16[i * 4 : i * 4 + 4] for i in range(4))


def mqtt_client_id(user_id: str, device_id: str) -> str:
    """Return the MQTT CONNECT ClientId (``APP_Android_{user_id}_{device_id}``).

    Pass a ``device_id`` already normalized via :func:`normalize_device_id` so the origin
    matches the login body and the KVS identifier.
    """
    return f"APP_Android_{user_id}_{device_id}"


def crc32_hex(value: str) -> str:
    """Return upper-case 8-digit CRC32 (CRC-32/ISO-HDLC, poly 0xEDB88320), like java.util.zip.CRC32.

    Matches the official app ``WebRtcTool.c()`` = ``String.format("%08X", crc32.getValue())``.
    Example: ``crc32_hex("e6e2-c0ee-c2ad-ef93") == "7FBEABCD"``.
    """
    return f"{zlib.crc32(value.encode('utf-8')) & 0xFFFFFFFF:08X}"


def kvs_identifier(device_mac: str, device_id: str) -> str:
    """Build the KVS WebRTC identifier exactly like the official app ``KvsCamUtils.b0()``.

    Format: ``android_{mac_lower}_{CRC32(device_id) upper 8 hex}_{unix_seconds lower 8 hex}``
    (official app: ``WebRtcTool.c()`` = CRC32, trailing time as ``%08x``).

    Pass a ``device_id`` already normalized via :func:`normalize_device_id` so the CRC32 origin
    matches the login body and the MQTT ClientId.
    """
    crc = crc32_hex(device_id)
    ts_hex = f"{int(time.time()) & 0xFFFFFFFF:08x}"
    return f"android_{device_mac.lower()}_{crc}_{ts_hex}"
