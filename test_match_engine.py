import math
import sys

sys.path.insert(0, ".")
import match_engine as E

PASS, FAIL = [], []


def check(label, cond, extra=""):
  (PASS if cond else FAIL).append(label)
  print(("  OK  " if cond else " FAIL "), label, "" if cond else repr(extra))


def new_match(p1_ab="NONE", p2_ab="NONE"):
  m = E.Match("alice", "bob", p1_ab, p2_ab)
  m.round_countdown = 0
  return m


def freeze_ball(m):
  """Park the ball dead center with zero velocity so it can never
  score or hit a paddle -- for tests that are about something else
  (an ability timer, paddle movement) and shouldn't be contaminated by
  the ball's own randomized physics happening to score mid-test."""
  m.ball.x, m.ball.y = (E.WIDTH - E.BALL_SIZE) / 2, (E.HEIGHT - E.BALL_SIZE) / 2
  m.ball.dx, m.ball.dy = 0.0, 0.0


def run_ticks(m, n):
  for _ in range(n):
    m.tick()


# ---------------------------------------------------------------
# Basic ball physics
# ---------------------------------------------------------------
m = new_match()
m.ball.x, m.ball.y = 500, -5
m.ball.dx, m.ball.dy = 3, -4
m.tick()
check("top wall bounce reflects dy", m.ball.dy == 4, m.ball.dy)
check("top wall bounce clamps y to 0", m.ball.y == 0, m.ball.y)

m = new_match()
m.ball.x, m.ball.y = 500, E.HEIGHT - E.BALL_SIZE + 5
m.ball.dx, m.ball.dy = 3, 4
m.tick()
check("bottom wall bounce reflects dy", m.ball.dy == -4, m.ball.dy)

# ---------------------------------------------------------------
# Paddle collision + english (dy shifts by hit offset)
# ---------------------------------------------------------------
m = new_match()
m.p1.y = 250
m.ball.x = E.PADDLE_X1 + E.PADDLE_W - 2
m.ball.y = m.p1.centery - E.BALL_SIZE / 2 + 20  # hit below paddle center
m.ball.dx, m.ball.dy = -5, 0
m.tick()
check("paddle bounce reverses dx", m.ball.dx == 5, m.ball.dx)
check("off-center hit adds english to dy", m.ball.dy > 0, m.ball.dy)
check("ball repositioned to paddle's right edge", m.ball.x == m.p1.right, (m.ball.x, m.p1.right))

# ---------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------
m = new_match()
m.ball.x, m.ball.y = -1, 300
m.ball.dx, m.ball.dy = -5, 0  # moving further left -- guarantees it stays past the edge
ev = m.tick()
check("ball past left edge scores P2", "SCORE_P2" in ev, ev)
check("score incremented", m.score_p2 == 1, m.score_p2)
check("ball re-centered after score", abs(m.ball.centerx - E.WIDTH / 2) < 1, m.ball.centerx)
check("round_countdown reset after score", m.round_countdown == E.ROUND_COUNTDOWN_TICKS, m.round_countdown)

m = new_match()
m.ball.x, m.ball.y = E.WIDTH + 1, 300
m.ball.dx, m.ball.dy = 5, 0
ev = m.tick()
check("ball past right edge scores P1", "SCORE_P1" in ev, ev)

# ---------------------------------------------------------------
# Round countdown freezes everything
# ---------------------------------------------------------------
m = E.Match("a", "b", "NONE", "NONE")
freeze_ball(m)
bx, by = m.ball.x, m.ball.y
py = m.p1.y
m.set_input(1, 1)
m.tick()
check("round countdown blocks paddle movement", m.p1.y == py, (m.p1.y, py))
check("round countdown blocks ball movement", (m.ball.x, m.ball.y) == (bx, by))
check("round countdown ticks down", m.round_countdown == E.ROUND_COUNTDOWN_TICKS - 1)

# ---------------------------------------------------------------
# Paddle movement + clamping -- test the Paddle class directly,
# decoupled from the ball's own randomized scoring behavior.
# ---------------------------------------------------------------
p = E.Paddle(E.PADDLE_X1)
for _ in range(1000):
  p.move(-1)
check("paddle clamps at top", p.y == 0, p.y)
for _ in range(1000):
  p.move(1)
check("paddle clamps at bottom", p.y == E.HEIGHT - p.height, p.y)

# Same thing through a live Match, but with the ball frozen so it can't
# interrupt with a score partway through.
m = new_match()
freeze_ball(m)
m.set_input(1, -1)
run_ticks(m, 1000)
check("paddle clamps at top (via Match.tick)", m.p1.y == 0, m.p1.y)

