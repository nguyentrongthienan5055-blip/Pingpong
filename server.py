"""
server.py -- the Pong cloud server (Part 1: accounts, friends, chat, coins).

Run this on whichever machine is going to act as "the cloud":
    python3 server.py

By default it listens on 0.0.0.0 (all network interfaces) and dynamically
reads PORT from the environment (defaulting to 8765 for local runs).
"""

import asyncio
import json
import logging
import os
import time

import websockets
import storage
import match_engine

# Bind to all network interfaces and dynamically pull the Cloud assigned PORT
HOST = "0.0.0.0"
PORT = int(os.environ.get("PORT", 8765))

WINNER_COINS = 20
LOSER_COINS = 5

log = logging.getLogger("pong_cloud")
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(message)s",
    datefmt="%H:%M:%S"
)

# username (lowercased) -> websocket connection
ONLINE = {}

# username (lowercased) -> chosen ability name for their next online match,
# set by the client via "ability_select". Defaults to NONE if never set.
PLAYER_ABILITY = {}

# username (lowercased) -> LiveMatch, for whichever match that player is
# currently in. Both usernames in a match point at the SAME LiveMatch.
ACTIVE_MATCHES = {}


class LiveMatch:
  """Server-side wrapper around one match_engine.Match: the engine itself
  knows nothing about websockets or accounts, this is what connects it to
  both."""

  def __init__(self, engine, ws1, ws2, p1_username, p2_username, p1_id, p2_id):
    self.engine = engine
    self.ws1 = ws1
    self.ws2 = ws2
    self.p1_username = p1_username
    self.p2_username = p2_username
    self.p1_id = p1_id
    self.p2_id = p2_id
    self.task = None


def _norm(username):
  return username.strip().lower()


async def send(ws, msg_type, **fields):
  try:
    await ws.send(json.dumps({"type": msg_type, **fields}))
  except websockets.ConnectionClosed:
    pass


async def send_to_username(target_username, msg_type, **fields):
  ws = ONLINE.get(_norm(target_username))
  if ws is not None:
    await send(ws, msg_type, **fields)
    return True
  return False


async def broadcast_presence(user, online):
  """Tell every currently-connected friend of `user` that their status changed."""
  for friend in storage.list_friends(user["id"]):
    await send_to_username(
        friend["username"], "presence", username=user["username"], online=online
    )


def _friends_payload(user_id):
  out = []
  for f in storage.list_friends(user_id):
    out.append({
        "username": f["username"],
        "online": _norm(f["username"]) in ONLINE,
        "status": "accepted",
    })
  for r in storage.list_incoming_requests(user_id):
    out.append({"username": r["username"], "online": False, "status": "incoming"})
  return out


