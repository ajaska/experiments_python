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
    if USERS:  # asyncio.wait doesn't accept an empty list
        message = state_event()
        await asyncio.wait([user.send(message) for user in USERS])


async def register(websocket):
    USERS.add(websocket)


async def unregister(websocket):
    USERS.remove(websocket)


async def lightswitch(websocket, path):
    await register(websocket)
    try:
        await websocket.send(state_event())
        remote_ip = websocket.remote_address[0]
        user_agent = websocket.request_headers["User-Agent"]
        logging.error(f"{remote_ip} connected; {user_agent}")
        async for message in websocket:
            logging.info(f"Message from {remote_ip}")
            data = json.loads(message)
            STATE["on"] = data["on"]
            await notify_state()
    finally:
        await unregister(websocket)


start_server = websockets.serve(lightswitch, "0.0.0.0", 1235)

asyncio.get_event_loop().run_until_complete(start_server)
asyncio.get_event_loop().run_forever()
