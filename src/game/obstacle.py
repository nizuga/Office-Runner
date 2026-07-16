"""
obstacle.py — obstáculos que bajan hacia el jugador.

Dos tipos con señalización legible (§7): la FORMA dice qué hacer.
    JUMP   -> barra baja que cruza los 3 carriles (ámbar). OBLIGA a saltar: no se
              puede esquivar de lado. Jumpable => no es "imposible" aunque tape todo.
    DODGE  -> alto y sólido en UN carril (rojo). Seguro solo si el jugador NO está
              en su carril (hay que cambiarse a un carril libre).

La colisión separa PROFUNDIDAD de ALTURA: los rects (AABB) resuelven el plano
lógico carril×profundidad, y game.py compara `jump_offset` del jugador contra
`height` del obstáculo para decidir si el salto lo libra. Un JUMP (bajo) se
salta; un DODGE (más alto que JUMP_HEIGHT) no se libra nunca saltando.

`self.y` es el borde INFERIOR del obstáculo y baja `speed` px por frame.
"""

from __future__ import annotations

import random
from enum import Enum, auto

import pygame

from game import config


class ObstacleType(Enum):
    JUMP = auto()   # saltar por encima
    DODGE = auto()  # esquivar cambiando de carril


class Obstacle:
    def __init__(self, otype: ObstacleType, lane: int) -> None:
        self.type = otype
        self.lane = lane
        self.height = (
            config.OBSTACLE_JUMP_HEIGHT
            if otype is ObstacleType.JUMP
            else config.OBSTACLE_DODGE_HEIGHT
        )
        # Empieza justo arriba de la pantalla (borde inferior en y=0).
        self.y: float = 0.0
        # Se resuelve una sola vez (choque o esquive exitoso).
        self.resolved: bool = False
        self.hit: bool = False

    @classmethod
    def random(cls) -> "Obstacle":
        otype = random.choice((ObstacleType.JUMP, ObstacleType.DODGE))
        lane = random.randrange(config.LANE_COUNT)
        return cls(otype, lane)

    def update(self, speed: float) -> None:
        self.y += speed

    @property
    def rect(self) -> pygame.Rect:
        top = self.y - self.height
        if self.type is ObstacleType.JUMP:
            # JUMP ocupa los 3 carriles (barra baja de lado a lado): NO se puede
            # esquivar cambiando de carril, OBLIGA a saltar. Como el rect cubre
            # todo el ancho, la colisión depende solo de la profundidad Y de la
            # altura del salto — el jugador choca esté en el carril que esté.
            x0 = config.LANE_MARGIN
            w = config.SCREEN_WIDTH - 2 * config.LANE_MARGIN
            return pygame.Rect(int(x0), int(top), int(w), self.height)
        # DODGE ocupa un solo carril: se esquiva cambiándose a un carril libre.
        w = config.obstacle_width()
        cx = config.lane_center_x(self.lane)
        return pygame.Rect(int(cx - w / 2), int(top), int(w), self.height)

    def has_passed_player(self) -> bool:
        """True cuando el borde INFERIOR cruzó la línea del jugador.

        Mismo umbral que el culling de render (z > 1): en cuanto el obstáculo
        deja de dibujarse deja de poder hacer daño. Usar el borde superior
        dejaría `height` px de hitbox invisible detrás del jugador.
        """
        return self.y > config.PLAYER_BASE_Y

    def is_off_screen(self) -> bool:
        return (self.y - self.height) > config.SCREEN_HEIGHT
