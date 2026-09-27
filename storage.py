"""
storage.py -- everything the Pong cloud server persists to disk.

This is the answer to "does the cloud system need to store anything?" --
yes. Two players' clients don't talk to each other directly; they both
talk to this server, and the server is the only thing that knows who
exists, who is friends with whom, and what was said. All of that lives
in one SQLite file (pong_cloud.db) next to this script. SQLite was
chosen on purpose: it's a single file, ships with Python, needs no
separate database program running, and is more than fast enough for a
friends-and-family Pong server. If this ever needs to serve thousands
of concurrent strangers, swap this module for Postgres -- nothing
outside this file would need to change, since server.py only ever
calls the functions defined here.
"""

import hashlib
import os
import secrets
import sqlite3
import time

DB_PATH = os.path.join(os.path.dirname(__file__), "pong_cloud.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  username      TEXT UNIQUE NOT NULL,
  password_hash TEXT NOT NULL,
  salt          TEXT NOT NULL,
  coins         INTEGER NOT NULL DEFAULT 100,
  created_at    REAL NOT NULL
);

-- One row per direction. A pending request is a row the *addressee*
-- hasn't accepted yet. Accepting writes the reverse row too, so a
-- friendship is just "two rows exist, both accepted" and lookups for
-- either person are a single simple query.
CREATE TABLE IF NOT EXISTS friendships (
  user_id   INTEGER NOT NULL,
  friend_id INTEGER NOT NULL,
  status    TEXT NOT NULL CHECK(status IN ('pending', 'accepted')),
  PRIMARY KEY (user_id, friend_id)
);

