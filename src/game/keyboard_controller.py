"""
keyboard_controller.py — stub de teclado (herramienta de independencia).

Produce el MISMO ControllerState que la cámara, pero desde el teclado, para
desarrollar y probar el juego completo sin webcam.

Controles:
    ← / →      cambiar de carril (0..2)
    ESPACIO    saltar (evento de un frame)
    1 .. 5     MANTENER para sostener un estiramiento (modo jefe; 1 tecla por
               postura de BOSS_STRETCH_SEQUENCE)

Clave: `jump` es un evento de UN frame. Se acumula en `handle_event` al recibir
el KEYDOWN y se limpia en `get_state`, de modo que cada pulsación dispara el
salto exactamente una vez, aunque la tecla se mantenga presionada (§7 del plan).

En cambio `active_stretch`/`stretch_progress` son un ESTADO SOSTENIDO, no un
evento: mientras la tecla siga abajo el progreso sube hasta 1.0, y al soltarla
vuelve a 0. Así el stub imita a la cámara, que reporta cuánto lleva sostenida la
postura — sin eso el jefe recibiría todo el daño en un solo frame.
"""

from __future__ import annotations

import pygame

from game import config
from game.controller_state import ControllerState

# Mapeo de teclas numéricas a ids de estiramiento. Se derivan de la SECUENCIA del
# jefe (config), así siempre coinciden con lo que pide y con los ids de la cámara:
# tecla 1 = 1ª postura, 2 = 2ª, ... hasta 9. Se aceptan también las del keypad.
_STRETCH_KEYS: dict[int, str] = {}
for _i, _stretch in enumerate(config.BOSS_STRETCH_SEQUENCE):
    if _i >= 9:
        break
    _STRETCH_KEYS[getattr(pygame, f"K_{_i + 1}")] = _stretch
    _STRETCH_KEYS[getattr(pygame, f"K_KP{_i + 1}")] = _stretch

# Frames que hay que sostener la tecla para llegar a progress = 1.0. Se deriva del
# hold en segundos de config para tardar lo MISMO que la cámara. Solo aplica al
# stub: con la cámara, el progreso lo calcula el módulo de visión.
STRETCH_HOLD_FRAMES: int = int(config.BOSS_STRETCH_HOLD_SECONDS * config.FPS)


class KeyboardController:
    """Fuente de ControllerState basada en teclado."""

    def __init__(self) -> None:
        self._lane: int = 1
        self._jump_pending: bool = False
        # Estiramiento SOSTENIDO: qué tecla está abajo y hace cuántos frames.
        self._held_stretch: str | None = None
        self._held_frames: int = 0
        # Teclas de estiramiento físicamente abajo, en orden de pulsación: la
        # activa es la ÚLTIMA. Así soltar una tecla secundaria no cancela la que
        # sigue sostenida (rodar los dedos por 1..5 no pierde el progreso ajeno).
        self._down_stretch_keys: list[int] = []

    def reset(self) -> None:
        """Re-centra el stub para un run nuevo (el juego lo llama al reiniciar)."""
        self._lane = 1
        self._jump_pending = False
        self._set_held(None)
        self._down_stretch_keys.clear()

    def _set_held(self, stretch: str | None) -> None:
        """Cambia la postura sostenida; cambiar de postura reinicia el progreso."""
        if stretch != self._held_stretch:
            self._held_stretch = stretch
            self._held_frames = 0

    def handle_event(self, event: pygame.event.Event) -> None:
        """Procesa un evento de pygame. Llamar por cada evento del frame."""
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_LEFT:
                self._lane = max(0, self._lane - 1)
            elif event.key == pygame.K_RIGHT:
                self._lane = min(2, self._lane + 1)
            elif event.key == pygame.K_SPACE:
                self._jump_pending = True
            elif event.key in _STRETCH_KEYS:
                if event.key not in self._down_stretch_keys:
                    self._down_stretch_keys.append(event.key)
                self._set_held(_STRETCH_KEYS[event.key])

        elif event.type == pygame.KEYUP:
            if event.key in self._down_stretch_keys:
                self._down_stretch_keys.remove(event.key)
                # La activa pasa a la última tecla que SIGA abajo (o ninguna).
                nxt = (_STRETCH_KEYS[self._down_stretch_keys[-1]]
                       if self._down_stretch_keys else None)
                self._set_held(nxt)

    def get_state(self) -> ControllerState:
        """Devuelve el estado del frame, avanza el progreso sostenido y
        consume el evento de salto."""
        if self._held_stretch is not None:
            self._held_frames = min(STRETCH_HOLD_FRAMES, self._held_frames + 1)
            progress = self._held_frames / STRETCH_HOLD_FRAMES
        else:
            progress = 0.0

        state = ControllerState(
            calibrated=True,  # el teclado no calibra: siempre listo
            lane=self._lane,
            jump=self._jump_pending,
            active_stretch=self._held_stretch,
            stretch_progress=progress,
        )
        # `jump` es evento de un frame: consumirlo. El estiramiento NO se
        # consume: sigue sostenido mientras la tecla esté abajo.
        self._jump_pending = False
        return state
