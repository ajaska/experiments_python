# WS server example that synchronizes state across clients

import asyncio
import json
import logging
import websockets

logging.basicConfig(level=logging.INFO)

STATE = {"on": False}

USERS = set()


def state_event():
    return json.dumps(STATE)


async def notify_state():
    if USERS:
        message = state_event()
        await asyncio.gather(*[user.send(message) for user in USERS])


async def register(websocket):
    USERS.add(websocket)


async def unregister(websocket):
    USERS.remove(websocket)


async def lightswitch(websocket):
    await register(websocket)
    try:
        await websocket.send(state_event())
        remote_ip = websocket.remote_address[0]
        user_agent = websocket.request.headers["User-Agent"]
        forwarded_for = websocket.request.headers["X-Forwarded-For"]
        logging.error(f"{remote_ip} {forwarded_for} connected; {user_agent}")
        async for message in websocket:
            logging.info(f"Message from {remote_ip} {forwarded_for}")
            data = json.loads(message)
            STATE["on"] = data["on"]
            await notify_state()
    finally:
        await unregister(websocket)


async def main():
    async with websockets.serve(lightswitch, "0.0.0.0", 1235):
        await asyncio.Future()  # run forever


asyncio.run(main())
