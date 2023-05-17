"""Telegram MFA payload."""
from pydantic import (BaseModel, Field,  # pylint: disable=import-error
                      validator)


class MFACodePayload(BaseModel):  # pylint: disable=too-few-public-methods
    """Code payload."""
    code: str = Field(...)

    @classmethod
    @validator('code')
    def validate_code(cls, value):
        """Validate code."""
        if not value.isnumeric():
            raise ValueError('code must be numeric')
        return value