# ---------------------------------------------------------------
# Abilities: cooldown gating
# (ability application and its own timer's decrement happen in the same
#  tick, same as the original local game's ordering -- so a value is
#  expected to read one tick short of its "nominal" starting value
#  immediately after activation. That's not a bug, it's a faithful port.)
# ---------------------------------------------------------------
m = new_match(p1_ab="GIANT PADDLE")
freeze_ball(m)
m.trigger_ability(1)
m.tick()
check("giant paddle activates", m.p1_giant == 300.0 - 1, m.p1_giant)
check("cooldown starts", m.p1_cd == E.ABILITY_COOLDOWNS["GIANT PADDLE"] - 1, m.p1_cd)

m.p1_giant = 0  # let the visual effect end without waiting out the timer
m.trigger_ability(1)
m.tick()
check("can't reactivate while on cooldown", m.p1_giant == 0, m.p1_giant)

run_ticks(m, int(E.ABILITY_COOLDOWNS["GIANT PADDLE"]))
check("cooldown expires", m.p1_cd == 0, m.p1_cd)

m.trigger_ability(1)
m.tick()
check("reactivates after cooldown", m.p1_giant == 300.0 - 1, m.p1_giant)

# ---------------------------------------------------------------
# Giant paddle actually changes height
# ---------------------------------------------------------------
m = new_match(p1_ab="GIANT PADDLE")
freeze_ball(m)
m.trigger_ability(1)
m.tick()
check("giant paddle grows height", m.p1.height == E.PADDLE_H_GIANT, m.p1.height)
m.p1_giant = 1  # about to expire
m.tick()
check("height still giant on the tick it expires on (matches height-then-decrement order)",
      m.p1.height == E.PADDLE_H_GIANT, m.p1.height)
m.tick()
check("giant paddle shrinks back one tick after the timer hits 0",
      m.p1.height == E.PADDLE_H_NORMAL, m.p1.height)

# ---------------------------------------------------------------
# Fast paddle / freeze change effective speed
# ---------------------------------------------------------------
m = new_match(p1_ab="FAST PADDLE")
freeze_ball(m)
m.trigger_ability(1)
m.tick()
check("fast paddle raises speed", m.p1.speed == E.PADDLE_SPEED_FAST, m.p1.speed)

m = new_match(p1_ab="FREEZE ENEMY")
freeze_ball(m)
m.trigger_ability(1)
m.tick()
check("freeze enemy slows p2", m.p2.speed == E.PADDLE_SPEED_FROZEN, m.p2.speed)
check("freeze doesn't affect the caster", m.p1.speed == E.PADDLE_SPEED_NORMAL, m.p1.speed)

m = new_match(p2_ab="TIME SLOW")
freeze_ball(m)
m.trigger_ability(2)
m.tick()
check("time slow freezes p1 (longer duration)", m.p1_freeze == 240.0 - 1, m.p1_freeze)

# ---------------------------------------------------------------
# Shield: blocks at the screen edge, breaks the shield, doesn't score
# ---------------------------------------------------------------
m = new_match(p1_ab="SHIELD")
freeze_ball(m)
m.trigger_ability(1)
m.tick()
check("shield activates", m.p1_shield is True)
m.ball.x, m.ball.y = 3, 300
m.ball.dx, m.ball.dy = -5, 0
ev = m.tick()
check("shield blocks the ball (no score)", m.score_p2 == 0, m.score_p2)
check("shield breaks on hit", m.p1_shield is False, m.p1_shield)
check("ball bounces off broken shield", m.ball.dx == 5, m.ball.dx)
check("shield break event reported", "P1_SHIELD_BREAK" in ev, ev)

# ---------------------------------------------------------------
# Bullet ball: sets speed to +/-22 preserving direction
# ---------------------------------------------------------------
m = new_match(p1_ab="BULLET BALL")
freeze_ball(m)
m.ball.dx = -3
m.trigger_ability(1)
m.tick()
check("bullet ball sets dx to -22 (preserves direction)", m.ball.dx == -22, m.ball.dx)
check("bullet_active flag set", m.ball.bullet_active is True)

# ---------------------------------------------------------------
# Curvy ball: direction changes over time but speed magnitude constant
# (kept dead center, well clear of any paddle, so a bounce's english
#  can't perturb the magnitude between renormalization ticks)
# ---------------------------------------------------------------
m = new_match(p1_ab="CURVY BALL")
m.ball.x, m.ball.y = 500, 300
m.ball.dx, m.ball.dy = 3, 4  # magnitude 5, matches ball.speed
speed_before = math.hypot(m.ball.dx, m.ball.dy)
m.trigger_ability(1)
m.tick()
check("curvy ball activates", m.ball.curvy_active is True)
initial_dx = m.ball.dx
for _ in range(30):
  m.tick()
  assert not m.ball.collides(m.p1) and not m.ball.collides(m.p2), "ball drifted into a paddle mid-test"
check("curvy ball actually curves (dx changes)", m.ball.dx != initial_dx, (initial_dx, m.ball.dx))
speed_after = math.hypot(m.ball.dx, m.ball.dy)
check("curvy ball preserves speed magnitude", abs(speed_after - speed_before) < 0.01,
      (speed_before, speed_after))

