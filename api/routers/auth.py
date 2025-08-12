"""Bridge Auth Router."""

import os
from fastapi import APIRouter

from api.models import (
    TelegramAuthResponse,
    TelegramAuthResponseSchema,
    TelegramAuthSchema,
)
from bridge.config import Config
from bridge.security.secret_manager import SecretManager

router = APIRouter(
    prefix="/auth",
    tags=["auth"],
)


@router.post(
    "/telegram",
    name="Telegram Auth",
    summary="Handles the Telegram authentication and authorization.",
    description="Authentication and authorization for the Telegram API including MFA and 2 steps auth.",
    response_model=TelegramAuthResponseSchema,
)
async def telegram_auth(auth: TelegramAuthSchema):
    """Handles the Telegram authentication and authorization."""
    config = Config.get_instance()

    try:
        manager = SecretManager.get_instance()
        await manager.set("identity", config.telegram.phone)
        await manager.set("code", auth.code)
        await manager.set("password", auth.password)
    except Exception as ex:  # pylint: disable=broad-except
        return TelegramAuthResponseSchema(
            auth=TelegramAuthResponse(
                status="authentication interrupted",
                message="failed to initialize the authentication with the Telegram API.",
                error=str(ex),
            )
        )

    return TelegramAuthResponseSchema(
        auth=TelegramAuthResponse(
            status="authentication initiated successfully",
            message="authenticating the Telegram API with the provided credentials.",
            error="",
        )
    )


@router.delete(
    "/telegram",
    name="Sign out from Telegram",
    summary="Clears the Telegram authentication.",
    description="Clears the Telegram authentication and session files.",
    response_model=TelegramAuthResponseSchema,
)
async def telegram_deauth():
    """Clears the Telegram authentication"""
    config = Config.get_instance()

    try:
        manager = SecretManager.get_instance()
        manager.clear("identity")
        manager.clear("code")
        manager.clear("password")

        if os.path.isfile(f"{config.application.name}.session"):
            os.remove(f"{config.application.name}.session")

        return TelegramAuthResponseSchema(
            auth=TelegramAuthResponse(
                status="success",
                message="signed out from the Telegram API successfully.",
                error="",
            )
        )

    except OSError as ex:
        return TelegramAuthResponseSchema(
            auth=TelegramAuthResponse(
                status="failed",
                message="failed to sign out from the Telegram API.",
                error=ex.strerror,
            )
        )
    except Exception as ex:  # pylint: disable=broad-except
        return TelegramAuthResponseSchema(
            auth=TelegramAuthResponse(
                status="failed",
                message="failed to sign out from the Telegram API.",
                error=str(ex),
            )
        )
