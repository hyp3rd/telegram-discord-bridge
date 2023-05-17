"""the bridge config schema."""

try:
    from .config_schema import ConfigSchema
    from .telagram_mfa_payload import MFACodePayload
except ImportError as ex:
    raise ex
