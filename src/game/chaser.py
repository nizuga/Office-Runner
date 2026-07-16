"""
chaser.py — el PDF perseguidor.

Mecánica simple (una barra) pero es lo que da toda la tensión (§7). Mantiene una
`distance` en [0,1]: 1.0 = lejos/seguro, 0.0 = te alcanzó (GAME_OVER).
Chocar acerca al PDF (duele); esquivar bien lo aleja (premia, pero menos que el
castigo, para que fallar importe). Su dibujo (barra HUD + sprite que se acerca en
perspectiva) vive en render.py; aquí solo está la lógica de distancia.
"""

from __future__ import annotations

from game import config


class Chaser:
    def __init__(self) -> None:
        self.distance: float = config.CHASER_START

    def reset(self) -> None:
        self.distance = config.CHASER_START

    def on_hit(self) -> None:
        self.distance = max(0.0, self.distance - config.CHASER_HIT_PENALTY)

    def on_dodge(self) -> None:
        self.distance = min(config.CHASER_MAX, self.distance + config.CHASER_DODGE_REWARD)

    @property
    def caught(self) -> bool:
        return self.distance <= 0.0
