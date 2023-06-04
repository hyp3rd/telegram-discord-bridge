"""Health Schema."""""

# from multiprocessing import Manager
# from multiprocessing.managers import SyncManager
from typing import Dict
from multiprocessing.managers import BaseManager
from pydantic import BaseModel
from bridge.enums import ProcessStateEnum
from bridge.config import Config
from bridge.logger import Logger

logger = Logger.get_logger(Config.get_config_instance().app.name)

class Health(BaseModel):
    """Health."""
    timestamp: float = 0
    process_state: ProcessStateEnum = ProcessStateEnum.UNKNOWN
    process_id: int = 0
    status: dict[str, bool] = {}


class HealthSchema(BaseModel):
    """Health Schema."""
    health: Health


class HealthHistory:
    """Health History."""

    # make this class a singleton
    def __new__(cls):
        """Create a new Health History object."""
        if not hasattr(cls, 'instance'):
            cls.instance = super(HealthHistory, cls).__new__(cls)
        return cls.instance

    def __init__(self):
        """Initialize the Health History."""
        if not hasattr(self, 'health_history'):
            self.health_history:Dict[float, Health]  = {}

    def add_health_data(self, health):
        """Add a health object to the health history."""
        logger.info('Adding health to history')
        if not isinstance(health, Health):
            logger.error('health must be a Health object')
            raise TypeError('health must be a Health object')
        if not health.timestamp > 0:
            logger.error('health timestamp must be > 0')
            raise ValueError('health timestamp must be > 0')
        self.health_history[health.timestamp] = health

    def get_health_data(self):
        """Return the last health object in the health history."""

        if not self.health_history:
            raise ValueError('No health objects in history')

        # Get the last timestamp from the history
        last_timestamp = max(self.health_history.keys()) # type: ignore

        # Get the last health object from the history
        last_health = self.health_history[last_timestamp]

        logger.info('Returning last health: %s', last_health)
        return last_health

    def get_health_history(self):
        """Return the health history."""
        return self.health_history

class HealtHistoryManager(BaseManager):
    """Health History Manager."""
