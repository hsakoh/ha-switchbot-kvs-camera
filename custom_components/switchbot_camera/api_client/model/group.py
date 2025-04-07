"""Group model."""


class Room:
    """Room."""

    roomID: str  # noqa: N815
    roomName: str  # noqa: N815


class Member:
    """Member."""

    identity: str
    userName: str  # noqa: N815
    userID: str  # noqa: N815
    email: str
    itemID: str | None = None  # noqa: N815
    inviteCode: str | None = None  # noqa: N815
    alias: str | None = None
    confirmTime: int | None = None  # noqa: N815
    inviteTime: int | None = None  # noqa: N815
    status: int | None = None


class Group:
    """Group."""

    userID: str  # noqa: N815
    homeID: int  # noqa: N815
    groupID: str | None  # noqa: N815
    groupName: str  # noqa: N815
    rooms: list[Room]
    isShared: bool  # noqa: N815
    alias: str
    ownerUserName: str  # noqa: N815
    ownerUserID: str  # noqa: N815
    members: list[Member]
