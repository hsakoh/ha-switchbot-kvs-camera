"""switchbot_camera exceptions."""


class ApiError(Exception):
    """Base exception for device errors."""


class MfaRequired(Exception):  # noqa: N818
    """Raised when the account has two-factor auth enabled.

    Carries the ``mfa_token`` returned by the login endpoint, which is needed to
    request and verify the second-factor code.
    """

    def __init__(self, mfa_token: str) -> None:
        """Initialize with the login-issued mfa_token."""
        super().__init__("Two-factor authentication is required.")
        self.mfa_token = mfa_token


class MfaTokenExpired(ApiError):
    """Raised when the mfa_token has expired (statusCode 2007) and login must restart."""
