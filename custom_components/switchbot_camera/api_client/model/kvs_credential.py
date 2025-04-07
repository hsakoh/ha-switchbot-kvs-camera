"""KVS Credential."""


class KvsCredential:
    """KVS Credential."""

    def __init__(
        self,
        channels: dict[str, str],
        access: str,
        secret: str,
        token: str,
        expiration: int,
    ) -> None:
        """Initialize."""
        self.channels = channels
        self.access = access
        self.secret = secret
        self.token = token
        self.expiration = expiration
