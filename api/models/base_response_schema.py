"""Base API response schema."""

from datetime import datetime
from typing import Dict, TypeAlias

from pydantic import BaseModel  # pylint: disable=import-error
from ulid import monotonic as ulid

from bridge.enums import ProcessStateEnum, RequestTypeEnum

OperationStatus: TypeAlias = Dict[str, str]

# OperationErrors
ErrorSummary: TypeAlias = str
ErrorDetails: TypeAlias = str
OperationErrors: TypeAlias = Dict[ErrorSummary, ErrorDetails]

class BaseResponse(BaseModel):
    """Base Response."""

    resource: str
    request_id: str = ulid.from_timestamp(datetime.timestamp(datetime.now())).str
    request_type: RequestTypeEnum
    bridge_status: ProcessStateEnum = ProcessStateEnum.STOPPED
    bridge_pid: int = 0
    config_version: str = "0.0.0"
    success: bool = False
    operation_status: OperationStatus = {}
    operation_errors: OperationErrors = {}
