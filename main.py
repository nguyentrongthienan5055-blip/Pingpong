import json
import math
import os
import random
import sys
import pygame
from ball import Ball
from player_one import PlayerOne
from player_two import PlayerTwo
from net_client import NetClient

pygame.init()
pygame.mixer.init()

MUSIC_VOLUME = 0.4
try:
  pygame.mixer.music.load("muscic/battle_music.mp3")
  pygame.mixer.music.set_volume(MUSIC_VOLUME)
  pygame.mixer.music.play(-1)
except pygame.error:
  try:
    pygame.mixer.music.load("music/battle_music.mp3")
    pygame.mixer.music.set_volume(MUSIC_VOLUME)
    pygame.mixer.music.play(-1)
  except pygame.error:
    print("Note: Background music file not found. Running without music.")

WIDTH, HEIGHT = 1000, 600

# --- SAVE & ECONOMY SYSTEM ---
SAVE_FILE = "pong_save.json"
MAP_FILE = "custom_map.json"
save_data = {
    "coins": 0,
    "show_fps": True,
    "fullscreen": False,
    "volume": 40,
    "target_fps": 240,
    "vsync": True,       # Hardware VSync for native monitor refresh rate matching
    "p1_upgrades": {"speed": 0, "cd": 0, "size": 0, "mult": 0},
    "p2_upgrades": {"speed": 0, "cd": 0, "size": 0},
}


def load_save():
  global save_data, MUSIC_VOLUME
  if os.path.exists(SAVE_FILE):
    try:
      with open(SAVE_FILE, "r") as f:
        loaded = json.load(f)
        save_data["coins"] = loaded.get("coins", 0)
        save_data["show_fps"] = loaded.get("show_fps", True)
        save_data["fullscreen"] = loaded.get("fullscreen", False)
        save_data["volume"] = loaded.get("volume", 40)
        save_data["target_fps"] = loaded.get("target_fps", 240)
        save_data["vsync"] = loaded.get("vsync", True)
        if "upgrades" in loaded:
          save_data["p1_upgrades"].update(loaded["upgrades"])
        if "p1_upgrades" in loaded:
          save_data["p1_upgrades"].update(loaded["p1_upgrades"])
        if "p2_upgrades" in loaded:
          save_data["p2_upgrades"].update(loaded["p2_upgrades"])
        
        MUSIC_VOLUME = save_data["volume"] / 100.0
        pygame.mixer.music.set_volume(MUSIC_VOLUME)
    except:
      print("Save file corrupted, creating new.")


def write_save():
  with open(SAVE_FILE, "w") as f:
    json.dump(save_data, f, indent=4)


load_save()


def create_window():
  flags = pygame.FULLSCREEN if save_data["fullscreen"] else 0
  try:
    return pygame.display.set_mode((WIDTH, HEIGHT), flags, vsync=1 if save_data["vsync"] else 0)
  except TypeError:
    return pygame.display.set_mode((WIDTH, HEIGHT), flags)


screen = create_window()
pygame.display.set_caption("ULTIMATE CHAOS PONG : MAP EDITOR & BATTLE EDITION")
clock = pygame.time.Clock()

COLOR_BLUE = (74, 189, 214)
COLOR_RED = (255, 74, 74)
COLOR_WHITE = (255, 255, 255)
COLOR_YELLOW = (255, 220, 0)
COLOR_ORANGE = (255, 140, 0)
COLOR_GRAY = (100, 100, 100)
COLOR_GREEN = (74, 255, 74)
COLOR_PURPLE = (147, 112, 219)

PALETTE = [
    ("CYAN", (74, 189, 214)),
    ("RED", (255, 74, 74)),
    ("GREEN", (74, 255, 74)),
    ("YELLOW", (255, 220, 0)),
    ("PINK", (255, 105, 180)),
    ("ORANGE", (255, 140, 0)),
    ("PURPLE", (147, 112, 219)),
    ("WHITE", (255, 255, 255)),
]

FONT_TITLE = pygame.font.SysFont("Courier", 48, bold=True)
FONT_SUBTITLE = pygame.font.SysFont("Consolas", 16, bold=True)
FONT_ARCADE = pygame.font.SysFont("Courier", 20, bold=True)
FONT_SCORE = pygame.font.SysFont("Courier", 35, bold=True)
FONT_SMALL = pygame.font.SysFont("Consolas", 13)
FONT_TINY = pygame.font.SysFont("Consolas", 10)

SHOP_ITEMS_P1 = [
    {
        "id": "speed",
        "name": "P1 THRUSTER MOD [Speed +]",
        "desc": "Increases P1 permanent movement speed.",
        "base_cost": 50,
        "max_lvl": 10,
    },
    {
        "id": "cd",
        "name": "P1 OVERCLOCK [Cooldown -]",
        "desc": "Reduces P1 ability cooldown times by 10% per level.",
        "base_cost": 75,
        "max_lvl": 8,
    },
    {
        "id": "size",
        "name": "P1 HULL EXPANSION [Size +]",
        "desc": "Permanently increases P1 paddle length.",
        "base_cost": 100,
        "max_lvl": 5,
    },
    {
        "id": "mult",
        "name": "BOUNTY HUNTER [Coin Multiplier]",
        "desc": "Increases coin payouts by +50% per level. (Account Wide)",
        "base_cost": 150,
        "max_lvl": 10,
    },
]

SHOP_ITEMS_P2 = [
    {
        "id": "speed",
        "name": "P2 THRUSTER MOD [Speed +]",
        "desc": "Increases P2 permanent movement speed. (Multiplayer Only)",
        "base_cost": 50,
        "max_lvl": 10,
    },
    {
        "id": "cd",
        "name": "P2 OVERCLOCK [Cooldown -]",
        "desc": "Reduces P2 ability cooldown times by 10% per level. (Multiplayer Only)",
        "base_cost": 75,
        "max_lvl": 8,
    },
    {
        "id": "size",
        "name": "P2 HULL EXPANSION [Size +]",
        "desc": "Permanently increases P2 paddle length. (Multiplayer Only)",
        "base_cost": 100,
        "max_lvl": 5,
    },
]


def get_upgrade_cost(item_id, player_view):
  upgrades = (
      save_data["p1_upgrades"] if player_view == 1 else save_data["p2_upgrades"]
  )
  lvl = upgrades[item_id]
  items_list = SHOP_ITEMS_P1 if player_view == 1 else SHOP_ITEMS_P2
  item = next(i for i in items_list if i["id"] == item_id)
  if lvl >= item["max_lvl"]:
    return "MAX"
  return int(item["base_cost"] * (1.5 ** lvl))


GAME_MODES = ["1 PLAYER (VS BOT)", "2 PLAYERS (LOCAL)"]
BOT_LEVELS = ["EASY", "NORMAL", "HARD", "INSANE", "EXTREME"]
SPEED_NAMES = ["NORMAL", "FAST", "TURBO", "INSANE"]
SPEED_VALUES = [5, 8, 12, 16]
SCORE_VALUES = [3, 5, 7, 9, 11, 13, 15]
BACKGROUND_TYPES = ["DEEP SPACE", "RETRO GRID", "CYBERPUNK"]

ABILITIES = [
    "NONE",
    "GIANT PADDLE",
    "FAST PADDLE",
    "FREEZE ENEMY",
    "SHIELD",
    "BULLET BALL",
    "GHOST BALL",
    "CURVY BALL",
    "TIME SLOW",
    "AUTO PLAY",
    "MULTIBALL",
]

ABILITY_COOLDOWNS = {
    "NONE": 0,
    "GIANT PADDLE": 360,
    "FAST PADDLE": 360,
    "CURVY BALL": 360,
    "GHOST BALL": 600,
    "FREEZE ENEMY": 600,
    "TIME SLOW": 600,
    "AUTO PLAY": 720,
    "SHIELD": 720,
    "BULLET BALL": 600,
    "MULTIBALL": 720,
}

current_mode_index = 0
current_bot_level = 1
current_speed_index = 0
current_score_index = 1
current_bg_index = 0
p1_color_idx = 0
p2_color_idx = 1
p1_ability_idx = 1
p2_ability_idx = 10

menu_row_selected = 0
shop_row_selected = 0
shop_player_view = 1
settings_row_selected = 0
grid_offset = 0

GRID_SIZE = 40
custom_map_objects = []
editor_tool = "wall"

player_one = PlayerOne(26, 250, PALETTE[p1_color_idx][1])
player_two = PlayerTwo(WIDTH - 26 - 15, 250, PALETTE[p2_color_idx][1])


def make_solid_paddle(paddle, color):
  w, h = paddle.rect.width, paddle.rect.height
  paddle.image = pygame.Surface((w, h))
  paddle.image.fill(color)


make_solid_paddle(player_one, PALETTE[p1_color_idx][1])
make_solid_paddle(player_two, PALETTE[p2_color_idx][1])

ball = Ball(WIDTH, HEIGHT)
ball.color = (255, 255, 255)

paddles_group = pygame.sprite.Group(player_one, player_two)
stars = [
    [random.randint(0, WIDTH), random.randint(0, HEIGHT), random.randint(1, 3)]
    for _ in range(60)
]
ball_particles = []

shake_timer = 0
shake_intensity = 0


def trigger_shake(duration, intensity):
  global shake_timer, shake_intensity
  shake_timer = duration
  shake_intensity = intensity


def get_next_color(current_idx, other_idx, direction):
  new_idx = (current_idx + direction) % len(PALETTE)
  while new_idx == other_idx:
    new_idx = (new_idx + direction) % len(PALETTE)
  return new_idx


# ---------------------------------------------------------------------
#  MOUSE / UI INTERACTION LAYER
#  Draw functions register their clickable regions every frame via
#  ui_register(); the event handlers in main() look them up by name with
#  ui_click()/ui_hover(). Because the rects come from the same code that
#  draws the widgets, a hitbox can never drift out of sync with what is
#  actually on screen.
# ---------------------------------------------------------------------
UI_HITBOXES = {}
_cursor_is_hand = False


def ui_reset():
  UI_HITBOXES.clear()


def ui_register(name, rect):
  UI_HITBOXES[name] = pygame.Rect(rect)
  return UI_HITBOXES[name]


def ui_click(name, pos):
  r = UI_HITBOXES.get(name)
  return r is not None and r.collidepoint(pos)


def ui_hover(name, pos=None):
  return ui_click(name, pos if pos is not None else pygame.mouse.get_pos())


def ui_side(name, pos):
  """-1 if the click landed on the left half of a widget, +1 on the right."""
  r = UI_HITBOXES.get(name)
  if r is None:
    return 1
  return -1 if pos[0] < r.centerx else 1


def ui_sync_cursor():
  """Show a hand cursor whenever something clickable is under the mouse."""
  global _cursor_is_hand
  mp = pygame.mouse.get_pos()
  want = any(r.collidepoint(mp) for r in UI_HITBOXES.values())
  if want != _cursor_is_hand:
    _cursor_is_hand = want
    try:
      pygame.mouse.set_cursor(
          pygame.SYSTEM_CURSOR_HAND if want else pygame.SYSTEM_CURSOR_ARROW
      )
    except Exception:
      pass


def draw_button(surface, rect, label, font, base_color, hot_color, mouse_pos,
                 idle_strength=1.0):
  """Draw a neon button. Returns True when the mouse is over it.

  idle_strength (0-1) softens the resting (non-hovered) look toward the
  background, so a button can sit quietly as part of the dark UI until the
  mouse finds it. 1.0 (default) reproduces the original full-brightness
  look, so existing callers are unaffected.
  """
  rect = pygame.Rect(rect)
  hot = rect.collidepoint(mouse_pos)
  if hot:
    col, border_col, text_col, fill_alpha, border_w = (
        hot_color, hot_color, hot_color, 60, 2,
    )
  else:
    col = base_color
    border_col = tuple(int(c * idle_strength) for c in col)
    # Text stays a bit more legible than the border even when dimmed.
    text_factor = 0.5 + 0.5 * idle_strength
    text_col = tuple(int(c * text_factor) for c in col)
    fill_alpha = int(22 * idle_strength)
    border_w = 1
  bg = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
  bg.fill((col[0], col[1], col[2], fill_alpha))
  surface.blit(bg, rect.topleft)
  pygame.draw.rect(surface, border_col, rect, border_w)
  txt = font.render(label, True, text_col)
  surface.blit(txt, txt.get_rect(center=rect.center))
  return hot


# ---------------------------------------------------------------------
#  ONLINE / CLOUD SYSTEM -- PART 1 (accounts, friends, chat, coins)
#  The actual synced match (tick system) is Part 2; CHALLENGE below only
#  notifies the other player for now, it doesn't start a game yet.
# ---------------------------------------------------------------------
SERVER_HOST = "pong-skills-remastered-release.onrender.com"  # LAN play: change to your host's local IP.
SERVER_PORT = 8765         # Both machines must use the same port.

net = NetClient()
net_state = {
    "logged_in": False,
    "user_id": None,
    "username": None,
    "coins": 0,
    "friends": [],       # [{username, online, status}], status: accepted/incoming
    "chat_target": None,
    "chat_log": [],
    "error": None,
    "info": None,
    "auth_mode": "login",
}


