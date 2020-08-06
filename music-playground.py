import asyncio
import json
import logging
import websockets

logging.basicConfig(
    format="%(asctime)s %(levelname)-8s %(message)s",
    level=logging.INFO,
    datefmt="%Y-%m-%d %H:%M:%S",
)

STATE = {}  # Opaque string from clients. Hope we don't get junk data

USERS = set()
FINGERPRINTS = {}


def state_event(model):
    return json.dumps({"type": "state", "model": model, "state": STATE[model]})


async def notify_state(user):
    for model in STATE.keys():
        await user.send(state_event(model))


async def notify_except(user, message):
    users = [other_user for other_user in USERS if other_user is not user]
    if users:  # asyncio.wait doesn't accept an empty list
        await asyncio.wait([user.send(message) for user in users])


async def register(websocket):
    USERS.add(websocket)


async def unregister(websocket):
    USERS.remove(websocket)


def ip_address(websocket):
    remote_ip = websocket.remote_address[0]
    forwarded_for = websocket.request_headers.get("X-Forwarded-For")
    ip_addr = forwarded_for or remote_ip
    return ip_addr


def user_agent(websocket):
    return websocket.request_headers["User-Agent"]


async def music_playground(websocket, path):
    await register(websocket)
    ip_addr = None
    try:
        ip_addr = ip_address(websocket)
        logging.info(f"{ip_addr} connected; {user_agent(websocket)}")

        await notify_state(websocket)

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
                await notify_except(websocket, message)
    except websockets.exceptions.ConnectionClosedError:
        pass
    except Exception:
        logging.exception("Fatal Error in client-handling loop")
    finally:
        logging.info(f"Client {ip_addr} disconnected")
        await unregister(websocket)


start_server = websockets.serve(music_playground, "0.0.0.0", 1238)

asyncio.get_event_loop().run_until_complete(start_server)
asyncio.get_event_loop().run_forever()
