"""Bridge controller router."""
import asyncio
from multiprocessing import Manager, Process
from multiprocessing.managers import ListProxy

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from api.models import (BridgeResponse, BridgeResponseSchema, Health,
                        HealthHistory, HealtHistoryManager, HealthSchema)
from api.routers.health import ConnectionManager, HealthcheckSubscriber
from bridge.config import Config
from bridge.enums import ProcessStateEnum
from bridge.events import EventDispatcher
from bridge.logger import Logger
from bridge.telegram_handler import check_telegram_session
from forwarder import controller, determine_process_state

logger = Logger.get_logger(Config.get_config_instance().app.name)


class BridgeRouter:  # pylint: disable=too-few-public-methods
    """Bridge Router."""

    def __init__(self):
        # The bridge_process variable is used to store the bridge process
        self.bridge_process = None
        self.dispatcher: EventDispatcher
        HealtHistoryManager.register('HealthHistory', HealthHistory)

        self.health_history_manager_instance = HealtHistoryManager()
        self.health_history_manager_instance.start()
        self.health_history: HealthHistory = self.health_history_manager_instance.HealthHistory() # type: ignore # pylint: disable=no-member

        self.ws_connection_manager = ConnectionManager(self.health_history)

        self.bridge_router = APIRouter(
            prefix="/bridge",
            tags=["bridge"],
        )

        self.bridge_router.post("/",
                         name="Start the Telegram to Discord Bridge",
                         summary="Spawns the Bridge process.",
                         description="Starts the Bridge controller triggering the Telegram authentication process.",
                         response_model=BridgeResponseSchema)(self.start)

        self.bridge_router.delete("/",
                           name="Stop the Telegram to Discord Bridge",
                           summary="Removes the Bridge process.",
                           description="Suspends the Bridge forwarding messages from Telegram to Discord and stops the process.",
                           response_model=BridgeResponseSchema)(self.stop)
        
        self.bridge_router.get("/health",
                        name="Get the health status of the Bridge.",
                        summary="Determines the Bridge process status, the Telegram, Discord, and OpenAI connections health and returns a summary.",
                        description="Determines the Bridge process status, the Telegram, Discord, and OpenAI connections health and returns a summary.",
                        response_model=HealthSchema)(self.health)
        
        self.bridge_router.websocket("/health/ws",
                                name="Get the health status of the Bridge.")(self.health_websocket_endpoint)

    async def start(self):
        """start the bridge."""
        config = Config.get_config_instance()
        pid_file = f'{config.app.name}.pid'
        _, pid = determine_process_state(pid_file)


        try:
            # if the pid file is empty and the process is None,
            # then start the bridge
            if pid == 0 and self.bridge_process is not ProcessStateEnum.RUNNING:

                manager = Manager()
                # create a list of subscribers to pass to the event dispatcher and
                sub: ListProxy[HealthcheckSubscriber] = manager.list()
                # create the event dispatcher
                self.dispatcher = EventDispatcher(subscribers=sub)
                healthcheck_subscriber = HealthcheckSubscriber('healthcheck_subscriber', self.health_history)
                self.dispatcher.add_subscriber(healthcheck_subscriber)

                self.bridge_process = Process(
                    target=controller, args=(self.dispatcher, True, False, False,))
                self.bridge_process.start()

                return BridgeResponseSchema(bridge=BridgeResponse(
                    name=config.app.name,
                    status=ProcessStateEnum.STARTING,
                    parent_process_id=self.bridge_process.pid if self.bridge_process else 0,
                    bridge_process_id=pid,
                    config_version=config.app.version,
                    telegram_authenticated=check_telegram_session(),
                    error="",
                ))
        except Exception as ex: # pylint: disable=broad-except
            return BridgeResponseSchema(bridge=BridgeResponse(
                name=config.app.name,
                status=ProcessStateEnum.STOPPED,
                parent_process_id=self.bridge_process.pid if self.bridge_process else 0,
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
        process_state, pid = determine_process_state(pid_file=f'{config.app.name}.pid')

        if self.bridge_process and self.bridge_process.is_alive():
            if process_state == ProcessStateEnum.RUNNING and pid > 0:
                controller(dispatcher=self.dispatcher, boot=False, background=False, stop=True)


            self.bridge_process.join()
            self.bridge_process.terminate()

            return BridgeResponseSchema(bridge=BridgeResponse(
                name=config.app.name,
                status=ProcessStateEnum.STOPPING,
                parent_process_id=self.bridge_process.pid if self.bridge_process else 0,
                bridge_process_id=pid,
                config_version=config.app.version,
                telegram_authenticated=check_telegram_session(),
                error="",
            ))

        return BridgeResponseSchema(bridge=BridgeResponse(
            name=config.app.name,
            status=ProcessStateEnum.STOPPED,
            parent_process_id=self.bridge_process.pid if self.bridge_process else 0,
            bridge_process_id=pid,
            config_version=config.app.version,
            telegram_authenticated=check_telegram_session(),
            error="",
        ))

    async def health(self):
        """Return the health status of the Bridge."""
        config = Config.get_config_instance()
        pid_file = f'{config.app.name}.pid'
        process_state, pid = determine_process_state(pid_file)

        try:
            health_status = self.health_history.get_health_data()
        except ValueError:
            logger.error("Unable to retrieve the last health status.")
            return HealthSchema(
                health=Health(
                timestamp=0,
                process_state=ProcessStateEnum.UNKNOWN,
                process_id=pid,
                status={},
            )
        )

        return HealthSchema(
            health=Health(
                timestamp=health_status.timestamp,
                process_state=process_state,
                process_id=pid,
                status=health_status.status,
            )
        )

    async def health_data_sender(self, websocket: WebSocket):
        """Send health data to the WS client."""
        while True:
            await self.ws_connection_manager.send_health_data(websocket)

    async def health_websocket_endpoint(self, websocket: WebSocket):
        """Websocket endpoint."""
        await self.ws_connection_manager.connect(websocket)
        task = asyncio.create_task(self.health_data_sender(websocket))
        try:
            while True:
                _ = await websocket.receive_text()
        except WebSocketDisconnect:
            task.cancel()
            await self.ws_connection_manager.disconnect(websocket)

router = BridgeRouter().bridge_router
