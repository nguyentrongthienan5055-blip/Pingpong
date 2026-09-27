"""
match_engine.py -- the server-authoritative synced match (Part 2).

This is a from-scratch, pygame-free reimplementation of the exact
gameplay math in ball.py / player_one.py / player_two.py / main.py's
game_loop(), so the server can run it with no display, no Surfaces,
just numbers -- and so a paddle collision on the server produces
*exactly* the same bounce a local match would.

Deliberate differences from local play, called out here rather than
buried:
  - No bot AI (obviously -- both paddles are real people).
  - No shop upgrades applied. Upgrades are local pong_save.json
    currency; online is its own account/wallet system, and applying
    local grinding to a PvP match would make it pay-to-win between
    friends. Both players start from the same baseline stats.
  - No custom map objects (walls/spikes/powerups). The online arena
    is the default open court. Custom maps can come later.
  - Win score and ball speed are fixed (first to 5, normal speed) for
    this first version rather than negotiated between two clients.
  - Ghost Ball actually works here. In local play, its timer is set
    but a leftover bug (a `+= (1.0 - dts)` that's always += 0 now that
    dts is a fixed 1.0) means it never counts down and is never even
    read to change collision -- so activating it currently does
    nothing. Here it does what it clearly was supposed to: the ball
    passes through paddles, harmlessly, until the timer runs out.
"""

import math
import random

WIDTH, HEIGHT = 1000, 600
BALL_SIZE = 15

PADDLE_W = 28
PADDLE_H_NORMAL = 100
PADDLE_H_GIANT = 200
PADDLE_X1 = 26
PADDLE_X2 = WIDTH - 26 - PADDLE_W

PADDLE_SPEED_NORMAL = 5
PADDLE_SPEED_FAST = 9
PADDLE_SPEED_FROZEN = 2

BALL_SPEED = 5  # SPEED_VALUES[0] ("NORMAL") -- fixed for v1, see module docstring
WIN_SCORE = 5   # SCORE_VALUES default-ish -- fixed for v1

ROUND_COUNTDOWN_TICKS = 120.0  # 2 seconds at 60 TPS, matches local play

PHYSICS_TPS = 60.0
TIME_STEP = 1.0 / PHYSICS_TPS

ABILITIES = [
    "NONE", "GIANT PADDLE", "FAST PADDLE", "FREEZE ENEMY", "SHIELD",
    "BULLET BALL", "GHOST BALL", "CURVY BALL", "TIME SLOW", "AUTO PLAY",
    "MULTIBALL",
]

ABILITY_COOLDOWNS = {
    "NONE": 0,
    "GIANT PADDLE": 360, "FAST PADDLE": 360, "CURVY BALL": 360,
    "GHOST BALL": 600, "FREEZE ENEMY": 600, "TIME SLOW": 600,
    "AUTO PLAY": 720, "SHIELD": 720, "BULLET BALL": 600, "MULTIBALL": 720,
}


def _clamp(v, lo, hi):
  return lo if v < lo else hi if v > hi else v


