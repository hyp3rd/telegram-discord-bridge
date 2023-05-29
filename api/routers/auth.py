"""Bridge Auth Router."""
import json

from fastapi import APIRouter
from telethon.errors.rpcerrorlist import SessionPasswordNeededError, PhoneCodeInvalidError
from api.models import (TelegramAuthResponseSchema, TelegramAuthResponse,
                        TelegramAuthSchema)
from bridge.config import Config

router = APIRouter(
    prefix="/auth",
    tags=["auth"],
)


@router.post("/telegram",
             name="Telegram Auth",
             summary="Handles the Telegram authentication and authorization.",
             description="Authentication and authorization for the Telegram API including MFA and 2 steps auth.",
             response_model=TelegramAuthResponseSchema)
async def telegram_auth(auth: TelegramAuthSchema):
    """Handles the Telegram authentication and authorization."""
    config = Config.get_config_instance()

    try:
        # Temporarily write the auth data to the Telegram auth file.
        with open(config.api.telegram_auth_file, 'w', encoding="utf-8") as auth_file:
            json.dump({
                'identity': config.telegram.phone,
                'code': auth.code,
                'password': auth.password}, auth_file)
    except OSError as ex:
        return TelegramAuthResponseSchema(
            auth=TelegramAuthResponse(
                status="authentication interrupted",
                message="failed to initialize the authentication with the Telegram API.",
                error=ex.strerror
            )
        )
    except Exception as ex: # pylint: disable=broad-except
        return TelegramAuthResponseSchema(
            auth=TelegramAuthResponse(
                status="authentication interrupted",
                message="failed to initialize the authentication with the Telegram API.",
                error=str(ex)
            )
        )

    return TelegramAuthResponseSchema(
        auth=TelegramAuthResponse(
            status="authentication initiated successfully",
            message="authenticating the Telegram API with the provided credentials.",
            error=""
        )
    )
