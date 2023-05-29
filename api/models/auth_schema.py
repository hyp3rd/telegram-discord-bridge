"""Auth Schema."""

from pydantic import BaseModel


class TelegramAuthSchema(BaseModel):
    """Telegram Auth Schema."""
    identity: str = ""
    password: str = ""
    code: str | int = 0


class TelegramAuthResponse(BaseModel):
    """Telegram Auth Response Schema."""
    status: str
    message: str
    error: str = ""
    session_revoked: bool = False
    mfa_required: bool = False


class TelegramAuthResponseSchema(BaseModel):
    """Telegram Auth Response Schema."""
    auth: TelegramAuthResponse