class MatchBall:
  """Mirrors ball.py's Ball exactly, minus anything pygame (Surface,
  Sprite, Rect) -- position is the ball's top-left corner, same as a
  pygame.Rect's (x, y), with BALL_SIZE x BALL_SIZE dimensions."""

  def __init__(self, speed=BALL_SPEED):
    self.speed = float(speed)
    self.x = 0.0
    self.y = 0.0
    self.dx = self.speed
    self.dy = self.speed
    self.curvy_active = False
    self.curvy_timer = 0.0
    self._prev_curvy_active = False
    self.curve_dir = 1
    self.curve_strength = 0.04
    self.bullet_active = False
    self.ghost_timer = 0.0
    self.reset()

  # -- geometry helpers, same semantics as a pygame.Rect --
  @property
  def left(self): return self.x

  @property
  def right(self): return self.x + BALL_SIZE

  @property
  def top(self): return self.y

  @property
  def bottom(self): return self.y + BALL_SIZE

  @property
  def centerx(self): return self.x + BALL_SIZE / 2

  @property
  def centery(self): return self.y + BALL_SIZE / 2

  def set_speed(self, speed):
    self.speed = float(speed)
    if self.dx != 0:
      self.dx = self.speed if self.dx > 0 else -self.speed
    if self.dy != 0:
      self.dy = self.speed if self.dy > 0 else -self.speed

  def reset(self):
    self.x = (WIDTH - BALL_SIZE) / 2.0
    self.y = (HEIGHT - BALL_SIZE) / 2.0
    self.dx = self.speed * random.choice((1, -1))
    self.dy = self.speed * random.choice((1, -1)) * random.uniform(0.5, 1.0)
    self.curvy_active = False
    self.curvy_timer = 0.0
    self._prev_curvy_active = False
    self.bullet_active = False
    self.ghost_timer = 0.0

  def collides(self, paddle):
    return not (self.right < paddle.left or self.left > paddle.right or
                self.bottom < paddle.top or self.top > paddle.bottom)

  def update(self, p1, p2, p1_shield, p2_shield):
    """One 60Hz tick. Returns one of: None, "P1", "P2",
    "P1_SHIELD_BREAK", "P2_SHIELD_BREAK"."""
    if self.curvy_active and not self._prev_curvy_active:
      self.curve_dir = random.choice([1, -1])
      self.curve_strength = random.uniform(0.03, 0.06)
    self._prev_curvy_active = self.curvy_active

    if self.curvy_active and self.curvy_timer > 0:
      self.curvy_timer -= 1
      speed_mag = math.hypot(self.dx, self.dy)
      if speed_mag > 0:
        nx = (-self.dy / speed_mag) * self.curve_dir
        ny = (self.dx / speed_mag) * self.curve_dir
        self.dx += nx * self.curve_strength
        self.dy += ny * self.curve_strength
        new_mag = math.hypot(self.dx, self.dy)
        if new_mag > 0:
          self.dx = (self.dx / new_mag) * self.speed
          self.dy = (self.dy / new_mag) * self.speed
      if self.curvy_timer <= 0:
        self.curvy_active = False

    ghosted = self.ghost_timer > 0
    if ghosted:
      self.ghost_timer -= 1

    self.x += self.dx
    self.y += self.dy

    if self.top <= 0:
      self.y = 0.0
      self.dy *= -1
    elif self.bottom >= HEIGHT:
      self.y = HEIGHT - BALL_SIZE
      self.dy *= -1

    if not ghosted:
      if self.collides(p1):
        self.x = p1.right
        self.dx *= -1
        self.dy += (self.centery - p1.centery) * 0.1
        self.bullet_active = False
      if self.collides(p2):
        self.x = p2.left - BALL_SIZE
        self.dx *= -1
        self.dy += (self.centery - p2.centery) * 0.1
        self.bullet_active = False

    if p1_shield and self.left <= 5:
      self.dx *= -1
      return "P1_SHIELD_BREAK"
    if p2_shield and self.right >= WIDTH - 5:
      self.dx *= -1
      return "P2_SHIELD_BREAK"

    if self.left <= 0:
      return "P2"
    if self.right >= WIDTH:
      return "P1"
    return None


class Paddle:
  def __init__(self, x):
    self.x = x
    self.height = PADDLE_H_NORMAL
    self.y = (HEIGHT - self.height) / 2.0
    self.speed = PADDLE_SPEED_NORMAL

  @property
  def left(self): return self.x

  @property
  def right(self): return self.x + PADDLE_W

  @property
  def top(self): return self.y

  @property
  def bottom(self): return self.y + self.height

  @property
  def centery(self): return self.y + self.height / 2

  @property
  def centerx(self): return self.x + PADDLE_W / 2

  def set_height(self, height):
    center = self.centery
    self.height = height
    self.y = center - height / 2

  def move(self, direction, dts=1.0):
    self.y += direction * self.speed * dts
    self.y = _clamp(self.y, 0, HEIGHT - self.height)