m2 = new_match(p1_ab="CURVY BALL")
m2.ball.x, m2.ball.y = 500, 300
m2.trigger_ability(1)
m2.tick()
run_ticks(m2, 210)  # curvy_timer starts at 200, decrements 1/tick
check("curvy ball effect expires", m2.ball.curvy_active is False, m2.ball.curvy_active)

# ---------------------------------------------------------------
# Ghost ball: passes through paddles while active, collides again after
# ---------------------------------------------------------------
m = new_match(p1_ab="GHOST BALL")
freeze_ball(m)
m.trigger_ability(1)
m.tick()
check("ghost ball timer set", m.ball.ghost_timer == 90.0 - 1, m.ball.ghost_timer)

m.p1.y = 250
m.ball.x = E.PADDLE_X1 + 5
m.ball.y = m.p1.centery
m.ball.dx, m.ball.dy = -5, 0
m.tick()
check("ghosted ball passes through paddle (no bounce)", m.ball.dx == -5, m.ball.dx)

run_ticks(m, 100)  # let the ghost timer fully expire (ball frozen, no scoring risk)
check("ghost timer actually counts down and expires", m.ball.ghost_timer == 0, m.ball.ghost_timer)
m.ball.x = E.PADDLE_X1 + 5
m.ball.y = m.p1.centery
m.ball.dx, m.ball.dy = -5, 0
m.tick()
check("collision resumes after ghost expires", m.ball.dx == 5, m.ball.dx)

# ---------------------------------------------------------------
# Multiball: spawns 2 extra balls derived from the primary ball
# ---------------------------------------------------------------
m = new_match(p1_ab="MULTIBALL")
freeze_ball(m)
m.ball.dx, m.ball.dy = 5, 3
m.trigger_ability(1)
m.tick()
check("multiball spawns 2 extra balls", len(m.balls) == 3, len(m.balls))
check("ball 2 velocity derived from primary", m.balls[1].dx == -5 * 0.9, m.balls[1].dx)
check("ball 3 velocity derived from primary", m.balls[2].dx == 5 * 1.2, m.balls[2].dx)

# scoring should clear back down to just the primary ball -- position it
# so that it's still past the edge *after* this tick's movement is applied.
m.balls[0].x, m.balls[0].y = -20, 300
m.balls[0].dx, m.balls[0].dy = -5, 0
m.balls[1].x, m.balls[1].y = 500, 300  # keep the others safely in-bounds
m.balls[1].dx, m.balls[1].dy = 0, 0
m.balls[2].x, m.balls[2].y = 500, 320
m.balls[2].dx, m.balls[2].dy = 0, 0
m.tick()
check("scoring clears extra balls", len(m.balls) == 1, len(m.balls))

# ---------------------------------------------------------------
# Auto play: overrides manual input and tracks the ball
# ---------------------------------------------------------------
m = new_match(p1_ab="AUTO PLAY")
m.ball.x, m.ball.y = 400, 50
m.ball.dx, m.ball.dy = -1, 0  # heading toward p1, slow enough not to reach it in 5 ticks
m.trigger_ability(1)
m.tick()
check("auto play activates", m.p1_auto == 360.0 - 1, m.p1_auto)
m.set_input(1, -1)  # manual input should be ignored while auto is active
dist_before = abs(m.p1.centery - m.ball.centery)
run_ticks(m, 5)
dist_after = abs(m.p1.centery - m.ball.centery)
check("auto play moves paddle toward the ball (ignores manual input)",
      dist_after < dist_before, (dist_before, dist_after))

# ---------------------------------------------------------------
# Game over
# ---------------------------------------------------------------
m = new_match()
m.score_p1 = E.WIN_SCORE - 1
m.ball.x, m.ball.y = E.WIDTH + 1, 300
m.ball.dx, m.ball.dy = 5, 0
ev = m.tick()
check("game over event fires at win score", "GAME_OVER" in ev, ev)
check("game_over flag set", m.game_over is True)
check("winner is p1", m.winner == 1, m.winner)
py_before = m.p1.y
m.set_input(1, 1)
m.tick()
check("no more updates once game is over", m.p1.y == py_before, (m.p1.y, py_before))

# ---------------------------------------------------------------
# Snapshot shape sanity
# ---------------------------------------------------------------
m = new_match(p1_ab="SHIELD", p2_ab="MULTIBALL")
snap = m.snapshot()
check("snapshot has expected top-level keys",
      set(["score_p1", "score_p2", "p1", "p2", "balls", "game_over"]) <= set(snap.keys()), snap.keys())
check("snapshot p1 carries ability name", snap["p1"]["ability"] == "SHIELD", snap["p1"])

print("\n%d passed, %d failed" % (len(PASS), len(FAIL)))
if FAIL:
  raise SystemExit(1)