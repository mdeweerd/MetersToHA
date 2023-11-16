#!/usr/bin/env python3
"""
This program monitors selected Home Assistant events
and calls an external program with the event name and
the event data as JSON in the second argument.

@author  https://github.com/mdeweerd
@licence https://opensource.org/license/mit/
"""
import argparse
import asyncio
import functools
import json
import logging
import os
import time
from collections import defaultdict

from aiohttp import ClientSession, WSMsgType


class EventDispatcher:
    handlers = defaultdict(list)  # type: ignore[var-annotated]

    @classmethod
    def setup(cls, event_type, callback, single=True):
        if single:
            cls.handlers[event_type] = (callback,)
        else:
            cls.handlers[event_type].append(callback)

    @classmethod
    def run_on_event(cls, event_type, *args):
        logging.debug("Run_on_event: %s", event_type)
        callback_list = cls.handlers[event_type]
        for callback in callback_list:
            asyncio.create_task(callback(*args))


async def read_config(config_path="config.json"):
    try:
        with open(config_path, encoding="utf8") as config_file:
            config = json.load(config_file)
            return config.get("ha_server"), config.get("ha_token")
    except FileNotFoundError:
        logging.error("Error: config.json file not found.")
        return None, None


async def kill_process(task):
    try:
        task.cancel()
    finally:
        logging.error("Task killed")


async def connect_to_hass(  # pylint: disable=too-many-locals
    hass_url, token, event_filter
):
    try:
        async with ClientSession() as session:
            async with session.ws_connect(f"{hass_url}/api/websocket") as ws:
                msg = await ws.receive_json()
                logging.info(f"Received {msg!r}")

                if msg.get("type") == "auth_required":
                    auth_msg = {"type": "auth", "access_token": token}
                    await ws.send_json(auth_msg)

                    msg = await ws.receive_json()

                    if msg.get("type") != "auth_ok":
                        raise Exception("Authentication failed")

                logging.info("Connected")

                process_handler = functools.partial(send_event_msg, ws)
                EventDispatcher.setup("process_done", process_handler)
                EventDispatcher.setup("process_fail", process_handler)

                msg_id: int = 1
                for event_type in event_filter:
                    # subscribe for each event type
                    subscribe_msg = {
                        "id": msg_id,
                        "type": "subscribe_events",
                        "event_type": event_type,
                    }
                    msg_id += 1
                    result = await ws.send_json(subscribe_msg)
                    logging.info(
                        "Result of subscription for '%s': %r",
                        event_type,
                        result,
                    )

                await send_event_msg(ws, "id", msg_id)

                logging.info("Subscribed, waiting for messages")

                async for msg in ws:
                    logging.info(f"Received {msg!r}")
                    if msg.type == WSMsgType.TEXT:
                        data = json.loads(msg.data)
                        if data["type"] == "event":
                            event = data["event"]
                            event_type = event["event_type"]
                            event_data = event["data"]
                            logging.info(f"Received event: {event_type}")

                            EventDispatcher.run_on_event(
                                "ha", event_type, event_data
                            )
    except Exception as e:
        logging.error(f"Error: {str(e)}")
        time.sleep(5)


async def send_event_msg(
    ws, event_type, *args
):  # pylint: disable=unused-argument
    logging.info("send_event_msg: Got %s %r", event_type, args)
    msg = None
    # TODO: call POST /api/events/<event_type> for event pylint: disable=fixme
    # https://developers.home-assistant.io/docs/api/rest/
    if event_type == "id":
        # Provides the event index
        ws.id = args[0]
    if event_type.endswith("_done"):
        pass
    elif event_type.endswith("_killed"):
        pass

    if msg is not None:
        logging.info("Send ha event %r", msg)
        # await ws.send_json(msg)


async def execute_external(
    event_name, event_data, external_program, execution_timeout
):
    try:
        logging.info("Start external program for %s", event_name)
        process = await asyncio.create_subprocess_exec(
            external_program,
            event_name,
            json.dumps(event_data),
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            # shell=False,
        )

        EventDispatcher.run_on_event("kill", kill_process, process)

        # Wait for the external process to complete or timeout
        try:
            await asyncio.wait_for(process.wait(), timeout=execution_timeout)
        except asyncio.TimeoutError:
            logging.warning(f"External process for {event_name} timed out")
            process.terminate()  # Terminate the process on timeout
            await asyncio.wait_for(
                process.wait(), timeout=5
            )  # Wait a bit for the process to terminate

        await process.wait()

        EventDispatcher.run_on_event("process_done", event_name)
    except Exception as e:
        logging.error(f"External program error: {str(e)}")
        EventDispatcher.run_on_event("process_fail", event_name)


VALID_LOGGING_LEVELS = ["debug", "info", "warning", "error"]


async def main():
    PROGRAM = os.path.basename(__file__)
    logConfig = {
        "format": f"%(asctime)s ({PROGRAM}) %(levelname)-7s %(message)s",
        "datefmt": "[%Y/%m/%d %H:%M:%S]",
    }
    logging.basicConfig(force=True, **logConfig)

    parser = argparse.ArgumentParser(
        description="Home Assistant Event Listener"
    )
    parser.add_argument("events", nargs="+", help="Events to listen to")
    parser.add_argument(
        "--config-json",
        default="./config.json",
        help="Configuration file with 'ha_server' and 'ha_token'",
    )
    parser.add_argument(
        "--log-level",
        choices=VALID_LOGGING_LEVELS,
        default="info",
        help="Logging level (error,warning,info,debug)",
    )
    parser.add_argument(
        "--timeout", type=int, default=600, help="Execution timeout in seconds"
    )
    parser.add_argument(
        "--external-program",
        required=True,
        help="Path to the external program",
    )

    args = parser.parse_args()

    logConfig["level"] = args.log_level.upper()
    logging.basicConfig(force=True, **logConfig)
    event_filter = args.events
    external_program = args.external_program
    execution_timeout = args.timeout

    hass_url, token = await read_config(args.config_json)

    try:
        EventDispatcher.setup(
            "ha",
            functools.partial(
                execute_external,
                external_program=external_program,
                execution_timeout=execution_timeout,
            ),
        )

        while True:
            await connect_to_hass(
                hass_url,
                token,
                event_filter,
            )
    except KeyboardInterrupt:
        logging.info("Terminating the program gracefully.")
    except Exception as unexpected_exception:
        logging.error("An unexpected error occurred: %s", unexpected_exception)


if __name__ == "__main__":
    asyncio.run(main())
