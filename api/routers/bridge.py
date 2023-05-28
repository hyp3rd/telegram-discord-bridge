"""Bridge controller router."""

# from multiprocessing import Process

from multiprocessing import Process

from fastapi import APIRouter

from bridge.config import Config
# from bridge.enums import ProcessStateEnum
from forwarder import controller, determine_process_state

# router = APIRouter(
#     prefix="/bridge",
#     tags=["bridge"],
# )

# bridge_process: Process = None


class BridgeRouter:  # pylint: disable=too-few-public-methods
    """Bridge Router."""

    def __init__(self):
        # The bridge_process variable is used to store the bridge process
        self.bridge_process: Process = None
        self.router = APIRouter(
            prefix="/bridge",
            tags=["bridge"],
        )

        self.router.post("/",
                         name="Start the Telegram to Discord Bridge",
                         summary="Spawns the Bridge process.",
                         description="Starts the Bridge controller triggering the Telegram authentication process.",
                         response_model=None)(self.start)

        self.router.delete("/",
                           name="Stop the Telegram to Discord Bridge",
                           summary="Removes the Bridge process.",
                           description="Suspends the Bridge forwarding messages from Telegram to Discord and stops the process.",
                           response_model=None)(self.stop)

    async def start(self):
        """start the bridge."""
        config = Config.get_config_instance()
        pid_file = f'{config.app.name}.pid'
        process_state, pid = determine_process_state(pid_file)
        if pid == 0 and self.bridge_process is None:
            self.bridge_process = Process(
                target=controller, args=(True, False, False,))
            self.bridge_process.start()
            return {"operation_status": f"starting the bridge {config.app.name}, version {config.app.version}"}
        if pid == 0 and self.bridge_process is not None and self.bridge_process.is_alive():
            return {"operation_status": f"the bridge {config.app.name}, version {config.app.version} is starting"}
        return {"operation_status": f"the bridge {config.app.name}, version {config.app.version} is {process_state} (PID: {pid})"}

    async def stop(self):
        """stop the bridge."""
        config = Config.get_config_instance()
        if self.bridge_process and self.bridge_process.is_alive():
            controller(boot=False, background=False, stop=True)
            self.bridge_process.join()
            self.bridge_process = None
            return {"operation_status": f"stopping the bridge {config.app.name}"}

        return {"operation_status": f"the bridge {config.app.name} is not running"}


router = BridgeRouter().router
