"""Bridge controller router."""
import asyncio
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, thread
from multiprocessing import Manager, Process, Queue
from multiprocessing.managers import ListProxy
from typing import Any, List

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from api.models import (BridgeResponse, BridgeResponseSchema, Health,
                        HealthHistory, HealtHistoryManager, HealthSchema)
from api.routers.health import HealthcheckSubscriber, WSConnectionManager
from bridge.config import Config
from bridge.enums import ProcessStateEnum
from bridge.events import EventDispatcher
from bridge.logger import Logger
from bridge.telegram_handler import check_telegram_session
from forwarder import determine_process_state, run_controller

# from typing import List



logger = Logger.get_logger(Config.get_config_instance().app.name)


class BridgeRouter:  # pylint: disable=too-few-public-methods
    """Bridge Router."""

    def __init__(self):
        # The bridge_process variable is used to store the bridge process
        self.bridge_process = None
        self.dispatcher: EventDispatcher
        HealtHistoryManager.register('HealthHistory', HealthHistory)

        self.health_history_manager_instance = HealtHistoryManager()
        self.health_history_manager_instance.start() # pylint: disable=consider-using-with # the server must stay alive as long as we want the shared object to be accessible
        self.health_history: HealthHistory = self.health_history_manager_instance.HealthHistory() # type: ignore # pylint: disable=no-member

        # self.ws_connection_manager = WSConnectionManager(self.health_history)
        self.ws_connection_manager: WSConnectionManager

        self.websocket_queue = Queue()

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
                        description="Determines the Bridge process status, and the Telegram, Discord, and OpenAI connections health.",
                        response_model=HealthSchema)(self.health)

        self.bridge_router.websocket("/health/ws",
                                name="Get the health status of the Bridge.")(self.health_websocket_endpoint)

    async def start(self):
        """start the bridge."""
        config = Config.get_config_instance()
        pid_file = f'{config.app.name}.pid'
        process_state, pid = determine_process_state(pid_file)

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

            if pid == 0 or process_state not in [ProcessStateEnum.RUNNING, ProcessStateEnum.STARTING]:
                # create a shared list of subscribers
                # with ThreadPoolExecutor(max_workers=10) as executor:
                    # create a list of subscribers to pass to the event dispatcher and the healthcheck subscriber
                healthcheck_subscribers: List[HealthcheckSubscriber] = []

                self.ws_connection_manager = WSConnectionManager(self.health_history)

                # create the event dispatcher
                self.dispatcher = EventDispatcher(subscribers=healthcheck_subscribers)
                self.healthcheck_subscriber = HealthcheckSubscriber('healthcheck_subscriber',
                                                                    self.dispatcher,
                                                                    self.health_history,
                                                                    self.ws_connection_manager,
                                                                    self.websocket_queue)
                self.dispatcher.add_subscriber("healthcheck", self.healthcheck_subscriber)

                self.on_update = self.healthcheck_subscriber.create_on_update_decorator()


                asyncio.run_coroutine_threadsafe(run_controller(self.dispatcher, asyncio.get_event_loop(), True, False, False,), asyncio.get_event_loop())

                # bridge_task.running()
                # executor.submit(controller, self.dispatcher, True, False, True,)

                    # executor.map(controller, [(self.dispatcher, True, False, False,)])

                    # self.bridge_process = Process(
                    #     target=controller, args=(self.dispatcher, True, False, False,))

                    # start the bridge process
                    # self.bridge_process.start()
                    # self.bridge_process.join()

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
            logger.error("Error starting the bridge: %s", ex, exc_info=Config.get_config_instance().app.debug)
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
                await run_controller(dispatcher=self.dispatcher, boot=False, background=False, stop=True)

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
                logger.exception("Error while sending health data to the WS client: %s", exc, exc_info=Config.get_config_instance().app.debug)
                raise exc

        asyncio.run_coroutine_threadsafe(send_health_data(), asyncio.get_running_loop())


    async def health_websocket_endpoint(self, websocket: WebSocket):
        """Websocket endpoint."""
        logger.info("Connected to the websocket.")
        # self.websocket_queue.put(websocket)
        task = None
        try:
            self.ws_connection_manager.websocket_subscribers.put(websocket)
            await self.ws_connection_manager.connect(websocket)
            task = asyncio.create_task(self.health_data_sender(websocket))

            while True:
                logger.debug("Waiting for message from the client.")
                _ = await websocket.receive_text()
        except WebSocketDisconnect:
            logger.info("Disconnecting from the websocket.")
            task.cancel()
            await self.ws_connection_manager.disconnect(websocket)
        except Exception as ex: # pylint: disable=broad-except
            logger.error("Error in health_websocket_endpoint: %s", ex, exc_info=Config.get_config_instance().app.debug)
            task.cancel()
            await self.ws_connection_manager.disconnect(websocket)

router = BridgeRouter().bridge_router
