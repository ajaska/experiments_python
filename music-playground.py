import asyncio
import json
import logging
import random
import websockets

logging.basicConfig(
    format="%(asctime)s %(levelname)-8s %(message)s",
    level=logging.INFO,
    datefmt="%Y-%m-%d %H:%M:%S",
)

# Board state
STATE = {}  # Opaque string from clients. Hope we don't get junk data

COLORS = ["red", "orange", "yellow", "green", "blue", "purple", "cyan", "magenta"]
# Cursor state. Maybe names in future
# { color: string; widget: string; rel_x: number (0 to 1); rel_y: number }
USER_STATE = {}

# Websockets
USERS = set()
FINGERPRINTS = {}


def state_event(model):
    return json.dumps({"type": "state", "model": model, "state": STATE[model]})


def cursor_event(user):
    cursors = [
        USER_STATE[other_user]
        for other_user in USER_STATE.keys()
        if other_user is not user
    ]
    return json.dumps({"type": "cursor", "cursors": cursors})


async def notify_state(user):
    for model in STATE.keys():
        await user.send(state_event(model))


async def notify_cursors(user):
    await user.send(cursor_event(user))


async def notify_except(user, message):
    users = [other_user for other_user in USERS if other_user is not user]
    if users:
        await asyncio.gather(*[user.send(message) for user in users])


async def register(websocket):
    USERS.add(websocket)
    USER_STATE[websocket] = {
        "widget": None,
        "rel_x": 0,
        "rel_y": 0,
        "color": random.choice(COLORS),
    }


async def unregister(websocket):
    USERS.remove(websocket)
    del USER_STATE[websocket]


def ip_address(websocket):
    remote_ip = websocket.remote_address[0]
    forwarded_for = websocket.request.headers.get("X-Forwarded-For")
    ip_addr = forwarded_for or remote_ip
    return ip_addr


def user_agent(websocket):
    return websocket.request.headers["User-Agent"]


async def music_playground(websocket):
    await register(websocket)
    ip_addr = None
    try:
        ip_addr = ip_address(websocket)
        logging.info(f"{ip_addr} connected; {user_agent(websocket)}")

        await notify_state(websocket)
        await notify_cursors(websocket)

        async for message in websocket:
            logging.info(f"Received new state from {ip_addr} {message}")

            data = json.loads(message)
            if data["type"] == "state":
                model = data["model"]
                if model in STATE and STATE[model] == data["state"]:
                    pass
                else:
                    STATE[model] = data["state"]
                    await notify_except(websocket, state_event(model))
            elif data["type"] == "sound":
                # Send it on back
                # await notify_except(websocket, message)
                pass
                # Do nothing because it's not great
            elif data["type"] == "cursor":
                USER_STATE[websocket].update(data["cursor"])
                for user in USERS:
                    if user is not websocket:
                        await notify_cursors(user)

    # Can't count on clients to disconnect gracefully; handle that code in finally
    except websockets.exceptions.ConnectionClosedError:
        pass
    except websockets.exceptions.ConnectionClosedOk:
        pass
    except Exception:
        logging.exception("Fatal Error in client-handling loop")
    finally:
        logging.info(f"Client {ip_addr} disconnected")
        await unregister(websocket)
        for user in USERS:
            await notify_cursors(websocket)


async def main():
    async with websockets.serve(music_playground, "0.0.0.0", 1238):
        await asyncio.Future()  # run forever


asyncio.run(main())
