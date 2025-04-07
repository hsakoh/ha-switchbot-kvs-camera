"""SwitchBot Camera KVS Preset model."""


class Position:
    """Position."""

    x: int
    y: int


class KVSPreset:
    """KVS Preset."""

    id: str
    name: str
    previewUrl: str  # noqa: N815
    position: Position
    is_favorite: bool
