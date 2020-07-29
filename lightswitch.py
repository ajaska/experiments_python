# WS server example that synchronizes state across clients

import asyncio
import json
import logging
import websockets

logging.basicConfig()

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
        async for message in websocket:
            data = json.loads(message)
            STATE["on"] = data["on"]
            await notify_state()
    finally:
        await unregister(websocket)


start_server = websockets.serve(lightswitch, "0.0.0.0", 1235)

asyncio.get_event_loop().run_until_complete(start_server)
asyncio.get_event_loop().run_forever()
