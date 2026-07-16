"""
controller_state.py — LA INTERFAZ ⭐ (frontera con Persona A / cámara).

Este es el único punto de contacto entre el módulo de juego (Persona B) y el
módulo de visión (Persona A). El juego SOLO LEE estos campos cada frame; nunca
los escribe (salvo el stub de teclado, que actúa como fuente alterna).

El Día 3 se cambia la fuente de este objeto (teclado -> cámara) sin tocar el
resto del juego. Mientras ambos respeten esta interfaz, cada mitad avanza sola.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ControllerState:
    """Estado del controlador leído por el juego una vez por frame."""

    # ¿Ya se fijó la línea base? Si es False, el juego muestra la pantalla de
    # calibración. Con teclado siempre es True (no hay calibración).
    calibrated: bool = False

    # Carril objetivo: 0 = izquierda, 1 = centro, 2 = derecha.
    lane: int = 1

    # Evento de UN frame (flanco de subida). Ya viene "desbotonado" por la
    # fuente. El juego reacciona una sola vez cuando llega True.
    jump: bool = False

    # --- solo en modo jefe ---
    # Id del estiramiento sostenido detectado, ej. "arm_cross_L". None si nada.
    active_stretch: str | None = None

    # 0.0 a 1.0: cuánto lleva sostenida la postura requerida.
    stretch_progress: float = 0.0