class TextInput:
  """A minimal single-line text box. Focus is managed by the caller
  (see focus_only/cycle_focus below); this class just accumulates
  keystrokes while .focused is True."""

  def __init__(self, max_len=24, masked=False):
    self.text = ""
    self.max_len = max_len
    self.masked = masked
    self.focused = False

  def handle_key(self, event):
    """Returns 'submit' on Enter, True if the key was consumed."""
    if not self.focused or event.type != pygame.KEYDOWN:
      return False
    if event.key == pygame.K_BACKSPACE:
      self.text = self.text[:-1]
      return True
    if event.key == pygame.K_RETURN:
      return "submit"
    if event.key in (pygame.K_TAB, pygame.K_ESCAPE):
      return False  # let the caller handle focus-switching / back-out
    ch = event.unicode
    if ch and ch.isprintable() and len(self.text) < self.max_len:
      self.text += ch
    return True

  def display_text(self):
    return "*" * len(self.text) if self.masked else self.text

  def clear(self):
    self.text = ""


net_fields = {
    "user": TextInput(max_len=20),
    "pass": TextInput(max_len=32, masked=True),
    "friend": TextInput(max_len=20),
    "chat": TextInput(max_len=200),
    "coins": TextInput(max_len=6),
}


def draw_text_input(surface, rect, field, font, placeholder=""):
  rect = pygame.Rect(rect)
  border = COLOR_GREEN if field.focused else COLOR_GRAY
  pygame.draw.rect(surface, (18, 22, 32), rect)
  pygame.draw.rect(surface, border, rect, 2 if field.focused else 1)
  shown = field.display_text()
  txt_color = COLOR_WHITE if (shown or field.focused) else COLOR_GRAY
  txt = font.render(shown if (shown or field.focused) else placeholder, True, txt_color)
  surface.blit(txt, (rect.x + 8, rect.centery - txt.get_height() // 2))
  if field.focused and (pygame.time.get_ticks() // 500) % 2 == 0:
    cx = rect.x + 8 + font.size(shown)[0] + 2
    pygame.draw.line(surface, COLOR_WHITE, (cx, rect.y + 6), (cx, rect.bottom - 6), 1)
  return rect


def focus_only(field):
  for f in net_fields.values():
    f.focused = False
  field.focused = True


def cycle_focus(order):
  cur = next((n for n in order if net_fields[n].focused), None)
  idx = (order.index(cur) + 1) % len(order) if cur else 0
  focus_only(net_fields[order[idx]])


def start_connect():
  net_state["error"] = None
  net.connect("ws://%s:%d" % (SERVER_HOST, SERVER_PORT))


def try_auth_submit():
  user = net_fields["user"].text.strip()
  pw = net_fields["pass"].text
  if not user or not pw:
    net_state["error"] = "Enter a username and password."
    return
  if not net.connected:
    net_state["error"] = "Not connected to the server yet."
    return
  net.send({"type": net_state["auth_mode"], "username": user, "password": pw})


def submit_add_friend():
  name = net_fields["friend"].text.strip()
  if name:
    net.send({"type": "friend_add", "username": name})
    net_fields["friend"].clear()


def submit_chat():
  body = net_fields["chat"].text.strip()
  if body and net_state["chat_target"]:
    net.send({"type": "chat_send", "to": net_state["chat_target"], "body": body})
    net_fields["chat"].clear()


def submit_coins():
  amt = net_fields["coins"].text.strip()
  if amt.isdigit() and int(amt) > 0 and net_state["chat_target"]:
    net.send({"type": "coins_send", "to": net_state["chat_target"], "amount": int(amt)})
    net_fields["coins"].clear()


def open_chat_with(username):
  net_state["chat_target"] = username
  net_state["chat_log"] = []
  net.send({"type": "chat_history", "with": username})


def net_process_incoming():
  """Drain messages the background thread has received since last frame
  and fold them into net_state. Call this once per frame while on an
  ONLINE_* screen."""
  for msg in net.poll():
    t = msg.get("type")
    if t == "auth_ok":
      net_state.update(logged_in=True, user_id=msg["user_id"], username=msg["username"],
                        coins=msg["coins"], error=None)
    elif t == "auth_fail":
      net_state["error"] = msg.get("reason", "Login failed.")
    elif t == "friend_list":
      net_state["friends"] = msg["friends"]
    elif t == "friend_request":
      net_state["info"] = "%s sent you a friend request!" % msg["from_username"]
      net.send({"type": "friend_list"})  # pull the fresh incoming entry in now
    elif t == "presence":
      for f in net_state["friends"]:
        if f["username"] == msg["username"]:
          f["online"] = msg["online"]
    elif t == "chat_message":
      other = msg["to"] if msg["from_username"] == net_state["username"] else msg["from_username"]
      if net_state["chat_target"] == other:
        net_state["chat_log"].append(msg)
    elif t == "chat_history":
      if net_state["chat_target"] == msg["with_username"]:
        net_state["chat_log"] = msg["messages"]
    elif t == "coins_update":
      net_state["coins"] = msg["coins"]
    elif t == "coins_received":
      net_state["info"] = "%s sent you %d coins!" % (msg["from_username"], msg["amount"])
    elif t == "challenge_received":
      net_state["info"] = "%s challenged you! (Online matches arrive in Part 2)" % msg["from_username"]
    elif t == "error":
      net_state["error"] = msg.get("message")
    elif t == "info":
      net_state["info"] = msg.get("message")


def net_logout():
  net.disconnect()
  net_state.update(logged_in=False, friends=[], chat_target=None, chat_log=[],
                    error=None, info=None)
  for f in net_fields.values():
    f.clear()


# ---------------------------------------------------------------------
#  Dedicated background for the online screens -- a "cloud network" of
#  pulsing nodes with data packets flowing between them, distinct from
#  the in-match backgrounds (which are the player's chosen arena theme,
#  not appropriate here). Built once at import time, animated by
#  frame_count like the rest of the game's backgrounds.
# ---------------------------------------------------------------------
_NET_BG_SPACING = 115
net_bg_nodes = []
for _gx in range(-1, WIDTH // _NET_BG_SPACING + 2):
  for _gy in range(-1, HEIGHT // _NET_BG_SPACING + 2):
    net_bg_nodes.append({
        "x": _gx * _NET_BG_SPACING + random.randint(-18, 18),
        "y": _gy * _NET_BG_SPACING + random.randint(-18, 18),
        "gx": _gx,
        "gy": _gy,
        "phase": random.uniform(0, math.tau if hasattr(math, "tau") else 6.28318),
    })

_net_bg_node_lookup = {(n["gx"], n["gy"]): n for n in net_bg_nodes}
net_bg_edges = []
for n in net_bg_nodes:
  right = _net_bg_node_lookup.get((n["gx"] + 1, n["gy"]))
  down = _net_bg_node_lookup.get((n["gx"], n["gy"] + 1))
  if right is not None:
    net_bg_edges.append((n, right))
  if down is not None:
    net_bg_edges.append((n, down))

net_bg_packets = [
    {"edge": random.choice(net_bg_edges), "t": random.uniform(0, 1),
     "speed": random.uniform(0.006, 0.014)}
    for _ in range(14)
] if net_bg_edges else []


def draw_online_background(surface, frame_count):
  surface.fill((6, 15, 14))  # deep teal-black -- distinct from every in-match theme

  for a, b in net_bg_edges:
    pygame.draw.line(surface, (18, 48, 40), (a["x"], a["y"]), (b["x"], b["y"]), 1)

  for pkt in net_bg_packets:
    a, b = pkt["edge"]
    pkt["t"] += pkt["speed"]
    if pkt["t"] >= 1.0:
      pkt["t"] = 0.0
      pkt["edge"] = random.choice(net_bg_edges)
    t = pkt["t"]
    px = a["x"] + (b["x"] - a["x"]) * t
    py = a["y"] + (b["y"] - a["y"]) * t
    pygame.draw.circle(surface, COLOR_GREEN, (int(px), int(py)), 3)

  for n in net_bg_nodes:
    pulse = 0.5 + 0.5 * math.sin(frame_count * 0.04 + n["phase"])
    radius = 2 + int(pulse * 2)
    dim = (int(30 + pulse * 60), int(90 + pulse * 120), int(70 + pulse * 90))
    pygame.draw.circle(surface, dim, (n["x"], n["y"]), radius)


def draw_online_auth(canvas, frame_count):
  mouse_pos = pygame.mouse.get_pos()
  ui_reset()
  draw_online_background(canvas, frame_count)

  title = FONT_TITLE.render("PLAY ONLINE", True, COLOR_GREEN)
  canvas.blit(title, title.get_rect(center=(WIDTH // 2, 55)))

  if net.connected:
    status_txt, status_col = "Connected to %s:%d" % (SERVER_HOST, SERVER_PORT), COLOR_GREEN
  elif net.connect_error:
    status_txt, status_col = "Couldn't reach server: %s" % net.connect_error, COLOR_RED
  else:
    status_txt, status_col = "Connecting to %s:%d ..." % (SERVER_HOST, SERVER_PORT), COLOR_YELLOW
  status_surf = FONT_SMALL.render(status_txt, True, status_col)
  canvas.blit(status_surf, status_surf.get_rect(center=(WIDTH // 2, 100)))

  box = pygame.Rect(WIDTH // 2 - 220, 140, 440, 300)
  pygame.draw.rect(canvas, (15, 20, 30), box)
  pygame.draw.rect(canvas, COLOR_GREEN, box, 2)

  mode_login = pygame.Rect(box.x + 30, box.y + 20, 180, 32)
  mode_reg = pygame.Rect(box.x + 230, box.y + 20, 180, 32)
  is_login = net_state["auth_mode"] == "login"
  draw_button(canvas, mode_login, "LOG IN", FONT_TINY,
              COLOR_WHITE if is_login else COLOR_GRAY, COLOR_WHITE, mouse_pos,
              idle_strength=1.0 if is_login else 0.5)
  draw_button(canvas, mode_reg, "REGISTER", FONT_TINY,
              COLOR_WHITE if not is_login else COLOR_GRAY, COLOR_WHITE, mouse_pos,
              idle_strength=1.0 if not is_login else 0.5)
  ui_register("auth_mode_login", mode_login)
  ui_register("auth_mode_register", mode_reg)

  canvas.blit(FONT_SMALL.render("USERNAME", True, COLOR_WHITE), (box.x + 30, box.y + 72))
  user_rect = pygame.Rect(box.x + 30, box.y + 94, 380, 34)
  draw_text_input(canvas, user_rect, net_fields["user"], FONT_SMALL, "3-20 letters/numbers")
  ui_register("auth_user", user_rect)

  canvas.blit(FONT_SMALL.render("PASSWORD", True, COLOR_WHITE), (box.x + 30, box.y + 140))
  pass_rect = pygame.Rect(box.x + 30, box.y + 162, 380, 34)
  draw_text_input(canvas, pass_rect, net_fields["pass"], FONT_SMALL, "at least 4 characters")
  ui_register("auth_pass", pass_rect)

  submit_rect = pygame.Rect(box.x + 30, box.y + 214, 380, 40)
  submit_label = "LOG IN" if is_login else "CREATE ACCOUNT"
  draw_button(canvas, submit_rect, submit_label, FONT_ARCADE, COLOR_GREEN, COLOR_WHITE, mouse_pos)
  ui_register("auth_submit", submit_rect)

  msg_y = box.bottom + 28
  if net_state["error"]:
    err_surf = FONT_SMALL.render(net_state["error"], True, COLOR_RED)
    canvas.blit(err_surf, err_surf.get_rect(center=(WIDTH // 2, msg_y)))
    msg_y += 26

  if net.connect_error and not net.connected:
    retry_rect = pygame.Rect(WIDTH // 2 - 70, msg_y, 140, 30)
    draw_button(canvas, retry_rect, "RETRY", FONT_TINY, COLOR_YELLOW, COLOR_WHITE, mouse_pos)
    ui_register("auth_retry", retry_rect)

  back_rect = pygame.Rect(WIDTH // 2 - 70, HEIGHT - 46, 140, 28)
  draw_button(canvas, back_rect, "BACK  [ESC]", FONT_TINY, COLOR_GRAY, COLOR_WHITE, mouse_pos)
  ui_register("auth_back", back_rect)

  ui_sync_cursor()
  draw_scanlines(canvas)


def draw_online_lobby(canvas, frame_count):
  mouse_pos = pygame.mouse.get_pos()
  ui_reset()
  draw_online_background(canvas, frame_count)

  canvas.blit(FONT_ARCADE.render("PLAY ONLINE", True, COLOR_GREEN), (30, 18))
  who_surf = FONT_SMALL.render(
      "%s   |   Server: %s:%d" % (net_state["username"], SERVER_HOST, SERVER_PORT),
      True, COLOR_WHITE,
  )
  canvas.blit(who_surf, (30, 46))
  coins_surf = FONT_ARCADE.render("COINS: %d" % net_state["coins"], True, COLOR_ORANGE)
  canvas.blit(coins_surf, coins_surf.get_rect(topright=(WIDTH - 170, 18)))

  logout_rect = pygame.Rect(WIDTH - 150, 16, 120, 28)
  draw_button(canvas, logout_rect, "LOG OUT", FONT_TINY, COLOR_RED, COLOR_WHITE, mouse_pos)
  ui_register("lobby_logout", logout_rect)

  # --- Friends panel ---
  fp = pygame.Rect(30, 80, 380, 470)
  pygame.draw.rect(canvas, (15, 20, 30), fp)
  pygame.draw.rect(canvas, COLOR_BLUE, fp, 2)
  canvas.blit(FONT_SMALL.render("FRIENDS", True, COLOR_BLUE), (fp.x + 12, fp.y + 10))

  add_field = pygame.Rect(fp.x + 12, fp.y + 34, 260, 30)
  draw_text_input(canvas, add_field, net_fields["friend"], FONT_TINY, "add by username")
  ui_register("lobby_add_friend_field", add_field)
  add_btn = pygame.Rect(fp.right - 82, fp.y + 34, 70, 30)
  draw_button(canvas, add_btn, "ADD", FONT_TINY, COLOR_GREEN, COLOR_WHITE, mouse_pos)
  ui_register("lobby_add_friend_btn", add_btn)

  row_y = fp.y + 78
  incoming = [f for f in net_state["friends"] if f["status"] == "incoming"]
  accepted = [f for f in net_state["friends"] if f["status"] == "accepted"]

  for f in incoming:
    row = pygame.Rect(fp.x + 8, row_y, fp.width - 16, 30)
    pygame.draw.rect(canvas, (60, 45, 15), row)
    name_surf = FONT_TINY.render(f["username"] + " wants to be friends", True, COLOR_YELLOW)
    canvas.blit(name_surf, (row.x + 6, row.centery - name_surf.get_height() // 2))
    accept_btn = pygame.Rect(row.right - 130, row.y + 2, 60, 26)
    decline_btn = pygame.Rect(row.right - 65, row.y + 2, 60, 26)
    draw_button(canvas, accept_btn, "YES", FONT_TINY, COLOR_GREEN, COLOR_WHITE, mouse_pos)
    draw_button(canvas, decline_btn, "NO", FONT_TINY, COLOR_RED, COLOR_WHITE, mouse_pos)
    ui_register("lobby_accept_" + f["username"], accept_btn)
    ui_register("lobby_decline_" + f["username"], decline_btn)
    row_y += 34

  if not accepted:
    empty_surf = FONT_TINY.render("No friends yet -- add one above!", True, COLOR_GRAY)
    canvas.blit(empty_surf, (fp.x + 12, row_y + 4))
    row_y += 30

  for f in accepted:
    row = pygame.Rect(fp.x + 8, row_y, fp.width - 16, 32)
    is_sel = net_state["chat_target"] == f["username"]
    is_hot = row.collidepoint(mouse_pos)
    if is_sel or is_hot:
      hi = pygame.Surface(row.size, pygame.SRCALPHA)
      hi.fill((*COLOR_BLUE, 45 if is_sel else 22))
      canvas.blit(hi, row.topleft)
    dot_color = COLOR_GREEN if f["online"] else COLOR_GRAY
    pygame.draw.circle(canvas, dot_color, (row.x + 14, row.centery), 5)
    name_surf = FONT_SMALL.render(f["username"], True, COLOR_WHITE if f["online"] else COLOR_GRAY)
    canvas.blit(name_surf, (row.x + 28, row.centery - name_surf.get_height() // 2))
    status_surf = FONT_TINY.render("ONLINE" if f["online"] else "OFFLINE", True, dot_color)
    canvas.blit(status_surf, status_surf.get_rect(midright=(row.right - 8, row.centery)))
    ui_register("lobby_friend_" + f["username"], row)
    row_y += 36

  # --- Chat / actions panel ---
  cp = pygame.Rect(430, 80, WIDTH - 460, 470)
  pygame.draw.rect(canvas, (15, 20, 30), cp)
  pygame.draw.rect(canvas, COLOR_PURPLE, cp, 2)

  target = net_state["chat_target"]
  if not target:
    hint = FONT_SMALL.render("Select a friend on the left to chat, send coins, or challenge them.",
                              True, COLOR_GRAY)
    canvas.blit(hint, hint.get_rect(center=(cp.centerx, cp.y + 40)))
  else:
    header = FONT_SMALL.render("CHAT WITH %s" % target, True, COLOR_PURPLE)
    canvas.blit(header, (cp.x + 12, cp.y + 10))

    log_rect = pygame.Rect(cp.x + 12, cp.y + 36, cp.width - 24, 300)
    pygame.draw.rect(canvas, (10, 12, 20), log_rect)
    lines = net_state["chat_log"][-10:]
    ly = log_rect.bottom - 22
    for m in reversed(lines):
      mine = m["from_username"] == net_state["username"]
      prefix = "you: " if mine else "%s: " % m["from_username"]
      col = COLOR_BLUE if mine else COLOR_WHITE
      line_surf = FONT_TINY.render(prefix + m["body"], True, col)
      canvas.blit(line_surf, (log_rect.x + 8, ly))
      ly -= 20
      if ly < log_rect.y:
        break

    chat_field = pygame.Rect(cp.x + 12, log_rect.bottom + 10, cp.width - 110, 32)
    draw_text_input(canvas, chat_field, net_fields["chat"], FONT_SMALL, "type a message...")
    ui_register("lobby_chat_field", chat_field)
    send_btn = pygame.Rect(chat_field.right + 8, chat_field.y, 78, 32)
    draw_button(canvas, send_btn, "SEND", FONT_TINY, COLOR_PURPLE, COLOR_WHITE, mouse_pos)
    ui_register("lobby_chat_send", send_btn)

    action_y = chat_field.bottom + 16
    canvas.blit(FONT_TINY.render("SEND COINS:", True, COLOR_ORANGE), (cp.x + 12, action_y + 8))
    coins_field = pygame.Rect(cp.x + 120, action_y, 90, 32)
    draw_text_input(canvas, coins_field, net_fields["coins"], FONT_SMALL, "amount")
    ui_register("lobby_coins_field", coins_field)
    coins_btn = pygame.Rect(coins_field.right + 8, action_y, 70, 32)
    draw_button(canvas, coins_btn, "SEND", FONT_TINY, COLOR_ORANGE, COLOR_WHITE, mouse_pos)
    ui_register("lobby_coins_send", coins_btn)

    challenge_btn = pygame.Rect(cp.right - 190, action_y, 178, 32)
    draw_button(canvas, challenge_btn, "CHALLENGE", FONT_TINY, COLOR_RED, COLOR_WHITE, mouse_pos)
    ui_register("lobby_challenge", challenge_btn)

  msg_y = fp.bottom + 12
  if net_state["error"]:
    canvas.blit(FONT_TINY.render(net_state["error"], True, COLOR_RED), (fp.x, msg_y))
  elif net_state["info"]:
    canvas.blit(FONT_TINY.render(net_state["info"], True, COLOR_GREEN), (fp.x, msg_y))

  back_rect = pygame.Rect(WIDTH // 2 - 70, HEIGHT - 40, 140, 26)
  draw_button(canvas, back_rect, "BACK  [ESC]", FONT_TINY, COLOR_GRAY, COLOR_WHITE, mouse_pos)
  ui_register("lobby_back", back_rect)

  ui_sync_cursor()
  draw_scanlines(canvas)


def apply_menu_change(row, direction):
  """Cycle the value on a main-menu row. Shared by keyboard and mouse."""
  global current_mode_index, current_bot_level, current_speed_index
  global current_score_index, current_bg_index, p1_color_idx, p2_color_idx
  global p1_ability_idx, p2_ability_idx

  if row == 0:
    current_mode_index = (current_mode_index + direction) % len(GAME_MODES)
  elif row == 1:
    if current_mode_index == 0:  # bot level is N/A in 2-player mode
      current_bot_level = (current_bot_level + direction) % len(BOT_LEVELS)
  elif row == 2:
    current_speed_index = (current_speed_index + direction) % len(SPEED_NAMES)
  elif row == 3:
    current_score_index = (current_score_index + direction) % len(SCORE_VALUES)
  elif row == 4:
    current_bg_index = (current_bg_index + direction) % len(BACKGROUND_TYPES)
  elif row == 5:
    p1_color_idx = get_next_color(p1_color_idx, p2_color_idx, direction)
  elif row == 6:
    p2_color_idx = get_next_color(p2_color_idx, p1_color_idx, direction)
  elif row == 7:
    p1_ability_idx = (p1_ability_idx + direction) % len(ABILITIES)
  elif row == 8:
    p2_ability_idx = (p2_ability_idx + direction) % len(ABILITIES)


def shop_item_count():
  return len(SHOP_ITEMS_P1) if shop_player_view == 1 else len(SHOP_ITEMS_P2)


def try_buy_upgrade():
  """Buy the selected shop upgrade if it is affordable and not maxed."""
  active_items = SHOP_ITEMS_P1 if shop_player_view == 1 else SHOP_ITEMS_P2
  upgrades_dict = (
      save_data["p1_upgrades"] if shop_player_view == 1 else save_data["p2_upgrades"]
  )
  item = active_items[shop_row_selected]
  cost = get_upgrade_cost(item["id"], shop_player_view)
  if cost != "MAX" and save_data["coins"] >= cost:
    save_data["coins"] -= cost
    upgrades_dict[item["id"]] += 1
    write_save()
    return True
  return False


def apply_setting_change(row, direction):
  """Change one settings row. Shared by keyboard and mouse."""
  global MUSIC_VOLUME, screen

  if row == 0:
    save_data["show_fps"] = not save_data["show_fps"]
  elif row == 1:
    save_data["volume"] = max(0, min(100, save_data["volume"] + (direction * 10)))
    MUSIC_VOLUME = save_data["volume"] / 100.0
    pygame.mixer.music.set_volume(MUSIC_VOLUME)
  elif row == 2:
    save_data["fullscreen"] = not save_data["fullscreen"]
    screen = create_window()
  elif row == 3:
    save_data["vsync"] = not save_data.get("vsync", True)
    screen = create_window()
  elif row == 4:
    save_data["target_fps"] = max(
        60, min(360, save_data.get("target_fps", 240) + (direction * 20))
    )
  write_save()


def draw_scanlines(surface):
  scanline_surf = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
  for y in range(0, HEIGHT, 3):
    pygame.draw.line(scanline_surf, (0, 0, 0, 50), (0, y), (WIDTH, y), 1)
  surface.blit(scanline_surf, (0, 0))


def draw_fps_counter(surface):
  if save_data.get("show_fps", True):
    fps_val = int(clock.get_fps())
    fps_surf = FONT_TINY.render(f"FPS: {fps_val}", True, COLOR_GREEN)
    surface.blit(fps_surf, (WIDTH - 65, 10))


def draw_background(surface, frame_count):
  global grid_offset
  bg_type = BACKGROUND_TYPES[current_bg_index]

  if bg_type == "DEEP SPACE":
    surface.fill((10, 10, 25))
    for star in stars:
      star[1] += star[2] * 0.5
      if star[1] > HEIGHT:
        star[1] = 0
        star[0] = random.randint(0, WIDTH)
      alpha = int(128 + 127 * math.sin(frame_count * 0.05 + star[0]))
      star_color = (
          min(255, 150 + alpha // 2),
          min(255, 150 + alpha // 2),
          255,
      )
      pygame.draw.circle(
          surface, star_color, (int(star[0]), int(star[1])), star[2]
      )

  elif bg_type == "RETRO GRID":
    surface.fill((15, 5, 30))
    sun_center = (WIDTH // 2, HEIGHT // 2 - 50)
    pygame.draw.circle(surface, (255, 69, 0), sun_center, 90)
    pygame.draw.circle(surface, (255, 200, 0), sun_center, 70)
    for i in range(6):
      strip_y = sun_center[1] + 20 + i * 12
      pygame.draw.rect(
          surface, (15, 5, 30), (sun_center[0] - 100, strip_y, 200, 5)
      )

    grid_offset = (grid_offset + 1) % 40
    for x in range(0, WIDTH, 80):
      pygame.draw.line(surface, (255, 0, 128), (x, 0), (x, HEIGHT), 1)
    for y in range(grid_offset, HEIGHT, 40):
      pygame.draw.line(surface, (0, 255, 255), (0, y), (WIDTH, y), 1)

  elif bg_type == "CYBERPUNK":
    surface.fill((6, 8, 18))
    horizon_y = HEIGHT // 2
    pygame.draw.line(
        surface, (0, 255, 200), (0, horizon_y), (WIDTH, horizon_y), 2
    )

    center_x = WIDTH // 2
    col_x_coords = [center_x]
    offset = 140
    while center_x - offset > 0:
      col_x_coords.append(center_x - offset)
      col_x_coords.append(center_x + offset)
      offset += 140

    for i, x in enumerate(sorted(col_x_coords)):
      col_color = (255, 0, 128) if i % 2 == 0 else (0, 255, 200)
      pygame.draw.line(surface, col_color, (x, 0), (x, HEIGHT), 2)
      spark_y = (frame_count * 5 + x) % HEIGHT
      pygame.draw.circle(surface, (255, 255, 255), (x, spark_y), 3)
      pygame.draw.circle(surface, col_color, (x, spark_y), 7, 1)


def draw_neon_corners(
    surface,
    rect,
    base_color,
    frame_count,
    corner_len=10,
    is_selected=False,
):
  pulse = (
      int(180 + 75 * math.sin(frame_count * 0.3))
      if is_selected
      else int(100 + 40 * math.sin(frame_count * 0.05))
  )
  alpha_glow = 150 if is_selected else 40
  core_width = 2 if is_selected else 1

  neon_color = (
      min(255, max(30, (base_color[0] * pulse) // 255)),
      min(255, max(30, (base_color[1] * pulse) // 255)),
      min(255, max(30, (base_color[2] * pulse) // 255)),
  )

  glow_surface = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
  x, y, w, h = rect.x, rect.y, rect.width, rect.height

  lines = [
      ((x, y), (x + corner_len, y)),
      ((x, y), (x, y + corner_len)),
      ((x + w, y), (x + w - corner_len, y)),
      ((x + w, y), (x + w, y + corner_len)),
      ((x, y + h), (x + corner_len, y + h)),
      ((x, y + h), (x, y + h - corner_len)),
      ((x + w, y + h), (x + w - corner_len, y + h)),
      ((x + w, y + h), (x + w, y + h - corner_len)),
  ]

  thick = 4 if is_selected else 2
  for start, end in lines:
    pygame.draw.line(glow_surface, (*neon_color, alpha_glow), start, end, thick)
  surface.blit(glow_surface, (0, 0))

  for start, end in lines:
    pygame.draw.line(surface, neon_color, start, end, core_width)


def draw_shop(surface, frame_count):
  canvas = pygame.Surface((WIDTH, HEIGHT))
  draw_background(canvas, frame_count)

  theme_color = COLOR_BLUE if shop_player_view == 1 else COLOR_RED

  pygame.draw.line(canvas, theme_color, (0, 15), (WIDTH, 15), 3)
  pygame.draw.line(canvas, theme_color, (0, HEIGHT - 15), (WIDTH, HEIGHT - 15), 3)

  title_str = (
      "P1 BLACK MARKET" if shop_player_view == 1 else "P2 BLACK MARKET"
  )
  title_surf = FONT_TITLE.render(title_str, True, theme_color)
  canvas.blit(title_surf, title_surf.get_rect(center=(WIDTH // 2, 45)))

  coin_txt = f"COINS: {save_data['coins']} "
  coin_surf = FONT_ARCADE.render(coin_txt, True, COLOR_ORANGE)
  canvas.blit(coin_surf, coin_surf.get_rect(center=(WIDTH // 2, 85)))

  # --- Clickable page tabs + back button ---
  mouse_pos = pygame.mouse.get_pos()
  ui_reset()

  p1_tab = pygame.Rect(90, 72, 150, 28)
  p2_tab = pygame.Rect(WIDTH - 240, 72, 150, 28)
  draw_button(
      canvas, p1_tab, "< P1 UPGRADES", FONT_TINY,
      COLOR_BLUE if shop_player_view == 1 else COLOR_GRAY, COLOR_BLUE, mouse_pos,
  )
  draw_button(
      canvas, p2_tab, "P2 UPGRADES >", FONT_TINY,
      COLOR_RED if shop_player_view == 2 else COLOR_GRAY, COLOR_RED, mouse_pos,
  )
  ui_register("shop_tab_p1", p1_tab)
  ui_register("shop_tab_p2", p2_tab)

  back_btn = pygame.Rect(WIDTH // 2 - 70, 512, 140, 24)
  draw_button(canvas, back_btn, "BACK  [ESC]", FONT_TINY, COLOR_GRAY,
              COLOR_WHITE, mouse_pos)
  ui_register("shop_back", back_btn)

  board_rect = pygame.Rect(80, 110, 840, 395)
  board_bg = pygame.Surface((board_rect.width, board_rect.height), pygame.SRCALPHA)
  board_bg.fill((10, 10, 20, 220))
  canvas.blit(board_bg, board_rect.topleft)
  pygame.draw.rect(canvas, theme_color, board_rect, 2)
  draw_neon_corners(
      canvas, board_rect, theme_color, frame_count, corner_len=20, is_selected=True
  )

  active_items = SHOP_ITEMS_P1 if shop_player_view == 1 else SHOP_ITEMS_P2
  upgrades_dict = (
      save_data["p1_upgrades"] if shop_player_view == 1 else save_data["p2_upgrades"]
  )

  y_start = 125
  for i, item in enumerate(active_items):
    is_sel = shop_row_selected == i
    lvl = upgrades_dict[item["id"]]
    cost = get_upgrade_cost(item["id"], shop_player_view)

    row_rect = pygame.Rect(100, y_start + i * 92, 800, 82)
    ui_register("shop_row_%d" % i, row_rect)
    is_hot = row_rect.collidepoint(mouse_pos)

    if is_sel or is_hot:
      hover_surf = pygame.Surface((800, 82), pygame.SRCALPHA)
      hover_surf.fill((*theme_color, 40 if is_sel else 22))
      canvas.blit(hover_surf, row_rect.topleft)
      pygame.draw.rect(canvas, theme_color, row_rect, 2)
    else:
      pygame.draw.rect(canvas, (50, 50, 50), row_rect, 1)

    if is_hot and cost != "MAX" and save_data["coins"] >= cost:
      buy_hint = FONT_TINY.render("CLICK TO BUY", True, COLOR_GREEN)
      canvas.blit(buy_hint, (row_rect.right - 115, row_rect.bottom - 20))

    name_color = COLOR_WHITE if not is_sel else theme_color
    name_surf = FONT_SUBTITLE.render(item["name"], True, name_color)
    canvas.blit(name_surf, (row_rect.x + 15, row_rect.y + 12))

    desc_surf = FONT_TINY.render(item["desc"], True, COLOR_GRAY)
    canvas.blit(desc_surf, (row_rect.x + 15, row_rect.y + 45))

    lvl_txt = f"LVL: {lvl}/{item['max_lvl']}"
    lvl_color = COLOR_GREEN if lvl == item["max_lvl"] else COLOR_WHITE
    lvl_surf = FONT_SUBTITLE.render(lvl_txt, True, lvl_color)
    canvas.blit(lvl_surf, (row_rect.right - 220, row_rect.y + 12))

    cost_txt = "MAXED" if cost == "MAX" else f"COST: {cost} C"
    cost_color = (
        COLOR_RED
        if (cost != "MAX" and save_data["coins"] < cost)
        else COLOR_ORANGE
    )
    cost_surf = FONT_SUBTITLE.render(cost_txt, True, cost_color)
    canvas.blit(cost_surf, (row_rect.right - 220, row_rect.y + 45))

  ctrl_nav = FONT_SMALL.render(
      "MOUSE: CLICK A ROW TO BUY / SCROLL TO NAVIGATE  |  KEYS: [UP/DOWN]"
      " [ENTER] [ESC]",
      True,
      COLOR_WHITE,
  )
  canvas.blit(ctrl_nav, ctrl_nav.get_rect(center=(WIDTH // 2, 545)))

  ui_sync_cursor()
  draw_scanlines(canvas)
  draw_fps_counter(canvas)
  surface.blit(canvas, (0, 0))


def draw_settings(surface, frame_count):
  canvas = pygame.Surface((WIDTH, HEIGHT))
  draw_background(canvas, frame_count)

  pygame.draw.line(canvas, COLOR_PURPLE, (0, 15), (WIDTH, 15), 3)
  pygame.draw.line(canvas, COLOR_PURPLE, (0, HEIGHT - 15), (WIDTH, HEIGHT - 15), 3)

  title_surf = FONT_TITLE.render("SYSTEM SETTINGS", True, COLOR_PURPLE)
  canvas.blit(title_surf, title_surf.get_rect(center=(WIDTH // 2, 50)))

  mouse_pos = pygame.mouse.get_pos()
  ui_reset()

  board_rect = pygame.Rect(150, 100, 700, 390)
  board_bg = pygame.Surface((board_rect.width, board_rect.height), pygame.SRCALPHA)
  board_bg.fill((10, 10, 25, 220))
  canvas.blit(board_bg, board_rect.topleft)
  pygame.draw.rect(canvas, COLOR_PURPLE, board_rect, 2)
  draw_neon_corners(canvas, board_rect, COLOR_PURPLE, frame_count, corner_len=20, is_selected=True)

  settings_options = [
      ("FPS COUNTER", "ENABLED" if save_data["show_fps"] else "DISABLED"),
      ("MUSIC VOLUME", f"{save_data['volume']}%"),
      ("FULLSCREEN", "ENABLED" if save_data["fullscreen"] else "DISABLED"),
      ("VSYNC (REFRESH RATE)", "ENABLED" if save_data.get("vsync", True) else "DISABLED"),
      ("TARGET FPS CAP", f"{save_data.get('target_fps', 240)} (60 - 360)"),
  ]

  y_pos = 135
  for i, (lbl_txt, val_txt) in enumerate(settings_options):
    is_sel = settings_row_selected == i
    lbl_color = COLOR_WHITE if not is_sel else COLOR_YELLOW
    val_color = COLOR_GREEN if (is_sel or "ENABLED" in val_txt or "%" in val_txt) else COLOR_RED

    row_rect = pygame.Rect(180, y_pos - 15, 640, 40)
    ui_register("settings_row_%d" % i, row_rect)
    is_hot = row_rect.collidepoint(mouse_pos)

    if is_sel or is_hot:
      hover_surf = pygame.Surface((640, 40), pygame.SRCALPHA)
      hover_surf.fill((*COLOR_PURPLE, 50 if is_sel else 28))
      canvas.blit(hover_surf, row_rect.topleft)
      pygame.draw.rect(canvas, COLOR_YELLOW, row_rect, 1)

    lbl_surf = FONT_SUBTITLE.render(lbl_txt, True, lbl_color)
    val_surf = FONT_SUBTITLE.render(f"< {val_txt} >", True, val_color)

    canvas.blit(lbl_surf, (220, y_pos - 5))
    canvas.blit(val_surf, (480, y_pos - 5))
    ui_register(
        "settings_val_%d" % i, pygame.Rect((480, y_pos - 5), val_surf.get_size())
    )
    y_pos += 65

  back_btn = pygame.Rect(WIDTH // 2 - 70, 498, 140, 26)
  draw_button(canvas, back_btn, "BACK  [ESC]", FONT_TINY, COLOR_GRAY,
              COLOR_WHITE, mouse_pos)
  ui_register("settings_back", back_btn)

  ctrl_nav = FONT_SMALL.render(
      "MOUSE: CLICK LEFT/RIGHT OF A VALUE OR SCROLL  |  KEYS: [UP/DOWN]"
      " [LEFT/RIGHT] [ESC]",
      True,
      COLOR_WHITE,
  )
  canvas.blit(ctrl_nav, ctrl_nav.get_rect(center=(WIDTH // 2, 540)))

  ui_sync_cursor()
  draw_scanlines(canvas)
  draw_fps_counter(canvas)
  surface.blit(canvas, (0, 0))


def draw_map_editor(surface, frame_count):
  canvas = pygame.Surface((WIDTH, HEIGHT))
  canvas.fill((15, 15, 25))

  for x in range(0, WIDTH, GRID_SIZE):
    pygame.draw.line(canvas, (30, 30, 45), (x, 0), (x, HEIGHT), 1)
  for y in range(0, HEIGHT, GRID_SIZE):
    pygame.draw.line(canvas, (30, 30, 45), (0, y), (WIDTH, y), 1)

  for obj in custom_map_objects:
    if obj["type"] == "wall":
      col = COLOR_WHITE
    elif obj["type"] == "spike":
      col = COLOR_RED
    else:
      col = COLOR_YELLOW
    pygame.draw.rect(
        canvas, col, (obj["x"], obj["y"], obj["w"], obj["h"])
    )
    pygame.draw.rect(canvas, (0, 0, 0), (obj["x"], obj["y"], obj["w"], obj["h"]), 1)

  hud_bg = pygame.Surface((WIDTH, 40), pygame.SRCALPHA)
  hud_bg.fill((0, 0, 0, 200))
  canvas.blit(hud_bg, (0, 0))

  mouse_pos = pygame.mouse.get_pos()
  ui_reset()

  # --- Tool palette (clickable) ---
  editor_tools = [
      ("wall", "1 WALL", COLOR_WHITE),
      ("spike", "2 SPIKE", COLOR_RED),
      ("powerup", "3 POWER", COLOR_YELLOW),
      ("eraser", "4 ERASE", COLOR_GRAY),
  ]
  tool_x = 10
  for tool_id, tool_label, tool_col in editor_tools:
    tool_rect = pygame.Rect(tool_x, 7, 92, 26)
    is_active = editor_tool == tool_id
    draw_button(
        canvas, tool_rect, tool_label, FONT_TINY,
        tool_col if is_active else (70, 70, 80), tool_col, mouse_pos,
    )
    if is_active:
      pygame.draw.rect(canvas, tool_col, tool_rect, 2)
    ui_register("editor_tool_" + tool_id, tool_rect)
    tool_x += 96

  # --- Action buttons (clickable) ---
  editor_actions = [
      ("editor_save", "S SAVE", COLOR_GREEN),
      ("editor_load", "L LOAD", COLOR_BLUE),
      ("editor_play", "P PLAY", COLOR_YELLOW),
      ("editor_menu", "ESC MENU", COLOR_ORANGE),
  ]
  act_x = WIDTH - 75 - (len(editor_actions) * 96 - 4)
  for act_key, act_label, act_col in editor_actions:
    act_rect = pygame.Rect(act_x, 7, 92, 26)
    draw_button(canvas, act_rect, act_label, FONT_TINY, act_col, COLOR_WHITE,
                mouse_pos)
    ui_register(act_key, act_rect)
    act_x += 96

  paint_hint = FONT_TINY.render(
      "L-CLICK: PLACE   R-CLICK: ERASE", True, COLOR_GRAY
  )
  canvas.blit(paint_hint, paint_hint.get_rect(center=(WIDTH // 2, HEIGHT - 14)))

  ui_sync_cursor()
  draw_scanlines(canvas)
  draw_fps_counter(canvas)
  surface.blit(canvas, (0, 0))


def draw_arcade_menu(surface, frame_count):
  canvas = pygame.Surface((WIDTH, HEIGHT))
  draw_background(canvas, frame_count)

  p1_color = PALETTE[p1_color_idx][1]
  p2_color = PALETTE[p2_color_idx][1]

  pygame.draw.line(canvas, COLOR_BLUE, (0, 12), (WIDTH, 12), 3)
  pygame.draw.line(canvas, COLOR_RED, (0, HEIGHT - 12), (WIDTH, HEIGHT - 12), 3)

  title_pulse = int(math.sin(frame_count * 0.1) * 8)
  title_blue = FONT_TITLE.render("SUPER", True, COLOR_BLUE)
  title_red = FONT_TITLE.render("PONG", True, COLOR_RED)
  title_gap = 35

  total_width = title_blue.get_width() + title_red.get_width() + title_gap
  start_x = (WIDTH - total_width) // 2

  canvas.blit(title_blue, (start_x, 15 + title_pulse // 3))
  canvas.blit(
      title_red,
      (start_x + title_blue.get_width() + title_gap, 15 + title_pulse // 3),
  )

  # --- Clickable top navigation ---
  mouse_pos = pygame.mouse.get_pos()
  ui_reset()

  nav_buttons = [
      # Colors pulled from this screen's own palette (title blue/red, the
      # settings screen's purple) instead of an unrelated orange/green/
      # purple trio, so the row reads as part of the same theme.
      ("menu_shop", "SHOP  [TAB]", COLOR_ORANGE, COLOR_YELLOW),
      ("menu_editor", "MAP EDITOR  [E]", COLOR_BLUE, COLOR_WHITE),
      ("menu_settings", "SETTINGS  [N]", COLOR_PURPLE, COLOR_WHITE),
      ("menu_online", "PLAY ONLINE  [O]", COLOR_GREEN, COLOR_WHITE),
  ]
  nav_w, nav_h, nav_gap = 175, 26, 12
  nav_total = len(nav_buttons) * nav_w + (len(nav_buttons) - 1) * nav_gap
  nav_x = (WIDTH - nav_total) // 2
  for nav_key, nav_label, nav_base, nav_hot in nav_buttons:
    nav_rect = pygame.Rect(nav_x, 60, nav_w, nav_h)
    # idle_strength softens these to a quiet outline until hovered, instead
    # of sitting at full neon brightness all the time.
    draw_button(canvas, nav_rect, nav_label, FONT_TINY, nav_base, nav_hot,
                mouse_pos, idle_strength=0.5)
    ui_register(nav_key, nav_rect)
    nav_x += nav_w + nav_gap

  board_rect = pygame.Rect(80, 90, 840, 360)
  board_bg = pygame.Surface((board_rect.width, board_rect.height), pygame.SRCALPHA)
  board_bg.fill((10, 10, 25, 200))
  canvas.blit(board_bg, board_rect.topleft)

  pygame.draw.rect(canvas, COLOR_BLUE, board_rect, 2)
  draw_neon_corners(
      canvas, board_rect, COLOR_BLUE, frame_count, corner_len=20, is_selected=False
  )

  center_labels = [
      "GAME MODE:",
      "BOT LEVEL:",
      "BALL SPEED:",
      "WIN SCORE:",
      "BACKGROUND:",
      "P1 COLOR:",
      "P2 COLOR:",
  ]
  bot_colors = [COLOR_GREEN, COLOR_YELLOW, COLOR_ORANGE, COLOR_RED, COLOR_PURPLE]
  active_bot_color = bot_colors[current_bot_level]
  if current_bot_level == 4 and frame_count % 10 < 5:
    active_bot_color = COLOR_WHITE

  bot_level_text = (
      f"< {BOT_LEVELS[current_bot_level]} >"
      if current_mode_index == 0
      else "< N/A >"
  )

  center_texts = [
      f"< {GAME_MODES[current_mode_index]} >",
      bot_level_text,
      f"< {SPEED_NAMES[current_speed_index]} >",
      f"< {SCORE_VALUES[current_score_index]} PTS >",
      f"< {BACKGROUND_TYPES[current_bg_index]} >",
      f"< {PALETTE[p1_color_idx][0]} >",
      f"< {PALETTE[p2_color_idx][0]} >",
  ]

  y_pos = 110
  for i in range(7):
    is_sel = menu_row_selected == i

    if i == 1 and current_mode_index == 1:
      val_color = COLOR_GRAY
      lbl_color = COLOR_GRAY
    else:
      lbl_color = COLOR_WHITE
      if is_sel:
        if i == 1:
          val_color = active_bot_color
        elif i == 5:
          val_color = p1_color
        elif i == 6:
          val_color = p2_color
        else:
          val_color = COLOR_ORANGE
      else:
        if i == 1:
          val_color = active_bot_color
        elif i == 5:
          val_color = p1_color
        elif i == 6:
          val_color = p2_color
        else:
          val_color = COLOR_WHITE

    lbl = FONT_SUBTITLE.render(center_labels[i], True, lbl_color)
    val = FONT_SUBTITLE.render(center_texts[i], True, val_color)

    lbl_rect = lbl.get_rect(midright=(WIDTH // 2 - 20, y_pos))
    val_rect = val.get_rect(midleft=(WIDTH // 2 + 20, y_pos))

    row_rect = pygame.Rect(WIDTH // 2 - 280, y_pos - 11, 560, 24)
    ui_register("menu_row_%d" % i, row_rect)
    ui_register("menu_val_%d" % i, val_rect)
    is_hot = row_rect.collidepoint(mouse_pos)

    if is_sel or is_hot:
      hover_surf = pygame.Surface((560, 24), pygame.SRCALPHA)
      hover_color = val_color if val_color != COLOR_WHITE else COLOR_BLUE
      hover_surf.fill((*hover_color, 40 if is_sel else 20))
      canvas.blit(hover_surf, row_rect.topleft)
      pygame.draw.line(
          canvas,
          hover_color,
          (row_rect.left, row_rect.bottom),
          (row_rect.right, row_rect.bottom),
          1,
      )

    canvas.blit(lbl, lbl_rect)
    canvas.blit(val, val_rect)
    y_pos += 26

  for player_num in [1, 2]:
    is_p1 = player_num == 1
    is_sel = menu_row_selected == (7 if is_p1 else 8)
    box_color = (p1_color if is_p1 else p2_color) if is_sel else COLOR_GRAY

    box_rect = pygame.Rect(95 if is_p1 else 525, 310, 380, 125)
    ui_register("menu_ability_p1" if is_p1 else "menu_ability_p2", box_rect)
    box_hot = box_rect.collidepoint(mouse_pos)
    if box_hot and not is_sel:
      box_color = COLOR_WHITE

    term_bg = pygame.Surface((box_rect.width, box_rect.height), pygame.SRCALPHA)
    term_bg.fill((15, 20, 30, 220))
    canvas.blit(term_bg, box_rect.topleft)
    pygame.draw.rect(canvas, box_color, box_rect, 3 if box_hot else 2)

    title_txt = "P1 ABILITY" if is_p1 else "P2 ABILITY"
    ab_idx = p1_ability_idx if is_p1 else p2_ability_idx
    ab_name = ABILITIES[ab_idx]
    cd = ABILITY_COOLDOWNS[ab_name]

    if cd > 0:
      if is_p1:
        cd_mult = max(0.2, 1.0 - (save_data["p1_upgrades"]["cd"] * 0.1))
        cd = int(cd * cd_mult)
      else:
        if current_mode_index == 1:
          cd_mult = max(0.2, 1.0 - (save_data["p2_upgrades"]["cd"] * 0.1))
          cd = int(cd * cd_mult)

    cd_str = "CD: NONE" if cd == 0 else f"CD: {cd // 60}s"
    hint_txt = (
        "[L-SHIFT]"
        if is_p1
        else (
            f"[BOT: {BOT_LEVELS[current_bot_level]}]"
            if current_mode_index == 0
            else "[R-SHIFT]"
        )
    )

    center_x = box_rect.centerx
    canvas.blit(
        FONT_TINY.render(title_txt, True, p1_color if is_p1 else p2_color),
        FONT_TINY.render(title_txt, True, COLOR_WHITE).get_rect(
            center=(center_x, 328)
        ),
    )
    canvas.blit(
        FONT_SMALL.render(f"< {ab_name} >", True, box_color),
        FONT_SMALL.render(f"< {ab_name} >", True, box_color).get_rect(
            center=(center_x, 355)
        ),
    )
    canvas.blit(
        FONT_TINY.render(cd_str, True, COLOR_WHITE),
        FONT_TINY.render(cd_str, True, COLOR_WHITE).get_rect(
            center=(center_x, 385)
        ),
    )
    canvas.blit(
        FONT_TINY.render(hint_txt, True, COLOR_GRAY),
        FONT_TINY.render(hint_txt, True, COLOR_GRAY).get_rect(
            center=(center_x, 412)
        ),
    )

    draw_neon_corners(
        canvas,
        box_rect,
        p1_color if is_p1 else p2_color,
        frame_count,
        corner_len=14,
        is_selected=is_sel,
    )

  start_rect = pygame.Rect(WIDTH // 2 - 250, 458, 500, 34)
  ui_register("menu_start", start_rect)
  if start_rect.collidepoint(mouse_pos):
    draw_button(
        canvas, start_rect, "> CLICK TO INITIALIZE MATCH <", FONT_ARCADE,
        COLOR_GREEN, COLOR_WHITE, mouse_pos,
    )
  elif (frame_count // 25) % 2 == 0:
    prompt_surf = FONT_ARCADE.render(
        "> PRESS SPACE TO INITIALIZE MATCH <", True, COLOR_WHITE
    )
    canvas.blit(prompt_surf, prompt_surf.get_rect(center=(WIDTH // 2, 475)))

  coins_display = FONT_TINY.render(
      f"WALLET: {save_data['coins']} COINS", True, COLOR_YELLOW
  )
  canvas.blit(coins_display, (20, HEIGHT - 25))

  ctrl_nav = FONT_TINY.render(
      "MOUSE: HOVER + CLICK / SCROLL TO CHANGE  |  KEYS: [UP/DOWN] [LEFT/RIGHT]",
      True,
      COLOR_YELLOW,
  )
  ctrl_p1 = FONT_TINY.render("P1: [W]/[S]", True, p1_color)
  ctrl_p2 = FONT_TINY.render(
      f"P2: BOT ({BOT_LEVELS[current_bot_level]})"
      if current_mode_index == 0
      else "P2: [UP]/[DOWN]",
      True,
      p2_color,
  )

  canvas.blit(ctrl_nav, ctrl_nav.get_rect(center=(WIDTH // 2, 510)))
  canvas.blit(ctrl_p1, ctrl_p1.get_rect(center=(WIDTH // 2 - 150, 545)))
  canvas.blit(ctrl_p2, ctrl_p2.get_rect(center=(WIDTH // 2 + 150, 545)))

  ui_sync_cursor()
  draw_scanlines(canvas)
  draw_fps_counter(canvas)
  ox = random.randint(-shake_intensity, shake_intensity) if shake_timer > 0 else 0
  oy = random.randint(-shake_intensity, shake_intensity) if shake_timer > 0 else 0
  surface.blit(canvas, (ox, oy))


def game_loop():
  ui_reset()
  ui_sync_cursor()
  global shake_timer, current_mode_index, current_bot_level, save_data
  run = True
  score_p1 = 0
  score_p2 = 0
  max_score = SCORE_VALUES[current_score_index]
  frame_count = 0

  p1_color = PALETTE[p1_color_idx][1]
  p2_color = PALETTE[p2_color_idx][1]

  player_one.set_color(p1_color)
  player_two.set_color(p2_color)

  upg_speed_p1 = save_data["p1_upgrades"]["speed"]
  upg_cd_mult_p1 = max(0.2, 1.0 - (save_data["p1_upgrades"]["cd"] * 0.1))
  upg_size_p1 = save_data["p1_upgrades"]["size"] * 8

  if current_mode_index == 1:
    upg_speed_p2 = save_data["p2_upgrades"]["speed"]
    upg_cd_mult_p2 = max(0.2, 1.0 - (save_data["p2_upgrades"]["cd"] * 0.1))
    upg_size_p2 = save_data["p2_upgrades"]["size"] * 8
  else:
    upg_speed_p2 = 0
    upg_cd_mult_p2 = 1.0
    upg_size_p2 = 0

  base_p1_size = 100 + upg_size_p1
  base_p2_size = 100 + upg_size_p2

  player_one.set_height(base_p1_size)
  player_two.set_height(base_p2_size)
  make_solid_paddle(player_one, p1_color)
  make_solid_paddle(player_two, p2_color)

  p1_cd, p2_cd = 0.0, 0.0
  p1_giant, p2_giant = 0.0, 0.0
  p1_speed_buff, p2_speed_buff = 0.0, 0.0
  p1_freeze, p2_freeze = 0.0, 0.0
  p1_auto, p2_auto = 0.0, 0.0
  p1_shield, p2_shield = False, False

  game_over = False
  winner_text = ""
  winner_color = COLOR_WHITE
  sub_text = ""
  payout = 0
  payout_calculated = False

  ball.set_speed(SPEED_VALUES[current_speed_index])
  ball.reset()
  ball.color = (255, 255, 255)

  active_balls = [ball]

  player_one.rect.x = 26
  player_two.rect.x = WIDTH - 26 - player_two.rect.width
  player_one.rect.y = (HEIGHT - player_one.rect.height) // 2
  player_two.rect.y = (HEIGHT - player_two.rect.height) // 2

  round_countdown = 120.0

  # --- FIXED TIMESTEP CONFIGURATION (LIKE MINECRAFT'S 20 TPS TICK RATE) ---
  # Game logic / physics update exactly 60 times per second, independent of monitor refresh rate.
  PHYSICS_TPS = 60.0
  TIME_STEP = 1.0 / PHYSICS_TPS
  accumulator = 0.0

  def apply_ability(player_num, ab_name):
    nonlocal p1_giant, p2_giant, p1_speed_buff, p2_speed_buff, p1_freeze, p2_freeze
    nonlocal p1_shield, p2_shield, p1_auto, p2_auto, active_balls

    target_player = player_one if player_num == 1 else player_two
    target_player.trigger_ability_animation()
    trigger_shake(15, 4)

    if ab_name == "GIANT PADDLE":
      if player_num == 1:
        p1_giant = 300.0
      else:
        p2_giant = 300.0
    elif ab_name == "FAST PADDLE":
      if player_num == 1:
        p1_speed_buff = 300.0
      else:
        p2_speed_buff = 300.0
    elif ab_name == "FREEZE ENEMY":
      if player_num == 1:
        p2_freeze = 180.0
      else:
        p1_freeze = 180.0
    elif ab_name == "SHIELD":
      if player_num == 1:
        p1_shield = True
      else:
        p2_shield = True
    elif ab_name == "BULLET BALL":
      for b in active_balls:
        b.dx = 22 if b.dx > 0 else -22
        b.bullet_active = True
    elif ab_name == "GHOST BALL":
      for b in active_balls:
        b.ghost_timer = 90.0
    elif ab_name == "CURVY BALL":
      for b in active_balls:
        b.curvy_active = True
        b.curvy_timer = 200.0
    elif ab_name == "TIME SLOW":
      if player_num == 1:
        p2_freeze = 240.0
      else:
        p1_freeze = 240.0
    elif ab_name == "AUTO PLAY":
      if player_num == 1:
        p1_auto = 360.0
      else:
        p2_auto = 360.0
    elif ab_name == "MULTIBALL":
      b1 = Ball(WIDTH, HEIGHT)
      b1.set_speed(ball.speed)
      b1.reset()
      b1.dx = -ball.dx * 0.9
      b1.dy = ball.dy * 1.3
      b1.color = (50, 255, 100)

      b2 = Ball(WIDTH, HEIGHT)
      b2.set_speed(ball.speed)
      b2.reset()
      b2.dx = ball.dx * 1.2
      b2.dy = -ball.dy * 0.9
      b2.color = (173, 255, 47)
      active_balls.extend([b1, b2])

  while run:
    tick_limit = save_data.get("target_fps", 240)
    dt_ms = clock.tick(tick_limit)
    dt = dt_ms / 1000.0
    if dt > 0.2:
      dt = 0.2

    accumulator += dt
    dts = 1.0  # 1 tick step inside the fixed physics loop

    for event in pygame.event.get():
      if event.type == pygame.QUIT:
        return False
      if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
        return True

    keys = pygame.key.get_pressed()

    # --- FIXED PHYSICS TICK LOOP (DECOUPLED FROM RENDER FPS) ---
    while accumulator >= TIME_STEP:
      accumulator -= TIME_STEP

      if not game_over:
        if round_countdown > 0:
          round_countdown -= dts
          if round_countdown < 0:
            round_countdown = 0
        else:
          ab1 = ABILITIES[p1_ability_idx]
          if keys[pygame.K_LSHIFT] and p1_cd <= 0 and ab1 != "NONE":
            apply_ability(1, ab1)
            p1_cd = float(int(ABILITY_COOLDOWNS[ab1] * upg_cd_mult_p1))

          ab2 = ABILITIES[p2_ability_idx]
          human_trigger_p2 = keys[pygame.K_RSHIFT] and current_mode_index == 1
          bot_trigger_p2 = False

          incoming = [b for b in active_balls if b.dx > 0]
          if incoming:
            target_ball = max(incoming, key=lambda b: b.rect.x)
          else:
            target_ball = min(
                active_balls,
                key=lambda b: abs(b.rect.centerx - player_two.rect.centerx),
            )

          if current_mode_index == 0 and p2_cd <= 0 and ab2 != "NONE":
            dist_to_p2 = WIDTH - target_ball.rect.right
            ball_coming = target_ball.dx > 0
            ball_leaving = target_ball.dx < 0
            should_trigger_bot = False

            if current_bot_level == 0:
              should_trigger_bot = random.random() < (0.001 * dts)
            elif current_bot_level == 1:
              if ab2 == "SHIELD" and ball_coming and dist_to_p2 < 90:
                should_trigger_bot = True
              elif ab2 == "FREEZE ENEMY" and ball_leaving:
                should_trigger_bot = True
              elif random.random() < (0.003 * dts):
                should_trigger_bot = True
            else:
              if (
                  ab2 == "SHIELD"
                  and ball_coming
                  and dist_to_p2 < 110
                  and not p2_shield
              ):
                should_trigger_bot = True
              elif (
                  ab2 == "BULLET BALL"
                  and ball_leaving
                  and target_ball.rect.x > WIDTH // 2
              ):
                should_trigger_bot = True
              elif (
                  ab2 == "MULTIBALL" and ball_leaving and current_bot_level >= 3
              ):
                should_trigger_bot = True
              elif ab2 == "FREEZE ENEMY" and ball_leaving:
                should_trigger_bot = True
              elif ab2 == "TIME SLOW" and ball_coming and dist_to_p2 < 180:
                should_trigger_bot = True
              elif ab2 == "GIANT PADDLE" and ball_coming and dist_to_p2 < 150:
                should_trigger_bot = True
              elif ab2 == "CURVY BALL" and ball_coming:
                should_trigger_bot = True
              else:
                if random.random() < (0.005 * (current_bot_level + 1) * dts):
                  should_trigger_bot = True

            if should_trigger_bot:
              bot_trigger_p2 = True

          if (
              (human_trigger_p2 or bot_trigger_p2)
              and p2_cd <= 0
              and ab2 != "NONE"
          ):
            apply_ability(2, ab2)
            p2_cd = float(int(ABILITY_COOLDOWNS[ab2] * upg_cd_mult_p2))

          if p1_cd > 0:
            p1_cd -= dts
            if p1_cd < 0:
              p1_cd = 0.0
          if p2_cd > 0:
            p2_cd -= dts
            if p2_cd < 0:
              p2_cd = 0.0

          player_one.set_height(
              (200 + upg_size_p1) if p1_giant > 0 else base_p1_size
          )
          player_two.set_height(
              (200 + upg_size_p2) if p2_giant > 0 else base_p2_size
          )
          make_solid_paddle(player_one, p1_color)
          make_solid_paddle(player_two, p2_color)

          if p1_giant > 0:
            p1_giant -= dts
            if p1_giant < 0:
              p1_giant = 0.0
          if p2_giant > 0:
            p2_giant -= dts
            if p2_giant < 0:
              p2_giant = 0.0

          p1_active_spd = (
              (9 + upg_speed_p1) if p1_speed_buff > 0 else (5 + upg_speed_p1)
          )
          p2_active_spd = (
              (9 + upg_speed_p2) if p2_speed_buff > 0 else (5 + upg_speed_p2)
          )

          if p1_freeze > 0:
            p1_active_spd = 2
          if p2_freeze > 0:
            p2_active_spd = 2

          player_one.speed = p1_active_spd
          player_two.speed = p2_active_spd

          if p1_speed_buff > 0:
            p1_speed_buff -= dts
            if p1_speed_buff < 0:
              p1_speed_buff = 0.0
          if p2_speed_buff > 0:
            p2_speed_buff -= dts
            if p2_speed_buff < 0:
              p2_speed_buff = 0.0
          if p1_freeze > 0:
            p1_freeze -= dts
            if p1_freeze < 0:
              p1_freeze = 0.0
          if p2_freeze > 0:
            p2_freeze -= dts
            if p2_freeze < 0:
              p2_freeze = 0.0

          player_one.update()
          player_one.rect.y = max(
              0, min(HEIGHT - player_one.rect.height, player_one.rect.y)
          )

          if current_mode_index == 1:
            player_two.update()
            player_two.rect.y = max(
                0, min(HEIGHT - player_two.rect.height, player_two.rect.y)
            )

          make_solid_paddle(player_one, p1_color)
          make_solid_paddle(player_two, p2_color)

          if current_mode_index == 0:
            bot_speed = 0
            target_y = player_two.rect.centery

            if target_ball.dx > 0:
              if current_bot_level == 0:
                target_y = target_ball.rect.centery + math.sin(
                    frame_count * 0.03
                ) * 90
                bot_speed = 3.5
              elif current_bot_level == 1:
                target_y = target_ball.rect.centery + math.sin(
                    frame_count * 0.1
                ) * 25
                bot_speed = 5.5
              elif current_bot_level >= 2:
                frames_to_reach = (
                    player_two.rect.left - target_ball.rect.right
                ) / target_ball.dx
                predicted_y = target_ball.rect.centery + (
                    target_ball.dy * frames_to_reach
                )
                bounce_y = predicted_y
                while bounce_y < 0 or bounce_y > HEIGHT:
                  if bounce_y < 0:
                    bounce_y = -bounce_y
                  elif bounce_y > HEIGHT:
                    bounce_y = 2 * HEIGHT - bounce_y

                if current_bot_level == 2:
                  target_y = bounce_y + math.sin(frame_count * 0.2) * 15
                  bot_speed = 7.5
                elif current_bot_level == 3:
                  target_y = bounce_y
                  bot_speed = 12.0
                elif current_bot_level == 4:
                  target_y = bounce_y
                  bot_speed = 22.0
            else:
              if current_bot_level >= 3:
                target_y = HEIGHT // 2
                bot_speed = 5.0
              else:
                target_y = player_two.rect.centery
                bot_speed = 0.0

            if p2_freeze > 0:
              bot_speed = min(bot_speed, 2)

            diff = target_y - player_two.rect.centery
            move_step = min(abs(diff), bot_speed * dts)
            if diff > 0:
              player_two.rect.y += move_step
            elif diff < 0:
              player_two.rect.y -= move_step

            player_two.rect.y = max(
                0, min(HEIGHT - player_two.rect.height, player_two.rect.y)
            )

          if p1_auto > 0:
            p1_auto -= dts
            if p1_auto < 0:
              p1_auto = 0.0
            player_one.rect.y = max(
                0,
                min(
                    HEIGHT - player_one.rect.height,
                    target_ball.rect.centery - player_one.rect.height // 2,
                ),
            )
          if p2_auto > 0:
            p2_auto -= dts
            if p2_auto < 0:
              p2_auto = 0.0
            player_two.rect.y = max(
                0,
                min(
                    HEIGHT - player_two.rect.height,
                    target_ball.rect.centery - player_two.rect.height // 2,
                ),
            )

          scored_side = None
          shield_event = None

          for b in active_balls[:]:
            scorer = b.update(player_one, player_two, p1_shield, p2_shield)

            if hasattr(b, "ghost_timer") and b.ghost_timer > 0:
              b.ghost_timer += (1.0 - dts)
              if b.ghost_timer < 0:
                b.ghost_timer = 0.0
            if hasattr(b, "curvy_timer") and b.curvy_timer > 0 and getattr(b, "curvy_active", False):
              b.curvy_timer += (1.0 - dts)
              if b.curvy_timer < 0:
                b.curvy_timer = 0.0
                b.curvy_active = False

            if hasattr(b, "color") and hasattr(b, "image"):
              b.image.fill(b.color)

            b_rect = pygame.Rect(
                b.rect.centerx - 10, b.rect.centery - 10, 20, 20
            )
            for obj in custom_map_objects:
              obj_rect = pygame.Rect(obj["x"], obj["y"], obj["w"], obj["h"])
              if b_rect.colliderect(obj_rect):
                if obj["type"] == "wall":
                  b.dx *= -1
                  b.dy *= -1
                elif obj["type"] == "spike":
                  trigger_shake(20, 5)
                  scorer = "P2" if b.dx > 0 else "P1"
                elif obj["type"] == "powerup":
                  b.dx *= 1.25
                  custom_map_objects.remove(obj)
                  break

            if scorer == "P1_SHIELD_BREAK":
              shield_event = "P1_SHIELD_BREAK"
              p1_shield = False
            elif scorer == "P2_SHIELD_BREAK":
              shield_event = "P2_SHIELD_BREAK"
              p2_shield = False
            elif scorer == "P1":
              scored_side = "P1"
            elif scorer == "P2":
              scored_side = "P2"

          event_result = shield_event if shield_event else scored_side
          if event_result in ["P1", "P2"]:
            trigger_shake(25, 6)
            if event_result == "P1":
              score_p1 += 1
            else:
              score_p2 += 1

            active_balls = [ball]
            ball.reset()
            ball.color = (255, 255, 255)
            if hasattr(ball, "image"):
              ball.image.fill(ball.color)

            p1_shield, p2_shield = False, False
            p1_auto, p2_auto = 0.0, 0.0
            player_one.set_height(base_p1_size)
            player_two.set_height(base_p2_size)
            make_solid_paddle(player_one, p1_color)
            make_solid_paddle(player_two, p2_color)

            player_one.rect.y = (HEIGHT - player_one.rect.height) // 2
            player_two.rect.y = (HEIGHT - player_two.rect.height) // 2
            round_countdown = 120.0
          elif event_result in ["P1_SHIELD_BREAK", "P2_SHIELD_BREAK"]:
            trigger_shake(25, 6)

          if score_p1 >= max_score or score_p2 >= max_score:
            game_over = True
            multiplier = 1.0 + (save_data["p1_upgrades"]["mult"] * 0.5)

            if score_p1 >= max_score:
              winner_text, winner_color = "PLAYER 1 WINS!", p1_color
              if current_mode_index == 0:
                sub_text = (
                    "You broke the matrix!"
                    if current_bot_level >= 3
                    else "Easy victory!"
                )
                payout = int(
                    (10 * (current_bot_level + 1) * (current_score_index + 1))
                    * multiplier
                )
              else:
                sub_text = "Player 1 dominates!"
                payout = int(15 * multiplier)
            else:
              if current_mode_index == 0:
                winner_text, winner_color = (
                    f"BOT ({BOT_LEVELS[current_bot_level]}) WINS!",
                    p2_color,
                )
                sub_text = (
                    "The AI mathematically destroyed you."
                    if current_bot_level >= 3
                    else "Better luck next time!"
                )
                payout = int((2 * (current_bot_level + 1)) * multiplier)
              else:
                winner_text, winner_color = "PLAYER 2 WINS!", p2_color
                sub_text = "Player 2 destroyed Player 1!"
                payout = int(5 * multiplier)

        if game_over and not payout_calculated:
          save_data["coins"] += payout
          write_save()
          payout_calculated = True

      # --- COSMETIC TIMERS ON THE FIXED 60 TPS TICK ---
      # These used to advance once per rendered frame, which made the
      # background, ball trail and screen shake run 4x faster at 240 FPS
      # than at 60 FPS. Ticking them here keeps visual speed constant.
      frame_count += 1

      ball_particles.append([ball.rect.centerx, ball.rect.centery, 180])
      for p in ball_particles[:]:
        p[2] -= 15
        if p[2] <= 0:
          ball_particles.remove(p)

      if shake_timer > 0:
        shake_timer -= 1
        if shake_timer < 0:
          shake_timer = 0.0

    canvas = pygame.Surface((WIDTH, HEIGHT))
    draw_background(canvas, frame_count)

    for obj in custom_map_objects:
      if obj["type"] == "wall":
        col = COLOR_WHITE
      elif obj["type"] == "spike":
        col = COLOR_RED
      else:
        col = COLOR_YELLOW
      pygame.draw.rect(canvas, col, (obj["x"], obj["y"], obj["w"], obj["h"]))

    for y in range(0, HEIGHT, 30):
      pygame.draw.rect(canvas, (50, 50, 90), (WIDTH // 2 - 1, y, 2, 15))

    if p1_shield:
      pygame.draw.line(canvas, p1_color, (4, 0), (4, HEIGHT), 4)
    if p2_shield:
      pygame.draw.line(canvas, p2_color, (WIDTH - 4, 0), (WIDTH - 4, HEIGHT), 4)

    if not game_over:
      for p in ball_particles:
        p_alpha = max(0, min(255, p[2]))
        p_surf = pygame.Surface((8, 8), pygame.SRCALPHA)
        pygame.draw.circle(p_surf, (255, 220, 0, p_alpha), (4, 4), 3)
        canvas.blit(p_surf, (p[0] - 4, p[1] - 4))

      make_solid_paddle(player_one, p1_color)
      make_solid_paddle(player_two, p2_color)
      paddles_group.draw(canvas)
      for b in active_balls:
        canvas.blit(b.image, b.rect)

      if round_countdown > 0:
        cd_sec = math.ceil(round_countdown / 60)
        ready_surf = FONT_SUBTITLE.render("GET READY!", True, COLOR_WHITE)
        cd_surf = FONT_TITLE.render(str(cd_sec), True, COLOR_YELLOW)
        canvas.blit(
            ready_surf,
            ready_surf.get_rect(center=(WIDTH // 2, HEIGHT // 2 - 40)),
        )
        canvas.blit(
            cd_surf, cd_surf.get_rect(center=(WIDTH // 2, HEIGHT // 2 + 15))
        )

      p1_cd_text = "READY!" if p1_cd <= 0 else f"{math.ceil(p1_cd / 60)}s"
      p2_cd_text = "READY!" if p2_cd <= 0 else f"{math.ceil(p2_cd / 60)}s"
      canvas.blit(
          FONT_SMALL.render(f"P1 ABILITY: {p1_cd_text}", True, p1_color),
          (20, HEIGHT - 25),
      )

      p2_disp_text = (
          f"BOT ABILITY: {p2_cd_text}"
          if current_mode_index == 0
          else f"P2 ABILITY: {p2_cd_text}"
      )
      p2_surf = FONT_SMALL.render(p2_disp_text, True, p2_color)
      canvas.blit(p2_surf, (WIDTH - p2_surf.get_width() - 20, HEIGHT - 25))

    else:
      win_surf = FONT_TITLE.render(winner_text, True, winner_color)
      canvas.blit(
          win_surf, win_surf.get_rect(center=(WIDTH // 2, HEIGHT // 2 - 70))
      )

      sub_surf = FONT_SUBTITLE.render(sub_text, True, COLOR_WHITE)
      canvas.blit(
          sub_surf, sub_surf.get_rect(center=(WIDTH // 2, HEIGHT // 2 - 20))
      )

      payout_surf = FONT_ARCADE.render(f"+ {payout} COINS", True, COLOR_YELLOW)
      canvas.blit(
          payout_surf, payout_surf.get_rect(center=(WIDTH // 2, HEIGHT // 2 + 25))
      )

      restart_surf = FONT_ARCADE.render(
          "PRESS ESC TO RETURN TO MENU", True, COLOR_ORANGE
      )
      canvas.blit(
          restart_surf,
          restart_surf.get_rect(center=(WIDTH // 2, HEIGHT // 2 + 75)),
      )

    score_surf = FONT_SCORE.render(
        f"{score_p1}      {score_p2}", True, COLOR_WHITE
    )
    canvas.blit(score_surf, score_surf.get_rect(center=(WIDTH // 2, 35)))

    draw_scanlines(canvas)
    draw_fps_counter(canvas)

    ox = random.randint(-shake_intensity, shake_intensity) if shake_timer > 0 else 0
    oy = random.randint(-shake_intensity, shake_intensity) if shake_timer > 0 else 0

    screen.blit(canvas, (ox, oy))
    pygame.display.flip()

  return False


def main():
  global current_mode_index, current_bot_level, current_speed_index, current_score_index
  global current_bg_index, p1_color_idx, p2_color_idx, p1_ability_idx, p2_ability_idx
  global menu_row_selected, shop_row_selected, shop_player_view, settings_row_selected, save_data
  global custom_map_objects, editor_tool, screen

  state = "MENU"
  running = True
  frame_count = 0

  transition_frame = 0
  total_transition_duration = 200
  slash_duration = 10
  split_duration = 20
  transition_snapshot = None

  if os.path.exists(MAP_FILE):
    try:
      with open(MAP_FILE, "r") as f:
        custom_map_objects = json.load(f)
    except:
      pass

  while running:
    # Real-time animation clock (60 units/sec) so menu animations run at the
    # same speed regardless of the render FPS cap.
    frame_count = pygame.time.get_ticks() * 60 // 1000

    if state == "MENU":
      draw_arcade_menu(screen, frame_count)
      pygame.display.flip()

      for event in pygame.event.get():
        if event.type == pygame.QUIT:
          running = False

        elif event.type == pygame.MOUSEMOTION:
          # Hovering a row selects it, so the keyboard cursor follows the mouse.
          for i in range(7):
            if ui_click("menu_row_%d" % i, event.pos):
              if not (i == 1 and current_mode_index == 1):
                menu_row_selected = i
          if ui_click("menu_ability_p1", event.pos):
            menu_row_selected = 7
          elif ui_click("menu_ability_p2", event.pos):
            menu_row_selected = 8

        elif event.type == pygame.MOUSEWHEEL:
          # Scroll over a row to cycle its value; scroll elsewhere to move rows.
          hovered = None
          for i in range(7):
            if ui_hover("menu_row_%d" % i):
              hovered = i
          if ui_hover("menu_ability_p1"):
            hovered = 7
          elif ui_hover("menu_ability_p2"):
            hovered = 8

          if hovered is not None:
            apply_menu_change(hovered, 1 if event.y > 0 else -1)
          else:
            step = -1 if event.y > 0 else 1
            menu_row_selected = (menu_row_selected + step) % 9
            if menu_row_selected == 1 and current_mode_index == 1:
              menu_row_selected = (menu_row_selected + step) % 9

        elif event.type == pygame.MOUSEBUTTONDOWN and event.button in (1, 3):
          if ui_click("menu_shop", event.pos):
            state = "SHOP"
            shop_row_selected = 0
            shop_player_view = 1
          elif ui_click("menu_editor", event.pos):
            state = "EDITOR"
          elif ui_click("menu_settings", event.pos):
            state = "SETTINGS"
            settings_row_selected = 0
          elif ui_click("menu_online", event.pos):
            if net_state["logged_in"] and net.connected:
              state = "ONLINE_LOBBY"
            else:
              state = "ONLINE_AUTH"
              if not net.connected:
                start_connect()
          elif ui_click("menu_start", event.pos):
            transition_snapshot = screen.copy()
            transition_frame = 0
            state = "TRANSITION"
          else:
            hit_row = None
            for i in range(7):
              if ui_click("menu_row_%d" % i, event.pos):
                hit_row = i
            if hit_row is None and ui_click("menu_ability_p1", event.pos):
              hit_row = 7
            if hit_row is None and ui_click("menu_ability_p2", event.pos):
              hit_row = 8

            if hit_row is not None and not (hit_row == 1 and current_mode_index == 1):
              menu_row_selected = hit_row
              # Left-click: left half decrements, right half increments.
              # Right-click: always decrement.
              if event.button == 3:
                direction = -1
              elif hit_row == 7:
                direction = ui_side("menu_ability_p1", event.pos)
              elif hit_row == 8:
                direction = ui_side("menu_ability_p2", event.pos)
              else:
                direction = ui_side("menu_val_%d" % hit_row, event.pos)
              apply_menu_change(hit_row, direction)

        elif event.type == pygame.KEYDOWN:
          if event.key == pygame.K_TAB:
            state = "SHOP"
            shop_row_selected = 0
            shop_player_view = 1
          elif event.key == pygame.K_e:
            state = "EDITOR"
          elif event.key == pygame.K_n:
            state = "SETTINGS"
            settings_row_selected = 0
          elif event.key == pygame.K_o:
            if net_state["logged_in"] and net.connected:
              state = "ONLINE_LOBBY"
            else:
              state = "ONLINE_AUTH"
              if not net.connected:
                start_connect()
          elif event.key in (pygame.K_UP, pygame.K_w):
            menu_row_selected = (menu_row_selected - 1) % 9
            if menu_row_selected == 1 and current_mode_index == 1:
              menu_row_selected = 0
          elif event.key in (pygame.K_DOWN, pygame.K_s):
            menu_row_selected = (menu_row_selected + 1) % 9
            if menu_row_selected == 1 and current_mode_index == 1:
              menu_row_selected = 2
          elif event.key in (pygame.K_RIGHT, pygame.K_d):
            apply_menu_change(menu_row_selected, 1)
          elif event.key in (pygame.K_LEFT, pygame.K_a):
            apply_menu_change(menu_row_selected, -1)
          elif event.key in (pygame.K_SPACE, pygame.K_RETURN):
            transition_snapshot = screen.copy()
            transition_frame = 0
            state = "TRANSITION"
          elif event.key in (pygame.K_q, pygame.K_ESCAPE):
            running = False

    elif state == "SHOP":
      draw_shop(screen, frame_count)
      pygame.display.flip()

      for event in pygame.event.get():
        if event.type == pygame.QUIT:
          running = False

        elif event.type == pygame.MOUSEMOTION:
          for i in range(shop_item_count()):
            if ui_click("shop_row_%d" % i, event.pos):
              shop_row_selected = i

        elif event.type == pygame.MOUSEWHEEL:
          shop_row_selected = (shop_row_selected - event.y) % shop_item_count()

        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
          if ui_click("shop_back", event.pos):
            state = "MENU"
          elif ui_click("shop_tab_p1", event.pos):
            shop_player_view = 1
            shop_row_selected = 0
          elif ui_click("shop_tab_p2", event.pos):
            shop_player_view = 2
            shop_row_selected = 0
          else:
            for i in range(shop_item_count()):
              if ui_click("shop_row_%d" % i, event.pos):
                shop_row_selected = i
                try_buy_upgrade()
                break

        elif event.type == pygame.KEYDOWN:
          if event.key in (pygame.K_ESCAPE, pygame.K_TAB):
            state = "MENU"
          elif event.key in (
              pygame.K_LEFT,
              pygame.K_a,
              pygame.K_RIGHT,
              pygame.K_d,
          ):
            shop_player_view = 2 if shop_player_view == 1 else 1
            shop_row_selected = 0
          elif event.key in (pygame.K_UP, pygame.K_w):
            shop_row_selected = (shop_row_selected - 1) % shop_item_count()
          elif event.key in (pygame.K_DOWN, pygame.K_s):
            shop_row_selected = (shop_row_selected + 1) % shop_item_count()
          elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
            try_buy_upgrade()

    elif state == "SETTINGS":
      draw_settings(screen, frame_count)
      pygame.display.flip()

      for event in pygame.event.get():
        if event.type == pygame.QUIT:
          running = False

        elif event.type == pygame.MOUSEMOTION:
          for i in range(5):
            if ui_click("settings_row_%d" % i, event.pos):
              settings_row_selected = i

        elif event.type == pygame.MOUSEWHEEL:
          hovered = None
          for i in range(5):
            if ui_hover("settings_row_%d" % i):
              hovered = i
              break
          # Scrolling adjusts the numeric rows (volume, FPS cap). On toggle rows
          # it only moves the selection, so the window isn't rebuilt per notch.
          if hovered in (1, 4):
            settings_row_selected = hovered
            apply_setting_change(hovered, 1 if event.y > 0 else -1)
          else:
            settings_row_selected = (settings_row_selected - event.y) % 5

        elif event.type == pygame.MOUSEBUTTONDOWN and event.button in (1, 3):
          if ui_click("settings_back", event.pos):
            state = "MENU"
          else:
            for i in range(5):
              if ui_click("settings_row_%d" % i, event.pos):
                settings_row_selected = i
                if event.button == 3:
                  direction = -1
                else:
                  direction = ui_side("settings_val_%d" % i, event.pos)
                apply_setting_change(i, direction)
                break

        elif event.type == pygame.KEYDOWN:
          if event.key == pygame.K_ESCAPE:
            state = "MENU"
          elif event.key in (pygame.K_UP, pygame.K_w):
            settings_row_selected = (settings_row_selected - 1) % 5
          elif event.key in (pygame.K_DOWN, pygame.K_s):
            settings_row_selected = (settings_row_selected + 1) % 5
          elif event.key in (pygame.K_RIGHT, pygame.K_d, pygame.K_LEFT, pygame.K_a):
            direction = 1 if event.key in (pygame.K_RIGHT, pygame.K_d) else -1
            apply_setting_change(settings_row_selected, direction)

    elif state == "ONLINE_AUTH":
      net_process_incoming()
      draw_online_auth(screen, frame_count)
      pygame.display.flip()

      for event in pygame.event.get():
        if event.type == pygame.QUIT:
          running = False

        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
          if ui_click("auth_back", event.pos):
            if not net_state["logged_in"]:
              net.disconnect()
            state = "MENU"
          elif ui_click("auth_user", event.pos):
            focus_only(net_fields["user"])
          elif ui_click("auth_pass", event.pos):
            focus_only(net_fields["pass"])
          elif ui_click("auth_mode_login", event.pos):
            net_state["auth_mode"] = "login"
          elif ui_click("auth_mode_register", event.pos):
            net_state["auth_mode"] = "register"
          elif ui_click("auth_submit", event.pos):
            try_auth_submit()
          elif ui_click("auth_retry", event.pos):
            start_connect()

        elif event.type == pygame.KEYDOWN:
          if event.key == pygame.K_ESCAPE:
            if not net_state["logged_in"]:
              net.disconnect()
            state = "MENU"
          elif event.key == pygame.K_TAB:
            cycle_focus(["user", "pass"])
          else:
            r1 = net_fields["user"].handle_key(event)
            r2 = net_fields["pass"].handle_key(event)
            if r1 == "submit" or r2 == "submit":
              try_auth_submit()

      if net_state["logged_in"]:
        state = "ONLINE_LOBBY"

    elif state == "ONLINE_LOBBY":
      net_process_incoming()
      if not net.connected:
        net_state["logged_in"] = False
        state = "ONLINE_AUTH"
        if not net.connect_error:
          net.connect_error = "Lost connection to the server."
        continue

      draw_online_lobby(screen, frame_count)
      pygame.display.flip()

      for event in pygame.event.get():
        if event.type == pygame.QUIT:
          running = False

        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
          if ui_click("lobby_back", event.pos):
            state = "MENU"
          elif ui_click("lobby_logout", event.pos):
            net_logout()
            state = "MENU"
          elif ui_click("lobby_add_friend_field", event.pos):
            focus_only(net_fields["friend"])
          elif ui_click("lobby_add_friend_btn", event.pos):
            submit_add_friend()
          elif ui_click("lobby_chat_field", event.pos):
            focus_only(net_fields["chat"])
          elif ui_click("lobby_chat_send", event.pos):
            submit_chat()
          elif ui_click("lobby_coins_field", event.pos):
            focus_only(net_fields["coins"])
          elif ui_click("lobby_coins_send", event.pos):
            submit_coins()
          elif ui_click("lobby_challenge", event.pos):
            if net_state["chat_target"]:
              net.send({"type": "challenge_send", "to": net_state["chat_target"]})
          else:
            for f in net_state["friends"]:
              uname = f["username"]
              if f["status"] == "accepted" and ui_click("lobby_friend_" + uname, event.pos):
                open_chat_with(uname)
              elif f["status"] == "incoming" and ui_click("lobby_accept_" + uname, event.pos):
                net.send({"type": "friend_respond", "from": uname, "accept": True})
              elif f["status"] == "incoming" and ui_click("lobby_decline_" + uname, event.pos):
                net.send({"type": "friend_respond", "from": uname, "accept": False})

        elif event.type == pygame.KEYDOWN:
          if event.key == pygame.K_ESCAPE:
            state = "MENU"
          elif event.key == pygame.K_TAB:
            cycle_focus(["friend", "chat", "coins"])
          else:
            for key, submit_fn in (("friend", submit_add_friend), ("chat", submit_chat),
                                    ("coins", submit_coins)):
              if net_fields[key].handle_key(event) == "submit":
                submit_fn()

    elif state == "EDITOR":
      draw_map_editor(screen, frame_count)
      pygame.display.flip()

      mx, my = pygame.mouse.get_pos()
      mouse_btns = pygame.mouse.get_pressed()
      
      if my > 40:
        gx = (mx // GRID_SIZE) * GRID_SIZE
        gy = (my // GRID_SIZE) * GRID_SIZE
        
        if mouse_btns[0]:
          if editor_tool == "eraser":
            custom_map_objects = [o for o in custom_map_objects if not (gx >= o["x"] and gx < o["x"] + o["w"] and gy >= o["y"] and gy < o["y"] + o["h"])]
          else:
            if not any(o["x"] == gx and o["y"] == gy for o in custom_map_objects):
              custom_map_objects.append({"type": editor_tool, "x": gx, "y": gy, "w": GRID_SIZE, "h": GRID_SIZE})
        elif mouse_btns[2]:
          custom_map_objects = [o for o in custom_map_objects if not (gx >= o["x"] and gx < o["x"] + o["w"] and gy >= o["y"] and gy < o["y"] + o["h"])]

      for event in pygame.event.get():
        if event.type == pygame.QUIT:
          running = False
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
          if ui_click("editor_tool_wall", event.pos):
            editor_tool = "wall"
          elif ui_click("editor_tool_spike", event.pos):
            editor_tool = "spike"
          elif ui_click("editor_tool_powerup", event.pos):
            editor_tool = "powerup"
          elif ui_click("editor_tool_eraser", event.pos):
            editor_tool = "eraser"
          elif ui_click("editor_save", event.pos):
            with open(MAP_FILE, "w") as f:
              json.dump(custom_map_objects, f)
            print("Map successfully saved!")
          elif ui_click("editor_load", event.pos):
            if os.path.exists(MAP_FILE):
              with open(MAP_FILE, "r") as f:
                custom_map_objects = json.load(f)
              print("Map loaded successfully!")
          elif ui_click("editor_play", event.pos):
            transition_snapshot = screen.copy()
            transition_frame = 0
            state = "TRANSITION"
          elif ui_click("editor_menu", event.pos):
            state = "MENU"
        elif event.type == pygame.KEYDOWN:
          if event.key == pygame.K_1: editor_tool = "wall"
          elif event.key == pygame.K_2: editor_tool = "spike"
          elif event.key == pygame.K_3: editor_tool = "powerup"
          elif event.key == pygame.K_4: editor_tool = "eraser"
          elif event.key == pygame.K_s:
            with open(MAP_FILE, "w") as f:
              json.dump(custom_map_objects, f)
            print("Map successfully saved!")
          elif event.key == pygame.K_l:
            if os.path.exists(MAP_FILE):
              with open(MAP_FILE, "r") as f:
                custom_map_objects = json.load(f)
              print("Map loaded successfully!")
          elif event.key == pygame.K_p:
            transition_snapshot = screen.copy()
            transition_frame = 0
            state = "TRANSITION"
          elif event.key == pygame.K_ESCAPE:
            state = "MENU"

    elif state == "TRANSITION":
      ui_reset()
      ui_sync_cursor()
      transition_frame += 1
      canvas = pygame.Surface((WIDTH, HEIGHT))
      draw_background(canvas, frame_count)
      draw_scanlines(canvas)

      if transition_frame <= slash_duration:
        if transition_snapshot:
          canvas.blit(transition_snapshot, (0, 0))

        slash_prog = transition_frame / slash_duration
        center_y = HEIGHT // 2
        cut_width = int(WIDTH * slash_prog)
        start_x = (WIDTH - cut_width) // 2
        end_x = (WIDTH + cut_width) // 2

        bg_type = BACKGROUND_TYPES[current_bg_index]
        if bg_type == "DEEP SPACE":
          slash_core, slash_glow = (220, 230, 255), (90, 140, 255)
        elif bg_type == "RETRO GRID":
          slash_core, slash_glow = (255, 255, 255), (255, 0, 128)
        else:
          slash_core, slash_glow = (255, 255, 255), (0, 255, 200)

        pygame.draw.line(
            canvas, slash_core, (start_x, center_y), (end_x, center_y), 10
        )
        pygame.draw.line(
            canvas, slash_glow, (start_x, center_y - 4), (end_x, center_y - 4), 4
        )
        pygame.draw.line(
            canvas, slash_glow, (start_x, center_y + 4), (end_x, center_y + 4), 4
        )

        for _ in range(6):
          sx, sy = end_x + random.randint(-10, 10), center_y + random.randint(
              -12, 12
          )
          pygame.draw.circle(canvas, slash_core, (sx, sy), random.randint(2, 5))

      else:
        split_progress = min(
            1.0, (transition_frame - slash_duration) / split_duration
        )
        max_offset = HEIGHT // 2 + 50
        current_offset = int(split_progress * max_offset)

        top_rect, bottom_rect = pygame.Rect(
            0, 0, WIDTH, HEIGHT // 2
        ), pygame.Rect(0, HEIGHT // 2, WIDTH, HEIGHT // 2)

        if transition_snapshot:
          canvas.blit(transition_snapshot, (0, -current_offset), top_rect)
          canvas.blit(
              transition_snapshot, (0, HEIGHT // 2 + current_offset), bottom_rect
          )

        vs_progress = min(1.0, split_progress * 1.5)
        box_width, box_height = int(WIDTH * 0.7 * vs_progress), int(
            110 * vs_progress
        )
        vs_box = pygame.Rect(
            (WIDTH - box_width) // 2, (HEIGHT - box_height) // 2, box_width, box_height
        )

        if box_width > 10 and box_height > 10:
          pygame.draw.rect(canvas, (16, 16, 38), vs_box)
          p1_col, p2_col = PALETTE[p1_color_idx][1], PALETTE[p2_color_idx][1]
          pygame.draw.rect(canvas, COLOR_WHITE, vs_box, 3)

          if split_progress > 0.3:
            vs_text = FONT_TITLE.render("VS", True, COLOR_YELLOW)
            canvas.blit(vs_text, vs_text.get_rect(center=vs_box.center))
            p1_badge = FONT_SMALL.render(
                f"P1: {PALETTE[p1_color_idx][0]}", True, p1_col
            )

            if current_mode_index == 0:
              p2_badge_txt = f"BOT: {BOT_LEVELS[current_bot_level]}"
            else:
              p2_badge_txt = f"P2: {PALETTE[p2_color_idx][0]}"

            p2_badge = FONT_SMALL.render(p2_badge_txt, True, p2_col)
            canvas.blit(
                p1_badge,
                (vs_box.x + 20, vs_box.centery - p1_badge.get_height() // 2),
            )
            canvas.blit(
                p2_badge,
                (
                    vs_box.right - p2_badge.get_width() - 20,
                    vs_box.centery - p2_badge.get_height() // 2,
                ),
            )

      screen.blit(canvas, (0, 0))
      pygame.display.flip()

      if transition_frame >= total_transition_duration:
        state = "GAME"

    elif state == "GAME":
      return_to_menu = game_loop()
      if return_to_menu:
        state = "MENU"
      else:
        running = False

    tick_limit = save_data.get("target_fps", 240)
    clock.tick(tick_limit)

  net.disconnect()
  pygame.quit()
  sys.exit()


if __name__ == "__main__":
  main()
