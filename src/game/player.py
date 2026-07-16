"""
player.py — entidad Player.

El jugador vive en uno de 3 carriles y puede saltar. El movimiento entre
carriles se interpola (lerp) para que no sea instantáneo/tosco (§7). El salto
es una animación de offset vertical en arco durante N frames, e inmuniza al
jugador contra obstáculos de tipo JUMP mientras dura (se usará el Día 2).
"""

from __future__ import annotations

import math

import pygame

from game import config


class Player:
    """Personaje controlado por el ControllerState."""

    def __init__(self) -> None:
        self.target_lane: int = 1
        # Posición X actual (float para interpolar suave hacia el carril).
        self.x: float = config.lane_center_x(self.target_lane)
        self.base_y: float = config.PLAYER_BASE_Y
        # Estado de salto.
        self.in_air: bool = False
        self._jump_frame: int = 0

    # --- API que consume el juego ---

    def set_lane(self, lane: int) -> None:
        """Fija el carril objetivo (el movimiento real es gradual vía lerp)."""
        self.target_lane = max(0, min(config.LANE_COUNT - 1, lane))

    def start_jump(self) -> None:
        """Inicia un salto si no hay uno en curso (evento de un frame)."""
        if not self.in_air:
            self.in_air = True
            self._jump_frame = 0

    def update(self) -> None:
        """Avanza un frame: interpola X y progresa el arco de salto."""
        # Interpolación de carril.
        target_x = config.lane_center_x(self.target_lane)
        self.x += (target_x - self.x) * config.LANE_LERP

        # Progreso del salto.
        if self.in_air:
            self._jump_frame += 1
            if self._jump_frame >= config.JUMP_FRAMES:
                self.in_air = False
                self._jump_frame = 0

    # --- Derivados ---

    @property
    def jump_offset(self) -> float:
        """Offset vertical positivo (px hacia arriba) del arco de salto."""
        if not self.in_air:
            return 0.0
        p = self._jump_frame / config.JUMP_FRAMES  # 0 -> 1
        return config.JUMP_HEIGHT * math.sin(math.pi * p)

    @property
    def rect(self) -> pygame.Rect:
        """Huella de colisión LÓGICA (carril × profundidad, no píxeles de pantalla).

        NO sube con el salto: en el eje lógico `y` (profundidad de la pista) el
        jugador no se desplaza al saltar. La inmunidad del salto se resuelve en
        game.py comparando `jump_offset` (altura actual) contra la ALTURA del
        obstáculo — elevar este rect mezclaría altura con profundidad y movería
        al jugador HACIA el obstáculo. El dibujo pseudo-3D vive en render.py y
        no interviene en la física.
        """
        size = config.PLAYER_SIZE
        cx = self.x
        cy = self.base_y
        return pygame.Rect(int(cx - size / 2), int(cy - size), size, size)
