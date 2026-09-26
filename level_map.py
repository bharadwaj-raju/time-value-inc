from typing import Self

import pygame
import pygame.gfxdraw
from PIL import Image

from consts import AREA_HEIGHT, AREA_WIDTH
from geometry import (
    adjacents_cardinal,
    rect_edges,
)


class LevelMap:
    TILEMAP_WALL = (0, 0, 0)
    TILEMAP_PLAYER = (255, 0, 0)
    TILEMAP_GOAL = (255, 255, 0)
    TILEMAP_GUARD = (0, 0, 255)
    TILEMAP_LASER_GUN_DOWN = (255, 0, 255)
    TILEMAP_LASER_DANGER = (128, 0, 128)
    TILEMAP_TUTORIAL_TEXT_MARKER = (128, 128, 128)
    TILEMAP_TRAPDOOR = (128, 0, 0)
    TILEMAP_TRAPDOOR_TRIGGER = (128, 64, 0)
    TILEMAP_KEY = (255, 255, 128)
    TILEMAP_LOCKED_DOOR = (0, 128, 128)

    def __init__(self, im: Image.Image, tutorial_text: str | None = None, mappings: dict | None = None):
        self.im = im
        self.mappings = mappings or {}
        self.tutorial_text = tutorial_text
        self.scale_factor = AREA_WIDTH // im.width
        self.process()

    @classmethod
    def from_file(cls, filelike) -> Self:
        return cls(Image.open(filelike))

    def process(self):
        self.walls = []
        self.player_start = (0, 0)
        self.goal = None
        self.laser_guns = []
        self.laser_guns_danger = []
        self.tutorial_text_marker = None
        self.tutorial_text_tiles = []
        self.trapdoor_triggers = {}
        self.locked_door = None
        for trigger, trap in self.mappings.get("trapdoor_triggers", {}).items():
            trigger = tuple(map(int, trigger.split(",")))
            trigger = (trigger[0] * self.scale_factor, trigger[1] * self.scale_factor)
            self.trapdoor_triggers[trigger] = (trap[0] * self.scale_factor, trap[1] * self.scale_factor)
        self.key = None
        guard_tiles = set()
        wall_tiles = set()
        for y in range(self.im.height):
            for x in range(self.im.width):
                p = self.im.getpixel((x, y))
                if p == LevelMap.TILEMAP_WALL or p == LevelMap.TILEMAP_LASER_GUN_DOWN:
                    wall_tiles.add((x, y))
                    self.walls.append(
                        pygame.Rect(
                            x * self.scale_factor,
                            y * self.scale_factor,
                            self.scale_factor,
                            self.scale_factor,
                        )
                    )
                if p == LevelMap.TILEMAP_LOCKED_DOOR:
                    self.locked_door = (x * self.scale_factor, y * self.scale_factor)
                if p == LevelMap.TILEMAP_KEY:
                    self.key = (x * self.scale_factor, y * self.scale_factor)
                if p == LevelMap.TILEMAP_TUTORIAL_TEXT_MARKER:
                    if not self.tutorial_text_marker:
                        self.tutorial_text_marker = ((x * self.scale_factor, y * self.scale_factor))
                    self.tutorial_text_tiles.append((x * self.scale_factor, y * self.scale_factor))
                if p == LevelMap.TILEMAP_LASER_DANGER:
                    self.laser_guns_danger.append((x * self.scale_factor, y * self.scale_factor))
                if p == LevelMap.TILEMAP_LASER_GUN_DOWN:
                    wall_tiles.add((x, y))
                    self.laser_guns.append((x * self.scale_factor, y * self.scale_factor))
                if p == LevelMap.TILEMAP_PLAYER:
                    self.player_start = (x * self.scale_factor, y * self.scale_factor)
                if p == LevelMap.TILEMAP_GUARD:
                    guard_tiles.add((x, y))
                if p == LevelMap.TILEMAP_GOAL:
                    self.goal = (x, y)

        self.wall_edges = []

        # 1. Merge Horizontal Edges
        for y in range(self.im.height + 1):
            start_x = None
            for x in range(self.im.width + 1):
                # An edge exists if one side is a wall and the other is empty
                is_wall_below = (x, y) in wall_tiles
                is_wall_above = (x, y - 1) in wall_tiles
                has_edge = is_wall_below ^ is_wall_above

                if has_edge and start_x is None:
                    start_x = x  # Start tracking a new continuous edge
                elif not has_edge and start_x is not None:
                    # End the continuous edge and scale it to screen coordinates
                    self.wall_edges.append(
                        (
                            (start_x * self.scale_factor, y * self.scale_factor),
                            (x * self.scale_factor, y * self.scale_factor),
                        )
                    )
                    start_x = None

        # 2. Merge Vertical Edges
        for x in range(self.im.width + 1):
            start_y = None
            for y in range(self.im.height + 1):
                is_wall_right = (x, y) in wall_tiles
                is_wall_left = (x - 1, y) in wall_tiles
                has_edge = is_wall_right ^ is_wall_left

                if has_edge and start_y is None:
                    start_y = y
                elif not has_edge and start_y is not None:
                    self.wall_edges.append(
                        (
                            (x * self.scale_factor, start_y * self.scale_factor),
                            (x * self.scale_factor, y * self.scale_factor),
                        )
                    )
                    start_y = None

        # Add screen borders to edges so rays always hit a boundary
        border_rect = pygame.Rect(0, 0, AREA_WIDTH, AREA_HEIGHT)
        self.wall_edges.extend(rect_edges(border_rect))

        self.guard_routes = []
        while guard_tiles:
            tile = guard_tiles.pop()
            route = {tile}
            while True:
                route_next_iter = route.copy()
                for other_tile in guard_tiles:
                    if any(other_tile in adjacents_cardinal(*tile) for tile in route):
                        route_next_iter.add(other_tile)
                if len(route_next_iter) == len(route):
                    break
                route = route_next_iter
            for tile in route:
                guard_tiles.discard(tile)
            self.guard_routes.append(set(route))
        print(len(self.guard_routes))
