import json
from enum import Enum
from pathlib import Path

import pygame


class Animation:
    def __init__(self, image_path: Path):
        meta = json.loads((image_path.parent / (image_path.stem + ".json")).read_text())
        self.sheet = pygame.image.load(image_path).convert_alpha()
        self.frames = []
        self.t = 0
        for frame in meta["frames"]:
            self.size = (frame["sourceSize"]["w"], frame["sourceSize"]["h"])
            pos = (frame["frame"]["x"], frame["frame"]["y"])
            dt = frame["duration"]
            self.frames.append((pos, range(self.t, self.t + dt)))
            self.t += dt

class AnimationPlayStyle(Enum):
    FORWARD = 1
    PINGPONG = 2

class AnimationPlayer:
    def __init__(self, animation: Animation, playstyle: AnimationPlayStyle = AnimationPlayStyle.FORWARD):
        self.animation = animation
        self.playstyle = playstyle
        self.curr_frame = 0
        self.t = 0.0
        self.absolute_t = 0.0
        self.max_t = self.animation.t
        self.direction = +1  # used for pingpong style

    def update(self, dt):
        dt_ms = dt * 1000.0
        self.absolute_t += dt_ms
        
        if self.playstyle == AnimationPlayStyle.FORWARD:
            self.absolute_t %= self.max_t
            self.t = self.absolute_t
            
        elif self.playstyle == AnimationPlayStyle.PINGPONG:
            cycle_length = self.max_t * 2
            self.absolute_t %= cycle_length
            
            if self.absolute_t < self.max_t:
                self.t = self.absolute_t
            else:
                self.t = (cycle_length - 1) - self.absolute_t
                
        check_t = int(self.t)
        for i, (_pos, timerange) in enumerate(self.animation.frames):
            if check_t in timerange:
                self.curr_frame = i
                break

    def draw(self, surface, dest):
        frame = self.animation.frames[self.curr_frame]
        pos, _timerange = frame
        surface.blit(self.animation.sheet, dest=dest, area=pygame.Rect(*pos, *self.animation.size))
            
        
