"""Devices."""

from __future__ import annotations


class DeviceDetail:
    """DeviceDetail."""

    device_type: str
    isEncrypted: bool  # noqa: N815
    parent_device: str
    pubtopic: str
    remote: str
    subtopic: str
    support_cmd: list[str]
    update_time: str
    version: str
    wifi_mac: str
    awsRegion: str | None = None  # noqa: N815
    bucket: str | None = None
    channelARN: str | None = None  # noqa: N815
    clientID: str | None = None  # noqa: N815
    ip: str | None = None
    model: str | None = None
    region: str | None = None
    streamName: str | None = None  # noqa: N815
    timeZoneID: str | None = None  # noqa: N815
    deviceRegion: str | None = None  # noqa: N815


class Device:
    """Device."""

    ble_version: int
    cloudServiceAble: bool  # noqa: N815
    device_detail: DeviceDetail
    device_mac: str
    device_name: str
    groupID: str | None  # noqa: N815
    roomID: str  # noqa: N815
    userID: str  # noqa: N815
    user_name: str
    hardware_version: int | None = None
    isGroup: bool | None = None  # noqa: N815
    isMaster: bool | None = None  # noqa: N815
    isShared: bool | None = None  # noqa: N815
    platforms: list[str] | None = None
    cpu_version: int | None = None
    mcu_version: int | None = None
    wifi_version: int | None = None
    hasBattery: bool | None = None  # noqa: N815
    icon: str | None = None
    netConfigAble: bool | None = None  # noqa: N815
    usageTag: str | None = None  # noqa: N815


class Remote:
    """Remote."""

    userID: str  # noqa: N815
    userName: str  # noqa: N815
    groupID: str  # noqa: N815
    roomID: str  # noqa: N815
    remoteID: str  # noqa: N815
    remoteName: str  # noqa: N815
    type_: int
    isShared: bool  # noqa: N815
    ownerUserName: str  # noqa: N815
    ownerUserID: str  # noqa: N815
    parentHubMac: str  # noqa: N815
    codeType: str  # noqa: N815


class Devices:
    """Devices."""

    devices: list[Device]
    remotes: list[Remote]

    def __init__(
        self,
        devices: list[Device],
        remotes: list[Remote],
    ) -> None:
        """Initialize."""
        self.devices = devices
        self.remotes = remotes
