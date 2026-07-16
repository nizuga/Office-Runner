"""
main.py — punto de entrada. Ejecutar con:  python main.py

Agrega src/ al path para que el paquete `game` sea importable sin instalación.

Fuente del ControllerState (§ "La fuente del estado es intercambiable"):
  - Por defecto: teclado (no requiere webcam; sirve para desarrollo y pruebas).
  - Con cámara:  ejecutar `python main.py --camera`  (o  GAME_SOURCE=camera).
La cámara y el teclado exponen la MISMA interfaz (handle_event + get_state), así
que solo cambia qué se instancia; el resto del juego no se entera.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from game.game import Game  # noqa: E402


def _make_controller():
    """Elige la fuente de ControllerState según CLI / entorno."""
    use_camera = "--camera" in sys.argv or os.environ.get("GAME_SOURCE") == "camera"
    if use_camera:
        # Import perezoso: así el modo teclado no exige opencv/mediapipe.
        from game.camera_controller import CameraController
        return CameraController()
    from game.keyboard_controller import KeyboardController
    return KeyboardController()


if __name__ == "__main__":
    Game(controller=_make_controller()).run()
