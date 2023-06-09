"""Request Type Enum"""

from enum import Enum


class RequestTypeEnum(str, Enum):
    """Request Type Enum."""
    START = "start"
    STOP = "stop"
    RELOAD = "reload"
    UPLOAD_CONFIG = "upload_config"
    POST_CONFIG = "post_config"
    CHANGE_CONFIG_VERSION = "change_config_version"