async def handle_message(ws, user, data):
  """user is the logged-in account dict (already authenticated)."""
  mtype = data.get("type")

  if mtype == "friend_list":
    await send(ws, "friend_list", friends=_friends_payload(user["id"]))

  elif mtype == "friend_add":
    target_name = str(data.get("username", ""))
    target = storage.get_user_by_username(target_name)
    if target is None:
      await send(ws, "error", message="No player named '%s'." % target_name)
      return
    result = storage.send_friend_request(user["id"], target["id"])
    if result == "self":
      await send(ws, "error", message="You can't friend yourself.")
    elif result == "already_friends":
      await send(ws, "error", message="You're already friends with %s." % target["username"])
    elif result == "already_pending":
      await send(ws, "error", message="Friend request already sent.")
    else:
      await send(ws, "friend_list", friends=_friends_payload(user["id"]))
      if result == "sent":
        await send_to_username(
            target["username"], "friend_request", from_username=user["username"]
        )
      elif result == "accepted":
        await send_to_username(
            target["username"], "friend_list", friends=_friends_payload(target["id"])
        )
        await broadcast_presence(user, True)

  elif mtype == "friend_respond":
    requester_name = str(data.get("from", ""))
    requester = storage.get_user_by_username(requester_name)
    if requester is None:
      return
    accept = bool(data.get("accept"))
    if storage.respond_friend_request(user["id"], requester["id"], accept):
      await send(ws, "friend_list", friends=_friends_payload(user["id"]))
      if accept:
        await send_to_username(
            requester["username"], "friend_list", friends=_friends_payload(requester["id"])
        )
        await broadcast_presence(user, True)

  elif mtype == "chat_send":
    to_name = str(data.get("to", ""))
    body = str(data.get("body", "")).strip()[:500]
    target = storage.get_user_by_username(to_name)
    if not body:
      return
    if target is None or not storage.are_friends(user["id"], target["id"]):
      await send(ws, "error", message="You can only message friends.")
      return
    storage.save_message(user["id"], target["id"], body)
    payload = dict(
        from_username=user["username"], to=target["username"], body=body, ts=time.time()
    )
    await send(ws, "chat_message", **payload)
    await send_to_username(target["username"], "chat_message", **payload)

  elif mtype == "chat_history":
    with_name = str(data.get("with", ""))
    target = storage.get_user_by_username(with_name)
    if target is None:
      return
    rows = storage.get_history(user["id"], target["id"])
    out = [
        {
            "from_username": (
                user["username"] if r["sender_id"] == user["id"] else target["username"]
            ),
            "to": target["username"] if r["sender_id"] == user["id"] else user["username"],
            "body": r["body"],
            "ts": r["ts"],
        }
        for r in rows
    ]
    await send(ws, "chat_history", with_username=target["username"], messages=out)

  elif mtype == "coins_send":
    to_name = str(data.get("to", ""))
    amount = data.get("amount")
    target = storage.get_user_by_username(to_name)
    if target is None or not storage.are_friends(user["id"], target["id"]):
      await send(ws, "error", message="You can only send coins to friends.")
      return
    if not isinstance(amount, int) or amount <= 0:
      await send(ws, "error", message="Enter a positive whole number of coins.")
      return
    ok, reason, new_balance = storage.transfer_coins(user["id"], target["id"], amount)
    if not ok:
      reasons = {
          "insufficient_funds": "You don't have that many coins.",
          "invalid_amount": "Enter a positive whole number of coins.",
          "self": "You can't send coins to yourself.",
      }
      await send(ws, "error", message=reasons.get(reason, "Transfer failed."))
      return
    await send(ws, "coins_update", coins=new_balance)
    recipient = storage.get_user_by_id(target["id"])
    await send_to_username(target["username"], "coins_update", coins=recipient["coins"])
    await send_to_username(
        target["username"], "coins_received", from_username=user["username"], amount=amount
    )

  elif mtype == "challenge_send":
    to_name = str(data.get("to", ""))
    target = storage.get_user_by_username(to_name)
    if target is None or not storage.are_friends(user["id"], target["id"]):
      await send(ws, "error", message="You can only challenge friends.")
      return
    delivered = await send_to_username(
        target["username"], "challenge_received", from_username=user["username"]
    )
    if delivered:
      await send(ws, "info", message="Challenge sent to %s." % target["username"])
    else:
      await send(ws, "error", message="%s is offline." % target["username"])
    await send(
        ws,
        "info",
        message="(Online matches arrive in Part 2 -- for now this just notifies them.)",
    )

  else:
    await send(ws, "error", message="Unknown message type '%s'." % mtype)


async def handle_connection(ws):
  user = None
  try:
    raw = await ws.recv()
    data = json.loads(raw)
    mtype = data.get("type")
    username = str(data.get("username", "")).strip()
    password = str(data.get("password", ""))

    if mtype == "register":
      if not (3 <= len(username) <= 20) or not username.replace("_", "").isalnum():
        await send(ws, "auth_fail", reason="Username must be 3-20 letters/numbers/underscore.")
        return
      if len(password) < 4:
        await send(ws, "auth_fail", reason="Password must be at least 4 characters.")
        return
      user = storage.create_user(username, password)
      if user is None:
        await send(ws, "auth_fail", reason="That username is taken.")
        return
    elif mtype == "login":
      user = storage.verify_login(username, password)
      if user is None:
        await send(ws, "auth_fail", reason="Wrong username or password.")
        return
    else:
      await send(ws, "auth_fail", reason="Log in first.")
      return

    key = _norm(user["username"])
    old_ws = ONLINE.get(key)
    ONLINE[key] = ws
    if old_ws is not None:
      try:
        await old_ws.close(code=4000, reason="Logged in from another location")
      except Exception:
        pass
    log.info("%s connected (%d online)", user["username"], len(ONLINE))
    await send(ws, "auth_ok", user_id=user["id"], username=user["username"], coins=user["coins"])
    await send(ws, "friend_list", friends=_friends_payload(user["id"]))
    await broadcast_presence(user, True)

    async for raw in ws:
      try:
        data = json.loads(raw)
      except json.JSONDecodeError:
        continue
      user = storage.get_user_by_id(user["id"])
      await handle_message(ws, user, data)

  except websockets.ConnectionClosed:
    pass
  finally:
    if user is not None:
      key = _norm(user["username"])
      was_current = ONLINE.get(key) is ws
      if was_current:
        del ONLINE[key]
      log.info("%s disconnected (%d online)", user["username"], len(ONLINE))
      if was_current:
        await broadcast_presence(user, False)


async def main():
  storage.init_db()
  log.info("Pong cloud server listening on %s:%d", HOST, PORT)
  async with websockets.serve(
      handle_connection,
      HOST,
      PORT,
      ping_interval=20,
      ping_timeout=20,
      max_size=2**16
  ):
    await asyncio.Future()


if __name__ == "__main__":
  asyncio.run(main())
