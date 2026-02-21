# WS server example that synchronizes state across clients

import asyncio
import json
import logging
import websockets
import time

logging.basicConfig(
    format="%(asctime)s %(levelname)-8s %(message)s",
    level=logging.INFO,
    datefmt="%Y-%m-%d %H:%M:%S",
)

# Candle
# {
#   ip_addr: str,
#   set_at: int,
#   message: str,
# } | null

NUM_CANDLES = 20

STATE = [None for i in range(NUM_CANDLES)]
USERS = set()


def state_event():
    messages = [candle and candle["message"] for candle in STATE]
    return json.dumps(messages)


async def notify_state():
    if USERS:
        message = state_event()
        await asyncio.gather(*[user.send(message) for user in USERS])


async def register(websocket):
    USERS.add(websocket)


async def unregister(websocket):
    USERS.remove(websocket)


async def candles(websocket):
    await register(websocket)
    try:
        await websocket.send(state_event())

        remote_ip = websocket.remote_address[0]
        user_agent = websocket.request.headers["User-Agent"]
        forwarded_for = websocket.request.headers.get("X-Forwarded-For")
        logging.error(f"{remote_ip} {forwarded_for} connected; {user_agent}")

        ip_addr = forwarded_for or remote_ip

        async for message in websocket:
            logging.info(f"Message from {ip_addr}: {message}")
            data = json.loads(message)

            candle_index = data["i"]
            message = data["message"]

            if STATE[candle_index] is not None:
                if STATE[candle_index]["ip_addr"] == ip_addr:
                    if message is not None:
                        STATE[candle_index] = {
                            "ip_addr": ip_addr,
                            "set_at": int(time.time()),
                            "message": message,
                        }
                    else:
                        STATE[candle_index] = None
            else:
                for i in range(len(STATE)):
                    if STATE[i] is not None and STATE[i]["ip_addr"] == ip_addr:
                        STATE[i] = None
                if message is not None:
                    STATE[candle_index] = {
                        "ip_addr": ip_addr,
                        "set_at": int(time.time()),
                        "message": message,
                    }
                else:
                    STATE[candle_index] = None

            await notify_state()
    finally:
        await unregister(websocket)


async def unlight_old_candles():
    while True:
        now = int(time.time())
        change = False
        for i in range(len(STATE)):
            if STATE[i] is not None:
                candle = STATE[i]
                if now - candle["set_at"] > 60 * 60 * 8:  # seconds
                    logging.info(f"Unlighting old candle {json.dumps(candle)}")
                    STATE[i] = None
                    change = True
        if change:
            await notify_state()

        await asyncio.sleep(5)


async def main():
    async with websockets.serve(candles, "0.0.0.0", 1236):
        await unlight_old_candles()  # already loops forever


asyncio.run(main())
