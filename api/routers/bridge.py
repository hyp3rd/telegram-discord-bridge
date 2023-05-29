"""Bridge controller router."""

from multiprocessing import Process

from fastapi import APIRouter

from api.models import BridgeResponse, BridgeResponseSchema
from bridge.config import Config
from bridge.telegram_handler import check_telegram_session
from bridge.enums import ProcessStateEnum
from forwarder import controller, determine_process_state


class BridgeRouter:  # pylint: disable=too-few-public-methods
    """Bridge Router."""

    def __init__(self):
        # The bridge_process variable is used to store the bridge process
        self.bridge_process = None
        self.router = APIRouter(
            prefix="/bridge",
            tags=["bridge"],
        )

        self.router.post("/",
                         name="Start the Telegram to Discord Bridge",
                         summary="Spawns the Bridge process.",
                         description="Starts the Bridge controller triggering the Telegram authentication process.",
                         response_model=BridgeResponseSchema)(self.start)

        self.router.delete("/",
                           name="Stop the Telegram to Discord Bridge",
                           summary="Removes the Bridge process.",
                           description="Suspends the Bridge forwarding messages from Telegram to Discord and stops the process.",
                           response_model=BridgeResponseSchema)(self.stop)

    async def start(self):
        """start the bridge."""
        config = Config.get_config_instance()
        pid_file = f'{config.app.name}.pid'
        _, pid = determine_process_state(pid_file)

        # if the pid file is empty and the process is None,
        # then start the bridge
        try:
            if pid == 0 and self.bridge_process is not ProcessStateEnum.RUNNING:
                self.bridge_process = Process(
                    target=controller, args=(True, False, False,))
                self.bridge_process.start()

                return BridgeResponseSchema(bridge=BridgeResponse(
                    name=config.app.name,
                    status=ProcessStateEnum.STARTING,
                    parent_process_id=self.bridge_process.pid,
                    bridge_process_id=pid,
                    config_version=config.app.version,
                    telegram_authenticated=check_telegram_session(),
                    error="",
                ))
        except Exception as ex: # pylint: disable=broad-except
            return BridgeResponseSchema(bridge=BridgeResponse(
                name=config.app.name,
                status=ProcessStateEnum.STOPPED,
                parent_process_id=self.bridge_process.pid,
                bridge_process_id=pid,
                config_version=config.app.version,
                telegram_authenticated=check_telegram_session(),
                error=str(ex),
            ))

        # if the pid file is empty and the process is not None and is alive,
        # then return that the bridge is starting
        if pid == 0 and self.bridge_process is not None and self.bridge_process.is_alive():
            return BridgeResponseSchema(bridge=BridgeResponse(
                name=config.app.name,
                status=ProcessStateEnum.ORPHANED,
                parent_process_id=self.bridge_process.pid,
                bridge_process_id=pid,
                config_version=config.app.version,
                telegram_authenticated=check_telegram_session(),
                error="",
            ))

        # otherwise return the state of the process
        return BridgeResponseSchema(bridge=BridgeResponse(
            name=config.app.name,
            status=ProcessStateEnum.RUNNING,
            parent_process_id=self.bridge_process.pid if self.bridge_process else 0,
            bridge_process_id=pid,
            config_version=config.app.version,
            telegram_authenticated=check_telegram_session(),
            error="",
        ))

    async def stop(self):
        """stop the bridge."""
        config = Config.get_config_instance()
        _, pid = determine_process_state(pid_file=f'{config.app.name}.pid')
        if self.bridge_process and self.bridge_process.is_alive():
            controller(boot=False, background=False, stop=True)
            self.bridge_process.join()
            self.bridge_process.terminate()
            return BridgeResponseSchema(bridge=BridgeResponse(
                name=config.app.name,
                status=ProcessStateEnum.STOPPING,
                parent_process_id=self.bridge_process.pid,
                bridge_process_id=pid,
                config_version=config.app.version,
                telegram_authenticated=check_telegram_session(),
                error="",
            ))
        return BridgeResponseSchema(bridge=BridgeResponse(
            name=config.app.name,
            status=ProcessStateEnum.STOPPED,
            parent_process_id=self.bridge_process.pid if self.bridge_process else 0,
            config_version=config.app.version,
            telegram_authenticated=check_telegram_session(),
            error="",
        ))


router = BridgeRouter().router
