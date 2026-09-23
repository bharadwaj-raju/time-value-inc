import pygame
import pygame.draw
from PIL import Image


class Icon:
    def __init__(self, filelike):
        self.im = Image.open(filelike)

    def draw(self, surface: pygame.Surface, dest: tuple[int, int], color=(255, 255, 255), scale=1):
        base_x, base_y = dest
        for y in range(self.im.height):
            for x in range(self.im.width):
                if self.im.getpixel((x, y)) == 0:
                    pygame.draw.rect(surface, color, (base_x + x * scale, base_y + y * scale, scale, scale))
        
