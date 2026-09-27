import pygame


class PlayerTwo(pygame.sprite.Sprite):
    def __init__(self, x, y, color):
        super().__init__()
        self.color = color
        self.base_image = pygame.Surface((28, 125))
        self.base_image.fill(self.color)
        self.image = self.base_image
        self.rect = self.image.get_rect(topleft=(x, y))
        self.speed = 5
        self.animation_timer = 0

    def set_color(self, color):
        self.color = color
        self.base_image.fill(self.color)
        self.image = self.base_image

    def set_height(self, height):
        center = self.rect.center
        self.base_image = pygame.Surface((28, height))
        self.base_image.fill(self.color)
        self.image = self.base_image
        self.rect = self.image.get_rect(center=center)

    def trigger_ability_animation(self):
        self.animation_timer = 30

    def update(self):
        keys = pygame.key.get_pressed()
        if keys[pygame.K_UP]: 
            self.rect.y -= self.speed
        if keys[pygame.K_DOWN]: 
            self.rect.y += self.speed

        if self.rect.top < 0:
            self.rect.top = 0
        if self.rect.bottom > 600:
            self.rect.bottom = 600

        if self.animation_timer > 0:
            self.animation_timer -= 1
            if (self.animation_timer // 5) % 2 == 0:
                flash_surf = self.base_image.copy()
                flash_surf.fill((255, 255, 255), special_flags=pygame.BLEND_RGB_ADD)
                self.image = flash_surf
            else:
                self.image = self.base_image
        else:
            self.image = self.base_image