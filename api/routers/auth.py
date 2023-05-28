"""Bridge Auth Router."""
import json

from fastapi import APIRouter

from api.models import TelegramAuthSchema
from bridge.config import Config

router = APIRouter(
    prefix="/auth",
    tags=["auth"],
)


@router.post("/telegram",
             name="Telegram Auth",
             summary="Handles the Telegram authentication and authorization.",
             description="Authentication and authorization for the Telegram API including MFA and 2 steps auth.",
             response_model=TelegramAuthSchema)
async def telegram_auth(auth: TelegramAuthSchema):
    """Handles the Telegram authentication and authorization."""
    config = Config.get_config_instance()
    # Temporarily write the auth data to the Telegram auth file.
    with open(config.api.telegram_auth_file, 'w', encoding="utf-8") as auth_file:
        json.dump({
            'code': auth.code,
            'password': auth.password}, auth_file)
    # Return a response.
    return {"operation_status": "code received successfully"}
