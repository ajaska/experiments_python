# WS server example that synchronizes state across clients

import asyncio
import json
import logging
import websockets

logging.basicConfig(
    format="%(asctime)s %(levelname)-8s %(message)s",
    level=logging.INFO,
    datefmt="%Y-%m-%d %H:%M:%S",
)

STATE = {"leavers": set()}

USERS = set()
FINGERPRINTS = {}


async def notify_ban(user, is_banned):
    await user.send(json.dumps({"x": is_banned}))


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


async def please_dont_go(websocket, path):
    await register(websocket)
    ip_addr = None
    fingerprint = None
    try:
        ip_addr = ip_address(websocket)
        logging.info(f"{ip_addr} connected; {user_agent(websocket)}")

        if ip_addr in STATE["leavers"]:
            logging.info(f"Informing {ip_addr} of ban.")
            await notify_ban(websocket, True)

        async for message in websocket:
            logging.info(f"Message from {ip_addr} {message}")
            data = json.loads(message)

            localstorage_ban = data["lsBan"]
            fingerprint = data["fingerprint"]

            if (
                localstorage_ban
                or fingerprint in STATE["leavers"]
                or ip_addr in STATE["leavers"]
            ):
                STATE["leavers"].add(fingerprint)
                STATE["leavers"].add(ip_addr)
                logging.info(f"Informing {ip_addr} of ban.")
                await notify_ban(websocket, True)
            else:
                await notify_ban(websocket, False)
    except websockets.exceptions.ConnectionClosedError:
        logging.info(f"Client {ip_addr} disconnected")
        if any(ip_address(user) for user in USERS if user != websocket):
            return
        logging.info("Was last client. Banning.")
        STATE["leavers"].add(fingerprint)
        STATE["leavers"].add(ip_addr)
    except Exception:
        logging.exception("Fatal Error in client-handling loop")
    finally:
        logging.debug(f"Removing {ip_addr} ({fingerprint})")
        await unregister(websocket)
        remaining = ", ".join([ip_address(user) for user in USERS])
        logging.debug(f"Remaining clients: [{remaining}]")


start_server = websockets.serve(please_dont_go, "0.0.0.0", 1237)

asyncio.get_event_loop().run_until_complete(start_server)
asyncio.get_event_loop().run_forever()