CREATE TABLE IF NOT EXISTS messages (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  sender_id   INTEGER NOT NULL,
  receiver_id INTEGER NOT NULL,
  body        TEXT NOT NULL,
  ts          REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS coin_transfers (
  id        INTEGER PRIMARY KEY AUTOINCREMENT,
  from_id   INTEGER NOT NULL,
  to_id     INTEGER NOT NULL,
  amount    INTEGER NOT NULL,
  ts        REAL NOT NULL
);

-- Created now so Part 2 (the synced match system) has a home for
-- results the moment it's ready; unused until then.
CREATE TABLE IF NOT EXISTS match_history (
  id         INTEGER PRIMARY KEY AUTOINCREMENT,
  p1_id      INTEGER NOT NULL,
  p2_id      INTEGER NOT NULL,
  p1_score   INTEGER NOT NULL,
  p2_score   INTEGER NOT NULL,
  winner_id  INTEGER,
  ended_at   REAL NOT NULL
);
"""


def connect():
  conn = sqlite3.connect(DB_PATH)
  conn.row_factory = sqlite3.Row
  conn.execute("PRAGMA foreign_keys = ON")
  return conn


def init_db():
  conn = connect()
  conn.executescript(SCHEMA)
  conn.commit()
  conn.close()


# --------------------------------------------------------------------
# Passwords: PBKDF2 with a per-user random salt. Stdlib-only (hashlib +
# secrets), no extra dependency, and the iteration count makes brute
# forcing a stolen DB slow without needing bcrypt/argon2 installed.
# --------------------------------------------------------------------
def _hash_password(password, salt):
  return hashlib.pbkdf2_hmac(
      "sha256", password.encode("utf-8"), bytes.fromhex(salt), 200_000
  ).hex()


def create_user(username, password):
  """Returns the new user's row dict, or None if the username is taken."""
  salt = secrets.token_hex(16)
  pw_hash = _hash_password(password, salt)
  conn = connect()
  try:
    cur = conn.execute(
        "INSERT INTO users (username, password_hash, salt, coins, created_at)"
        " VALUES (?, ?, ?, 100, ?)",
        (username, pw_hash, salt, time.time()),
    )
    conn.commit()
    return get_user_by_id(cur.lastrowid)
  except sqlite3.IntegrityError:
    return None
  finally:
    conn.close()


def verify_login(username, password):
  """Returns the user's row dict on success, else None."""
  conn = connect()
  row = conn.execute(
      "SELECT * FROM users WHERE username = ?", (username,)
  ).fetchone()
  conn.close()
  if row is None:
    return None
  if _hash_password(password, row["salt"]) != row["password_hash"]:
    return None
  return dict(row)


def get_user_by_id(user_id):
  conn = connect()
  row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
  conn.close()
  return dict(row) if row else None


def get_user_by_username(username):
  conn = connect()
  row = conn.execute(
      "SELECT * FROM users WHERE username = ?", (username,)
  ).fetchone()
  conn.close()
  return dict(row) if row else None


# --------------------------------------------------------------------
# Friends
# --------------------------------------------------------------------
def send_friend_request(user_id, friend_id):
  """Returns 'sent', 'already_friends', 'already_pending', or 'accepted'
  (if the other person had already requested you -- accept immediately,
  same as most chat apps do)."""
  if user_id == friend_id:
    return "self"
  conn = connect()
  existing = conn.execute(
      "SELECT status FROM friendships WHERE user_id=? AND friend_id=?",
      (user_id, friend_id),
  ).fetchone()
  if existing:
    conn.close()
    return "already_friends" if existing["status"] == "accepted" else "already_pending"

  reverse = conn.execute(
      "SELECT status FROM friendships WHERE user_id=? AND friend_id=?",
      (friend_id, user_id),
  ).fetchone()
  now = time.time()
  if reverse and reverse["status"] == "pending":
    # They already asked us -- auto-accept both directions.
    conn.execute(
        "UPDATE friendships SET status='accepted' WHERE user_id=? AND friend_id=?",
        (friend_id, user_id),
    )
    conn.execute(
        "INSERT INTO friendships (user_id, friend_id, status) VALUES (?, ?, 'accepted')",
        (user_id, friend_id),
    )
    conn.commit()
    conn.close()
    return "accepted"

  conn.execute(
      "INSERT INTO friendships (user_id, friend_id, status) VALUES (?, ?, 'pending')",
      (user_id, friend_id),
  )
  conn.commit()
  conn.close()
  return "sent"


def respond_friend_request(user_id, requester_id, accept):
  """user_id is responding to a request that came from requester_id."""
  conn = connect()
  row = conn.execute(
      "SELECT status FROM friendships WHERE user_id=? AND friend_id=?",
      (requester_id, user_id),
  ).fetchone()
  if not row or row["status"] != "pending":
    conn.close()
    return False
  if accept:
    conn.execute(
        "UPDATE friendships SET status='accepted' WHERE user_id=? AND friend_id=?",
        (requester_id, user_id),
    )
    conn.execute(
        "INSERT OR REPLACE INTO friendships (user_id, friend_id, status)"
        " VALUES (?, ?, 'accepted')",
        (user_id, requester_id),
    )
  else:
    conn.execute(
        "DELETE FROM friendships WHERE user_id=? AND friend_id=?",
        (requester_id, user_id),
    )
  conn.commit()
  conn.close()
  return True


def list_friends(user_id):
  """Accepted friends: [{id, username}]."""
  conn = connect()
  rows = conn.execute(
      "SELECT u.id, u.username FROM friendships f"
      " JOIN users u ON u.id = f.friend_id"
      " WHERE f.user_id = ? AND f.status = 'accepted'",
      (user_id,),
  ).fetchall()
  conn.close()
  return [dict(r) for r in rows]


def list_incoming_requests(user_id):
  """Pending requests aimed at user_id: [{id, username}]."""
  conn = connect()
  rows = conn.execute(
      "SELECT u.id, u.username FROM friendships f"
      " JOIN users u ON u.id = f.user_id"
      " WHERE f.friend_id = ? AND f.status = 'pending'",
      (user_id,),
  ).fetchall()
  conn.close()
  return [dict(r) for r in rows]


def are_friends(user_id, other_id):
  conn = connect()
  row = conn.execute(
      "SELECT 1 FROM friendships WHERE user_id=? AND friend_id=? AND status='accepted'",
      (user_id, other_id),
  ).fetchone()
  conn.close()
  return row is not None


# --------------------------------------------------------------------
# Chat -- this is the direct answer to "how does the server know two
# random players just chatted": it doesn't, unless the message passes
# through it. Every DM is relayed live to the recipient *and* written
# here, which is also what makes chat history possible after a
# reconnect.
# --------------------------------------------------------------------
def save_message(sender_id, receiver_id, body):
  conn = connect()
  cur = conn.execute(
      "INSERT INTO messages (sender_id, receiver_id, body, ts) VALUES (?, ?, ?, ?)",
      (sender_id, receiver_id, body, time.time()),
  )
  conn.commit()
  msg_id = cur.lastrowid
  conn.close()
  return msg_id


def get_history(user_a, user_b, limit=50):
  conn = connect()
  rows = conn.execute(
      "SELECT sender_id, receiver_id, body, ts FROM messages"
      " WHERE (sender_id=? AND receiver_id=?) OR (sender_id=? AND receiver_id=?)"
      " ORDER BY id DESC LIMIT ?",
      (user_a, user_b, user_b, user_a, limit),
  ).fetchall()
  conn.close()
  return [dict(r) for r in reversed(rows)]


# --------------------------------------------------------------------
# Coins -- a real transfer, not a client-editable number. The server
# owns the balance; a client can only ask "send N coins to X", and the
# server debits/credits atomically inside one transaction so a crash
# mid-transfer can't duplicate or destroy coins.
# --------------------------------------------------------------------
def transfer_coins(from_id, to_id, amount):
  """Returns (ok: bool, reason: str, new_balance: int|None)."""
  if amount <= 0:
    return False, "invalid_amount", None
  if from_id == to_id:
    return False, "self", None
  conn = connect()
  try:
    conn.execute("BEGIN IMMEDIATE")
    sender = conn.execute(
        "SELECT coins FROM users WHERE id=?", (from_id,)
    ).fetchone()
    if sender is None or sender["coins"] < amount:
      conn.execute("ROLLBACK")
      return False, "insufficient_funds", None
    conn.execute("UPDATE users SET coins = coins - ? WHERE id=?", (amount, from_id))
    conn.execute("UPDATE users SET coins = coins + ? WHERE id=?", (amount, to_id))
    conn.execute(
        "INSERT INTO coin_transfers (from_id, to_id, amount, ts) VALUES (?, ?, ?, ?)",
        (from_id, to_id, amount, time.time()),
    )
    conn.commit()
    new_balance = conn.execute(
        "SELECT coins FROM users WHERE id=?", (from_id,)
    ).fetchone()["coins"]
    return True, "ok", new_balance
  finally:
    conn.close()
