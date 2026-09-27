import pygame
import random
import math


class Ball(pygame.sprite.Sprite):
    def __init__(self, width, height):
        super().__init__()
        self.screen_width = width
        self.screen_height = height
        
        # Base image setup
        self.image = pygame.Surface((15, 15))
        self.rect = self.image.get_rect()
        
        # Floating-point position accumulators for smooth sub-pixel movement & curving
        self.x = float(self.rect.x)
        self.y = float(self.rect.y)
        
        self.speed = 5
        self.dx = float(self.speed)
        self.dy = float(self.speed)
        
        # Ability state properties
        self.curvy_active = False
        self.curvy_timer = 0
        self._prev_curvy_active = False
        self.curve_dir = 1
        self.curve_strength = 0.04
        
        self.bullet_active = False
        self.ghost_timer = 0
        
        self.reset()

    def set_speed(self, speed):
        self.speed = speed
        if self.dx != 0:
            self.dx = float(self.speed if self.dx > 0 else -self.speed)
        if self.dy != 0:
            self.dy = float(self.speed if self.dy > 0 else -self.speed)

    def reset(self):
        self.rect.center = (self.screen_width // 2, self.screen_height // 2)
        self.x = float(self.rect.x)
        self.y = float(self.rect.y)
        self.dx = float(self.speed * random.choice((1, -1)))
        self.dy = float(self.speed * random.choice((1, -1)) * random.uniform(0.5, 1.0))
        self.curvy_active = False
        self.curvy_timer = 0
        self._prev_curvy_active = False
        self.bullet_active = False
        self.ghost_timer = 0
        self.image.fill((255, 255, 255))

    def update(self, player_one, player_two, p1_shield, p2_shield):
        # Detect fresh activation of Curvy Ball to randomize direction & strength once per use
        if self.curvy_active and not self._prev_curvy_active:
            self.curve_dir = random.choice([1, -1])  # Randomize curve direction (clockwise or counter-clockwise)
            self.curve_strength = random.uniform(0.03, 0.06)  # Safe bounded strength to prevent looping circles

        self._prev_curvy_active = self.curvy_active

        # Curveball Physics with randomized direction and gentle arc
        if self.curvy_active and self.curvy_timer > 0:
            self.curvy_timer -= 1
            self.image.fill((255, 0, 255))  # Magenta glow for active curvy ball
            
            speed_mag = math.hypot(self.dx, self.dy)
            if speed_mag > 0:
                # Perpendicular vector multiplied by randomized curve_dir
                nx, ny = (-self.dy / speed_mag) * self.curve_dir, (self.dx / speed_mag) * self.curve_dir
                self.dx += nx * self.curve_strength
                self.dy += ny * self.curve_strength
                
                # Normalize back to maintain consistent speed magnitude
                new_mag = math.hypot(self.dx, self.dy)
                if new_mag > 0:
                    self.dx = (self.dx / new_mag) * self.speed
                    self.dy = (self.dy / new_mag) * self.speed
                    
            if self.curvy_timer <= 0:
                self.curvy_active = False
                self.image.fill((255, 255, 255))
        else:
            self.image.fill((255, 255, 255))

        # Update floating point positions and sync to rect
        self.x += self.dx
        self.y += self.dy
        self.rect.x = int(self.x)
        self.rect.y = int(self.y)

        # Top and bottom wall collisions
        if self.rect.top <= 0:
            self.rect.top = 0
            self.y = float(self.rect.y)
            self.dy *= -1
        elif self.rect.bottom >= self.screen_height:
            self.rect.bottom = self.screen_height
            self.y = float(self.rect.y)
            self.dy *= -1

        # Paddle collisions
        if self.rect.colliderect(player_one.rect):
            self.rect.left = player_one.rect.right
            self.x = float(self.rect.x)
            self.dx *= -1
            diff = self.rect.centery - player_one.rect.centery
            self.dy += diff * 0.1
            self.bullet_active = False

        if self.rect.colliderect(player_two.rect):
            self.rect.right = player_two.rect.left
            self.x = float(self.rect.x)
            self.dx *= -1
            diff = self.rect.centery - player_two.rect.centery
            self.dy += diff * 0.1
            self.bullet_active = False

        # Shield collisions
        if p1_shield and self.rect.left <= 5:
            self.dx *= -1
            return "P1_SHIELD_BREAK"
        if p2_shield and self.rect.right >= self.screen_width - 5:
            self.dx *= -1
            return "P2_SHIELD_BREAK"

        # Scoring checks
        if self.rect.left <= 0:
            return "P2"
        if self.rect.right >= self.screen_width:
            return "P1"

        return None