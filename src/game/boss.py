"""
boss.py — el jefe final (§4).

Mecánica: el jefe pide un estiramiento a la vez (`required_stretch`). Cuando el
jugador SOSTIENE esa postura hasta `stretch_progress == 1.0`, el jefe pierde 1
de vida y pide el siguiente. Vida a 0 -> VICTORY.

El jefe solo LEE `active_stretch` / `stretch_progress` del ControllerState; da
igual si vienen del teclado o de la cámara (misma interfaz).

Clave: `_armed` evita que una MISMA postura sostenida siga haciendo daño frame
tras frame. Tras un golpe hay que soltar/cambiar de postura para re-armar — es
el mismo espíritu que el "jump es un evento de un frame" del run.

Su dibujo vive en render.py; aquí solo está la lógica.
"""

from __future__ import annotations

from game import config


class Boss:
    def __init__(self) -> None:
        self.max_health: int = config.BOSS_MAX_HEALTH
        self.health: int = self.max_health
        self._step: int = 0        # índice dentro de BOSS_STRETCH_SEQUENCE
        self._armed: bool = True   # ¿puede el estiramiento actual hacer daño?

    # --- Derivados ---

    @property
    def required_stretch(self) -> str:
        """Id del estiramiento que el jefe pide ahora mismo."""
        seq = config.BOSS_STRETCH_SEQUENCE
        return seq[min(self._step, len(seq) - 1)]

    @property
    def required_label(self) -> str:
        """Texto legible del estiramiento pedido (para la UI)."""
        return config.BOSS_STRETCH_LABELS.get(self.required_stretch, self.required_stretch)

    @property
    def defeated(self) -> bool:
        return self.health <= 0

    @property
    def health_ratio(self) -> float:
        return self.health / self.max_health if self.max_health else 0.0

    # --- API que consume el juego ---

    def update(self, active_stretch: str | None, stretch_progress: float) -> bool:
        """Avanza un frame. Devuelve True SOLO en el frame en que recibe daño."""
        if self.defeated:
            return False

        if active_stretch != self.required_stretch:
            # Soltó la postura o hace otra: se re-arma para el próximo intento.
            self._armed = True
            return False

        if self._armed and stretch_progress >= 1.0:
            self._armed = False          # consumir: un golpe por postura sostenida
            self.health -= 1
            self._step += 1
            return True

        return False
