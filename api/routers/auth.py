"""Bridge Auth Router."""

import os

from fastapi import APIRouter

from api.models import (
    TelegramAuthResponse,
    TelegramAuthResponseSchema,
    TelegramAuthSchema,
)
from bridge.config import Config
from bridge.telegram.credentials import credential_store

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
    Config.get_instance()  # ensure config is loaded

    try:
        credential_store.set("code", auth.code)
        if auth.password:
            credential_store.set("password", auth.password)
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
        credential_store.clear()

        # Remove the session file.
        session_file = f"{config.application.name}.session"
        if os.path.isfile(session_file):
            os.remove(session_file)

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