class Match:
  """One authoritative online match between two players. p1 is always
  the challenger (left paddle), p2 the one who accepted (right
  paddle) -- purely for a consistent, unambiguous side assignment."""

  def __init__(self, p1_username, p2_username, p1_ability, p2_ability):
    self.usernames = {1: p1_username, 2: p2_username}
    self.p1 = Paddle(PADDLE_X1)
    self.p2 = Paddle(PADDLE_X2)
    self.ball = MatchBall(BALL_SPEED)
    self.balls = [self.ball]

    self.p1_ability = p1_ability if p1_ability in ABILITY_COOLDOWNS else "NONE"
    self.p2_ability = p2_ability if p2_ability in ABILITY_COOLDOWNS else "NONE"

    self.score_p1 = 0
    self.score_p2 = 0
    self.max_score = WIN_SCORE

    self.p1_cd = 0.0
    self.p2_cd = 0.0
    self.p1_giant = 0.0
    self.p2_giant = 0.0
    self.p1_speed_buff = 0.0
    self.p2_speed_buff = 0.0
    self.p1_freeze = 0.0
    self.p2_freeze = 0.0
    self.p1_auto = 0.0
    self.p2_auto = 0.0
    self.p1_shield = False
    self.p2_shield = False

    self.round_countdown = ROUND_COUNTDOWN_TICKS
    self.game_over = False
    self.winner = None  # 1, 2, or None
    self.forfeited_by = None  # username, if the match ended by disconnect

    self.input_dir = {1: 0, 2: 0}       # -1 / 0 / +1, held state
    self.ability_queue = {1: False, 2: False}  # one-shot triggers

  def set_input(self, player_num, direction):
    self.input_dir[player_num] = _clamp(int(direction), -1, 1)

  def trigger_ability(self, player_num):
    self.ability_queue[player_num] = True

  def _apply_ability(self, player_num, name):
    if name == "GIANT PADDLE":
      if player_num == 1:
        self.p1_giant = 300.0
      else:
        self.p2_giant = 300.0
    elif name == "FAST PADDLE":
      if player_num == 1:
        self.p1_speed_buff = 300.0
      else:
        self.p2_speed_buff = 300.0
    elif name == "FREEZE ENEMY":
      if player_num == 1:
        self.p2_freeze = 180.0
      else:
        self.p1_freeze = 180.0
    elif name == "SHIELD":
      if player_num == 1:
        self.p1_shield = True
      else:
        self.p2_shield = True
    elif name == "BULLET BALL":
      for b in self.balls:
        b.dx = 22 if b.dx > 0 else -22
        b.bullet_active = True
    elif name == "GHOST BALL":
      for b in self.balls:
        b.ghost_timer = 90.0
    elif name == "CURVY BALL":
      for b in self.balls:
        b.curvy_active = True
        b.curvy_timer = 200.0
    elif name == "TIME SLOW":
      if player_num == 1:
        self.p2_freeze = 240.0
      else:
        self.p1_freeze = 240.0
    elif name == "AUTO PLAY":
      if player_num == 1:
        self.p1_auto = 360.0
      else:
        self.p2_auto = 360.0
    elif name == "MULTIBALL":
      base = self.ball
      b1 = MatchBall(base.speed)
      b1.x, b1.y = base.x, base.y
      b1.dx, b1.dy = -base.dx * 0.9, base.dy * 1.3
      b2 = MatchBall(base.speed)
      b2.x, b2.y = base.x, base.y
      b2.dx, b2.dy = base.dx * 1.2, -base.dy * 0.9
      self.balls.extend([b1, b2])

  def tick(self):
    """Advance exactly one 60Hz step. Returns a list of event strings
    for anything the caller might want to react to, e.g. ["SCORE_P1"],
    ["P1_SHIELD_BREAK"], ["GAME_OVER"] -- purely informational, all
    state changes already happened by the time this returns."""
    if self.game_over:
      return []

    events = []
    dts = 1.0

    if self.round_countdown > 0:
      self.round_countdown = max(0.0, self.round_countdown - dts)
      return events

    for pnum, ability in ((1, self.p1_ability), (2, self.p2_ability)):
      cd = self.p1_cd if pnum == 1 else self.p2_cd
      if self.ability_queue[pnum]:
        self.ability_queue[pnum] = False
        if cd <= 0 and ability != "NONE":
          self._apply_ability(pnum, ability)
          if pnum == 1:
            self.p1_cd = float(ABILITY_COOLDOWNS[ability])
          else:
            self.p2_cd = float(ABILITY_COOLDOWNS[ability])

    if self.p1_cd > 0:
      self.p1_cd = max(0.0, self.p1_cd - dts)
    if self.p2_cd > 0:
      self.p2_cd = max(0.0, self.p2_cd - dts)

    self.p1.set_height(PADDLE_H_GIANT if self.p1_giant > 0 else PADDLE_H_NORMAL)
    self.p2.set_height(PADDLE_H_GIANT if self.p2_giant > 0 else PADDLE_H_NORMAL)
    if self.p1_giant > 0:
      self.p1_giant = max(0.0, self.p1_giant - dts)
    if self.p2_giant > 0:
      self.p2_giant = max(0.0, self.p2_giant - dts)

    p1_speed = PADDLE_SPEED_FAST if self.p1_speed_buff > 0 else PADDLE_SPEED_NORMAL
    p2_speed = PADDLE_SPEED_FAST if self.p2_speed_buff > 0 else PADDLE_SPEED_NORMAL
    if self.p1_freeze > 0:
      p1_speed = PADDLE_SPEED_FROZEN
    if self.p2_freeze > 0:
      p2_speed = PADDLE_SPEED_FROZEN
    self.p1.speed = p1_speed
    self.p2.speed = p2_speed

    if self.p1_speed_buff > 0:
      self.p1_speed_buff = max(0.0, self.p1_speed_buff - dts)
    if self.p2_speed_buff > 0:
      self.p2_speed_buff = max(0.0, self.p2_speed_buff - dts)
    if self.p1_freeze > 0:
      self.p1_freeze = max(0.0, self.p1_freeze - dts)
    if self.p2_freeze > 0:
      self.p2_freeze = max(0.0, self.p2_freeze - dts)

    # AUTO PLAY overrides manual input for whichever paddle has it active,
    # tracking whichever ball is heading toward that side.
    def _target_ball_for(pnum):
      incoming = [b for b in self.balls if (b.dx > 0) == (pnum == 2)]
      pool = incoming if incoming else self.balls
      paddle = self.p1 if pnum == 1 else self.p2
      return min(pool, key=lambda b: abs(b.centerx - paddle.centerx))

    if self.p1_auto > 0:
      self.p1_auto = max(0.0, self.p1_auto - dts)
      target = _target_ball_for(1)
      self.p1.y = _clamp(target.centery - self.p1.height / 2, 0, HEIGHT - self.p1.height)
    else:
      self.p1.move(self.input_dir[1], dts)

    if self.p2_auto > 0:
      self.p2_auto = max(0.0, self.p2_auto - dts)
      target = _target_ball_for(2)
      self.p2.y = _clamp(target.centery - self.p2.height / 2, 0, HEIGHT - self.p2.height)
    else:
      self.p2.move(self.input_dir[2], dts)

    scored_side = None
    shield_event = None
    for b in self.balls[:]:
      result = b.update(self.p1, self.p2, self.p1_shield, self.p2_shield)
      if result == "P1_SHIELD_BREAK":
        shield_event = "P1_SHIELD_BREAK"
        self.p1_shield = False
      elif result == "P2_SHIELD_BREAK":
        shield_event = "P2_SHIELD_BREAK"
        self.p2_shield = False
      elif result == "P1":
        scored_side = "P1"
      elif result == "P2":
        scored_side = "P2"

    event_result = shield_event if shield_event else scored_side
    if event_result in ("P1", "P2"):
      if event_result == "P1":
        self.score_p1 += 1
        events.append("SCORE_P1")
      else:
        self.score_p2 += 1
        events.append("SCORE_P2")

      self.ball.reset()
      self.balls = [self.ball]
      self.p1_shield = False
      self.p2_shield = False
      self.p1_auto = 0.0
      self.p2_auto = 0.0
      self.p1.set_height(PADDLE_H_NORMAL)
      self.p2.set_height(PADDLE_H_NORMAL)
      self.p1.y = (HEIGHT - self.p1.height) / 2.0
      self.p2.y = (HEIGHT - self.p2.height) / 2.0
      self.round_countdown = ROUND_COUNTDOWN_TICKS
    elif event_result in ("P1_SHIELD_BREAK", "P2_SHIELD_BREAK"):
      events.append(event_result)

    if self.score_p1 >= self.max_score or self.score_p2 >= self.max_score:
      self.game_over = True
      self.winner = 1 if self.score_p1 >= self.max_score else 2
      events.append("GAME_OVER")

    return events

  def snapshot(self):
    return {
        "type": "match_state",
        "score_p1": self.score_p1,
        "score_p2": self.score_p2,
        "round_countdown": self.round_countdown,
        "game_over": self.game_over,
        "winner": self.winner,
        "p1": {
            "y": self.p1.y, "height": self.p1.height,
            "shield": self.p1_shield, "giant": self.p1_giant > 0,
            "speed_buff": self.p1_speed_buff > 0, "freeze": self.p1_freeze > 0,
            "auto": self.p1_auto > 0, "cd": self.p1_cd, "ability": self.p1_ability,
        },
        "p2": {
            "y": self.p2.y, "height": self.p2.height,
            "shield": self.p2_shield, "giant": self.p2_giant > 0,
            "speed_buff": self.p2_speed_buff > 0, "freeze": self.p2_freeze > 0,
            "auto": self.p2_auto > 0, "cd": self.p2_cd, "ability": self.p2_ability,
        },
        "balls": [
            {"x": b.x, "y": b.y, "curvy": b.curvy_active,
             "bullet": b.bullet_active, "ghost": b.ghost_timer > 0}
            for b in self.balls
        ],
    }