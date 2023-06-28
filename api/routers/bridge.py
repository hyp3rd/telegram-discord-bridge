"""Bridge controller router."""
import asyncio
from typing import List

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from api.models import (BridgeResponse, BridgeResponseSchema, Health,
                        HealthHistory, HealtHistoryManager, HealthSchema)
from api.routers.health import HealthcheckSubscriber, WSConnectionManager
from bridge.config import Config
from bridge.enums import ProcessStateEnum
from bridge.events import EventDispatcher
from bridge.logger import Logger
from bridge.telegram import TelegramHandler
from forwarder import Forwarder, OperationStatus

# from typing import List


config = Config.get_instance()
logger = Logger.get_logger(config.application.name)


class BridgeRouter:  # pylint: disable=too-many-instance-attributes
    """Bridge Router."""

    def __init__(self):
        """Initialize the Bridge Router."""

        self.forwarder = Forwarder(event_loop=asyncio.get_running_loop())
        self.telegram_handler: TelegramHandler

        self.dispatcher: EventDispatcher
        HealtHistoryManager.register('HealthHistory', HealthHistory)

        self.health_history_manager_instance = HealtHistoryManager()
        self.health_history_manager_instance.start() # pylint: disable=consider-using-with # the server must stay alive as long as we want the shared object to be accessible
        self.health_history: HealthHistory = self.health_history_manager_instance.HealthHistory() # type: ignore # pylint: disable=no-member

        self.ws_connection_manager: WSConnectionManager

        self.bridge_router = APIRouter(
            prefix="/bridge",
            tags=["bridge"],
        )

        self.bridge_router.post("/",
                         name="Start the Telegram to Discord Bridge",
                         summary="Initiate the forwarding.",
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
                        description="Determines the Bridge process status, and the Telegram, Discord, and OpenAI connections health.",
                        response_model=HealthSchema)(self.health)

        self.bridge_router.websocket("/health/ws",
                                name="Get the health status of the Bridge.")(self.health_websocket_endpoint)

    async def start(self):
        """start the bridge."""

        process_state, pid = self.forwarder.determine_process_state()

        try:
            # if the pid file is empty and the process is None,
            # # then start the bridge
            # if pid == 0 and self.bridge_process is not ProcessStateEnum.RUNNING:
            #     # create a shared list of subscribers
            #     manager = Manager()
            #     # create a list of subscribers to pass to the event dispatcher and the healthcheck subscriber
            #     healthcheck_subscribers: ListProxy[HealthcheckSubscriber] = manager.list()

            #     self.ws_connection_manager = WSConnectionManager(self.health_history)

            #     # create the event dispatcher
            #     self.dispatcher = EventDispatcher(subscribers=healthcheck_subscribers)
            #     self.healthcheck_subscriber = HealthcheckSubscriber('healthcheck_subscriber',
            #                                                    self.dispatcher,
            #                                                    self.health_history,
            #                                                    self.ws_connection_manager,
            #                                                    self.websocket_queue)
            #     self.dispatcher.add_subscriber("healthcheck", self.healthcheck_subscriber)

            #     self.on_update = self.healthcheck_subscriber.create_on_update_decorator()

            #     self.bridge_process = Process(
            #         target=controller, args=(self.dispatcher, True, False, False,))

            #     # start the bridge process
            #     self.bridge_process.start()
            #     # self.bridge_process.join()

            if pid == 0 or process_state not in [ProcessStateEnum.RUNNING, ProcessStateEnum.STARTING, ProcessStateEnum.UNKNOWN]:
                # create a shared list of subscribers
                healthcheck_subscribers: List[HealthcheckSubscriber] = []

                self.ws_connection_manager = WSConnectionManager(self.health_history)

                # create the event dispatcher
                self.dispatcher = EventDispatcher(subscribers=healthcheck_subscribers)
                self.healthcheck_subscriber = HealthcheckSubscriber('healthcheck_subscriber',
                                                                    self.dispatcher,
                                                                    self.health_history,
                                                                    self.ws_connection_manager)
                self.dispatcher.add_subscriber("healthcheck", self.healthcheck_subscriber)

                self.on_update = self.healthcheck_subscriber.create_on_update_decorator()

                self.telegram_handler = TelegramHandler(dispatcher=self.dispatcher)

                # event_loop = asyncio.get_running_loop()

                # controller_task = asyncio.ensure_future(run_controller(self.dispatcher, event_loop, True, False, False,))

                locker = asyncio.Lock()
                await locker.acquire()
                # event_loop.create_task(run_controller(self.dispatcher, event_loop, True, False, False))
                # event_loop.create_task(self.forwarder.api_controller())
                operation_status: OperationStatus = await self.forwarder.api_controller()
                locker.release()

                logger.info("Operation status: %s", operation_status)

                return BridgeResponseSchema(bridge=BridgeResponse(
                    name=config.application.name,
                    status=operation_status[0],
                    process_id=pid,
                    config_version=config.application.version,
                    telegram_authenticated=self.telegram_handler.has_session_file(),
                    error=operation_status[1],
                ))
        except Exception as ex: # pylint: disable=broad-except
            logger.error("Error starting the bridge: %s", ex, exc_info=Config.get_instance().application.debug)
            return BridgeResponseSchema(bridge=BridgeResponse(
                name=config.application.name,
                status=ProcessStateEnum.STOPPED,
                process_id=pid,
                config_version=config.application.version,
                telegram_authenticated=self.telegram_handler.has_session_file(),
                error=str(ex),
            ))

        # if the pid file is empty and the process is not None and is alive,
        # then return that the bridge is starting
        if pid == 0 and process_state == ProcessStateEnum.RUNNING:
            return BridgeResponseSchema(bridge=BridgeResponse(
                name=config.application.name,
                status=ProcessStateEnum.ORPHANED,
                process_id=pid,
                config_version=config.application.version,
                telegram_authenticated=self.telegram_handler.has_session_file(),
                error="",
            ))

        # otherwise return the state of the process
        return BridgeResponseSchema(bridge=BridgeResponse(
            name=config.application.name,
            status=ProcessStateEnum.RUNNING,
            process_id=pid,
            config_version=config.application.version,
            telegram_authenticated=self.telegram_handler.has_session_file(),
            error="",
        ))

    async def stop(self):
        """stop the bridge."""

        process_state, pid = self.forwarder.determine_process_state()

        if process_state == ProcessStateEnum.RUNNING and pid > 0:
            try:
                # await run_controller(dispatcher=self.dispatcher, boot=False, background=False, stop=True)
                await self.forwarder.api_controller(start_forwarding=False)
                self.health_history_manager_instance.shutdown()
                self.dispatcher.stop()
            except asyncio.exceptions.CancelledError:
                logger.info("Bridge process stopped.")
            except Exception as ex: # pylint: disable=broad-except
                logger.error("Error stopping the bridge: %s", ex, exc_info=Config.get_instance().application.debug)

            return BridgeResponseSchema(bridge=BridgeResponse(
                name=config.application.name,
                status=ProcessStateEnum.STOPPING,
                process_id=pid,
                config_version=config.application.version,
                telegram_authenticated=self.telegram_handler.has_session_file(),
                error="",
            ))

        return BridgeResponseSchema(bridge=BridgeResponse(
            name=config.application.name,
            status=ProcessStateEnum.STOPPED,
            process_id=pid,
            config_version=config.application.version,
            telegram_authenticated=False,
            error="",
        ))

    async def health(self):
        """Return the health status of the Bridge."""
        if self.forwarder is not None:
            process_state, pid = self.forwarder.determine_process_state()
        else:
            process_state = ProcessStateEnum.STOPPED
            pid = 0
        try:
            health_status = self.health_history.get_health_data()
        except ValueError:
            logger.error("Unable to retrieve the last health status.")
            return HealthSchema(
                health=Health(
                process_id=pid,
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
        logger.debug("Starting health data sender.")

        @self.on_update("healthcheck")
        async def send_health_data():
            """Send health data to the WS client."""
            logger.debug("Sending health data to the WS client.")
            try:
                await self.ws_connection_manager.send_health_data(websocket)
            # pylint: disable=broad-except
            except Exception as exc:
                logger.exception("Error while sending health data to the WS client: %s", exc, exc_info=Config.get_instance().application.debug)
                raise exc


    async def health_websocket_endpoint(self, websocket: WebSocket):
        """Websocket endpoint."""
        logger.info("Connected to the websocket.")
        task = None
        try:
            await self.ws_connection_manager.connect(websocket)
            task = asyncio.create_task(self.health_data_sender(websocket))

            while True:
                logger.debug("Waiting for message from the client.")
                _ = await websocket.receive_text()
        except WebSocketDisconnect:
            logger.info("Disconnecting from the websocket.")
            if task:
                task.cancel()
            await self.ws_connection_manager.disconnect(websocket)
        except Exception as ex: # pylint: disable=broad-except
            logger.error("Error in health_websocket_endpoint: %s", ex, exc_info=Config.get_instance().application.debug)
            if task:
                task.cancel()
            await self.ws_connection_manager.disconnect(websocket)

router = BridgeRouter().bridge_router
