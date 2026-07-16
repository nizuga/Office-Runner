"""
camera_controller.py — fuente de ControllerState basada en cámara (Persona A).

Integrado desde el módulo de visión de Persona A (webcam + OpenCV + MediaPipe).
Produce el MISMO ControllerState que el stub de teclado, así que es una fuente
INTERCAMBIABLE: para usar la cámara en vez del teclado basta con cambiar la línea
de instanciación en game.py (`KeyboardController()` -> `CameraController()`); el
resto del juego no cambia (§ "La fuente del estado es intercambiable" en CLAUDE.md).

Cambios respecto al código original de Persona A:
  1. Importa el contrato CANÓNICO `game.controller_state.ControllerState` (antes
     tenía su propia copia divergente). Ahora hay UNA sola interfaz.
  2. El estiramiento se mide contra un OBJETIVO conocido (el que pide el jefe,
     recibido por el canal lateral `target_stretch`): `_evaluate_pose` compara
     cada articulación clave con su posición objetivo (config.STRETCH_GUIDE_TARGETS)
     y `_draw_stretch_guide` pinta esa misma diana sobre el feed. Así el trazo-guía
     que el jugador ve ES la prueba de acierto (verde por parte del cuerpo). Los 5
     ids (arms_cross, neck_tilt_L/R, arm_reach_L/R) coinciden con
     config.BOSS_STRETCH_SEQUENCE y con el mapeo del teclado.
  3. Adaptador `handle_event()` / `get_state()` para que la interfaz sea idéntica
     a la de KeyboardController y el juego la consuma sin ramas especiales.

`update(boss_mode, draw_debug)` sigue disponible para el demo de calibración
(camera_debug_demo.py).
"""

from __future__ import annotations

import threading
import time
from collections import deque
from dataclasses import dataclass

import cv2
import mediapipe as mp

from game import config
from game.controller_state import ControllerState


@dataclass(slots=True)
class Calibration:
    shoulder_center_x: float
    shoulder_y: float
    shoulder_width: float


class PoseCameraController:
    """Webcam + MediaPipe controller for the Pausa Activa runner.

    The game should call update() once per frame and consume the returned
    ControllerState. The optional debug frame is useful during calibration.
    """

    def __init__(
        self,
        camera_index: int = 0,
        calibration_seconds: float = 2.0,
        # Cuánto hay que desplazar el centro de hombros (fracción del ancho de
        # hombros) para cambiar de carril. Bajado 0.38 -> 0.24: dispara más fácil
        # a ambos lados (menos lean necesario). return < enter da histéresis
        # (dead-band 0.12) para no parpadear entre carriles cerca del umbral.
        lane_enter_threshold: float = 0.24,
        lane_return_threshold: float = 0.12,
        jump_threshold: float = 0.22,
        # Hold de estiramiento: fuente única en config para no descoordinarse con
        # el stub de teclado (ambos tardan lo mismo en llegar a progress=1.0).
        stretch_hold_seconds: float = config.BOSS_STRETCH_HOLD_SECONDS,
        min_visibility: float = 0.55,
    ) -> None:
        self.capture = cv2.VideoCapture(camera_index)
        self.state = ControllerState()
        # Último frame anotado (numpy BGR con esqueleto). Canal LATERAL para que el
        # panel de la vista muestre al jugador; NO es parte del ControllerState.
        self.last_frame = None
        self.calibration_seconds = calibration_seconds
        self.lane_enter_threshold = lane_enter_threshold
        self.lane_return_threshold = lane_return_threshold
        self.jump_threshold = jump_threshold
        self.stretch_hold_seconds = stretch_hold_seconds
        self.min_visibility = min_visibility

        # Cuando el juego consume el estado vía get_state() (sin pasar boss_mode),
        # detectamos estiramientos SIEMPRE: el jefe solo los lee en BOSS_FIGHT y el
        # run solo lee `jump`, así que evaluar de más es inofensivo y evita tener
        # que informar el modo de juego a la cámara (drop-in sin tocar game.py).
        self.boss_mode = True

        # Canal LATERAL de ENTRADA (análogo a last_frame, que es de salida): el
        # juego escribe aquí qué estiramiento pide el jefe AHORA para que la cámara
        # dibuje su guía-fantasma y mida el acierto contra ESA pose. None = fuera
        # del jefe (sin guía). No forma parte del contrato ControllerState.
        self.target_stretch: str | None = None
        # Última evaluación por articulación (para dibujar la guía): lista de
        # dicts {label, target, actual, ok, visible}. None si no hay guía activa.
        self._last_guide: list[dict] | None = None

        self._mp_pose = mp.solutions.pose
        self._mp_drawing = mp.solutions.drawing_utils
        self._pose = self._mp_pose.Pose(
            model_complexity=1,
            min_detection_confidence=0.6,
            min_tracking_confidence=0.6,
        )

        self._calibration_started = time.monotonic()
        self._calibration_samples: deque[Calibration] = deque(maxlen=90)
        self._calibration: Calibration | None = None
        self._lane_latch: str | None = None
        self._arms_were_up = False
        self._held_stretch: str | None = None
        self._held_stretch_started = 0.0

        # Hilo lector de cámara (ver get_state): captura + MediaPipe corren
        # aparte para no frenar el loop del juego al ritmo de la webcam. El
        # flanco de `jump` se ACUMULA aquí para no perderse entre lecturas.
        self._lock = threading.Lock()
        self._jump_pending = False
        self._capture_thread: threading.Thread | None = None
        self._stop_capture = threading.Event()

    # --- Interfaz de FUENTE (idéntica a KeyboardController) ---

    def handle_event(self, event: object) -> None:
        """La cámara no usa eventos de pygame; existe para cumplir la interfaz."""
        return None

    def get_state(self) -> ControllerState:
        """Devuelve el último estado SIN bloquear: la cámara se lee en un hilo aparte.

        `capture.read()` bloquea hasta el próximo frame de la webcam (~30 fps) y
        MediaPipe suma varios ms más; hacerlo en el hilo del juego lo frenaba al
        ritmo de la cámara y, como la física es por-frame, TODO el juego corría en
        cámara lenta. El hilo lector (`_capture_loop`) actualiza `self.state` y
        `last_frame` a su ritmo; aquí solo se toma una foto instantánea. `jump` es
        un flanco: se acumula en el hilo y se CONSUME aquí, para que no se pierda
        (ni se duplique) entre lecturas del juego a distinta frecuencia.
        """
        if self._capture_thread is None:
            self._capture_thread = threading.Thread(
                target=self._capture_loop, daemon=True)
            self._capture_thread.start()
        with self._lock:
            jump = self._jump_pending
            self._jump_pending = False
            return ControllerState(
                calibrated=self.state.calibrated,
                lane=self.state.lane,
                jump=jump,
                active_stretch=self.state.active_stretch,
                stretch_progress=self.state.stretch_progress,
            )

    def _capture_loop(self) -> None:
        """Bucle del hilo lector: procesa frames de cámara hasta que close() pare."""
        while not self._stop_capture.is_set():
            state, frame = self.update(boss_mode=self.boss_mode, draw_debug=True)
            with self._lock:
                if state.jump:
                    self._jump_pending = True
                self.last_frame = frame
            if frame is None:
                # Cámara sin frames (desconectada/fallando): no quemar CPU.
                time.sleep(0.05)

    def reset(self) -> None:
        """Re-centra el carril para un run nuevo (mismo hook que el stub de teclado).

        No toca la calibración: la línea base del jugador sigue siendo válida.
        """
        with self._lock:
            self.state.lane = 1
            self._lane_latch = None
            self._jump_pending = False

    def start_calibration(self) -> None:
        """Reinicia la calibración para fijar la línea base AHORA (jugador ya ubicado).

        El juego la llama al terminar el onboarding, así la referencia se toma con
        el jugador en su posición final, no con la que tuviera al abrir la cámara.
        """
        self.state.calibrated = False
        self.state.lane = 1
        self._calibration = None
        self._calibration_samples.clear()
        self._calibration_started = time.monotonic()
        self._lane_latch = None

    def close(self) -> None:
        # Parar el hilo lector ANTES de soltar la cámara/modelo que él usa.
        self._stop_capture.set()
        if self._capture_thread is not None:
            self._capture_thread.join(timeout=1.0)
        self._pose.close()
        self.capture.release()

    def update(self, boss_mode: bool = False, draw_debug: bool = False) -> tuple[ControllerState, object | None]:
        ok, frame = self.capture.read()
        self.state.jump = False
        if not ok:
            return self.state, None

        frame = cv2.flip(frame, 1)
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = self._pose.process(rgb_frame)

        if not results.pose_landmarks:
            self._reset_stretch()
            self._draw_text(frame, "Sin pose detectada", (20, 40), (0, 0, 255))
            return self.state, frame if draw_debug else None

        landmarks = results.pose_landmarks.landmark
        if draw_debug:
            # Solo los puntos que USAMOS (hombros + brazos). No dibujamos la cara:
            # no controla nada y saturaba el feed. Ver _draw_pose_overlay.
            self._draw_pose_overlay(frame, landmarks)

        if not self._has_visible_shoulders(landmarks):
            self._reset_stretch()
            self._draw_text(frame, "Muestra ambos hombros para calibrar", (20, 40), (0, 0, 255))
            return self.state, frame if draw_debug else None

        current = self._read_body_reference(landmarks)
        if not self.state.calibrated:
            self._calibrate(current, frame)
            return self.state, frame if draw_debug else None

        self._update_lane(current)
        self._update_jump(landmarks, current)

        if boss_mode and self.target_stretch is not None:
            # Jefe: evaluamos SOLO la pose que pide (por articulación) y dibujamos
            # su guía-fantasma sobre el feed. No exige tener los brazos arriba: la
            # inclinación de cuello se hace con los brazos en reposo.
            self._update_stretch(landmarks)
            if draw_debug and self._last_guide:
                self._draw_stretch_guide(frame, self._last_guide)
        else:
            self._reset_stretch()
            self._last_guide = None
            if not self._has_visible_arms(landmarks):
                self._arms_were_up = False
                if draw_debug:
                    self._draw_text(frame, "Para saltar muestra codos y munecas", (20, 110), (0, 200, 255))

        if draw_debug:
            self._draw_debug_overlay(frame, current, boss_mode)

        return self.state, frame if draw_debug else None

    def _calibrate(self, current: Calibration, frame: object) -> None:
        self._calibration_samples.append(current)
        elapsed = time.monotonic() - self._calibration_started
        remaining = max(0.0, self.calibration_seconds - elapsed)
        self._draw_text(frame, f"Sientate derecho: calibrando {remaining:.1f}s", (20, 40), (0, 255, 255))

        if elapsed < self.calibration_seconds or len(self._calibration_samples) < 8:
            return

        count = len(self._calibration_samples)
        self._calibration = Calibration(
            shoulder_center_x=sum(sample.shoulder_center_x for sample in self._calibration_samples) / count,
            shoulder_y=sum(sample.shoulder_y for sample in self._calibration_samples) / count,
            shoulder_width=max(0.001, sum(sample.shoulder_width for sample in self._calibration_samples) / count),
        )
        self.state.calibrated = True
        self.state.lane = 1
        self._draw_text(frame, "Calibracion exitosa", (20, 80), (0, 255, 0))

    def _update_lane(self, current: Calibration) -> None:
        assert self._calibration is not None
        dx = (current.shoulder_center_x - self._calibration.shoulder_center_x) / self._calibration.shoulder_width

        if self._lane_latch == "left":
            if dx > -self.lane_return_threshold:
                self._lane_latch = None
            return

        if self._lane_latch == "right":
            if dx < self.lane_return_threshold:
                self._lane_latch = None
            return

        if dx < -self.lane_enter_threshold:
            self.state.lane = max(0, self.state.lane - 1)
            self._lane_latch = "left"
        elif dx > self.lane_enter_threshold:
            self.state.lane = min(2, self.state.lane + 1)
            self._lane_latch = "right"

    def _update_jump(self, landmarks: list, current: Calibration) -> None:
        left_wrist = landmarks[self._mp_pose.PoseLandmark.LEFT_WRIST]
        right_wrist = landmarks[self._mp_pose.PoseLandmark.RIGHT_WRIST]
        shoulder_line = current.shoulder_y
        margin = self.jump_threshold * current.shoulder_width
        arms_up = left_wrist.y < shoulder_line - margin and right_wrist.y < shoulder_line - margin

        self.state.jump = arms_up and not self._arms_were_up
        self._arms_were_up = arms_up

    def _update_stretch(self, landmarks: list) -> None:
        """Evalúa SOLO la pose que pide el jefe (self.target_stretch), por
        articulación, y avanza el progreso mientras TODAS aciertan.

        A diferencia de un reconocedor de "cualquier pose", aquí medimos contra un
        objetivo conocido: lo que se dibuja como guía-fantasma es exactamente lo
        que se mide, así el "verde por parte" y el avance de la barra coinciden con
        lo que el jugador ve. Romper la pose reinicia el progreso (como antes).
        """
        target = self.target_stretch
        matched, joints = self._evaluate_pose(target, landmarks)
        self._last_guide = joints
        now = time.monotonic()

        if not matched:
            self.state.active_stretch = None
            self.state.stretch_progress = 0.0
            self._held_stretch = None
            return

        if target != self._held_stretch:
            self._held_stretch = target
            self._held_stretch_started = now

        elapsed = now - self._held_stretch_started
        self.state.active_stretch = target
        self.state.stretch_progress = min(1.0, elapsed / self.stretch_hold_seconds)

    def _shoulder_anchor(self, landmarks: list) -> tuple[float, float, float]:
        """(centro_x, línea_y, ancho) de los hombros EN VIVO — ancla y escala del
        objetivo, para que la guía siga al cuerpo y sea invariante a la distancia."""
        left_shoulder = landmarks[self._mp_pose.PoseLandmark.LEFT_SHOULDER]
        right_shoulder = landmarks[self._mp_pose.PoseLandmark.RIGHT_SHOULDER]
        cx = (left_shoulder.x + right_shoulder.x) / 2
        sy = (left_shoulder.y + right_shoulder.y) / 2
        w = max(0.001, abs(right_shoulder.x - left_shoulder.x))
        return cx, sy, w

    def _actual_point(self, landmarks: list, name: str) -> tuple[float, float, float]:
        """Punto real (x, y normalizados) y visibilidad de una articulación clave.
        `EAR_CENTER` es un punto sintético: el medio de ambas orejas (la cabeza)."""
        if name == "EAR_CENTER":
            le = landmarks[self._mp_pose.PoseLandmark.LEFT_EAR]
            re = landmarks[self._mp_pose.PoseLandmark.RIGHT_EAR]
            return (le.x + re.x) / 2, (le.y + re.y) / 2, min(le.visibility, re.visibility)
        lm = landmarks[getattr(self._mp_pose.PoseLandmark, name)]
        return lm.x, lm.y, lm.visibility

    def _evaluate_pose(self, target: str | None, landmarks: list) -> tuple[bool, list[dict]]:
        """Compara cada articulación clave del `target` contra su objetivo.

        Devuelve (matched, joints). `joints` describe cada punto para el dibujo:
        {label, target (x,y norm), actual (x,y norm), ok, visible}. `matched` es
        True solo si TODAS aciertan (visibles y dentro de la tolerancia).
        """
        specs = config.STRETCH_GUIDE_TARGETS.get(target or "")
        if not specs:
            return False, []

        cx, sy, w = self._shoulder_anchor(landmarks)
        tol = config.STRETCH_GUIDE_TOL * w
        joints: list[dict] = []
        for label, name, dx, dy in specs:
            tx, ty = cx + dx * w, sy + dy * w
            ax, ay, vis = self._actual_point(landmarks, name)
            visible = vis >= self.min_visibility
            dist = ((ax - tx) ** 2 + (ay - ty) ** 2) ** 0.5
            joints.append({
                "label": label,
                "target": (tx, ty),
                "actual": (ax, ay),
                "ok": visible and dist <= tol,
                "visible": visible,
            })
        matched = bool(joints) and all(j["ok"] for j in joints)
        return matched, joints

    # Colores del fantasma, en BGR (se dibujan con OpenCV sobre el frame numpy).
    _GUIDE_OK_BGR = (110, 210, 100)      # verde: parte acertada
    _GUIDE_WAIT_BGR = (70, 180, 235)     # ámbar: aún no / muévela hacia el trazo
    _GUIDE_GHOST_BGR = (170, 170, 170)   # diana objetivo neutra

    def _draw_stretch_guide(self, frame: object, joints: list[dict]) -> None:
        """Dibuja el trazo-guía sobre el feed: una diana por articulación objetivo.

        Verde y rellena cuando esa parte acierta; ámbar con flecha desde tu punto
        real hacia el objetivo cuando falta. Así alguien que nunca ha estirado ve
        adónde llevar cada brazo/cabeza y cuándo lo logró. (Qué estiramiento es lo
        dice el texto grande del panel; aquí no repetimos etiquetas para no saturar,
        sobre todo en el abrazo donde las dos dianas quedan juntas.)
        """
        h, w = frame.shape[0], frame.shape[1]
        for j in joints:
            tx, ty = int(j["target"][0] * w), int(j["target"][1] * h)
            ok = j["ok"]
            color = self._GUIDE_OK_BGR if ok else self._GUIDE_WAIT_BGR
            if not ok and j["visible"]:
                # Flecha desde donde estás hacia el objetivo (cómo corregir). Se
                # dibuja primero para que las dianas queden por encima.
                ax, ay = int(j["actual"][0] * w), int(j["actual"][1] * h)
                cv2.arrowedLine(frame, (ax, ay), (tx, ty), color, 2, cv2.LINE_AA, tipLength=0.25)
            # Diana objetivo: aro exterior neutro + aro de estado.
            cv2.circle(frame, (tx, ty), 26, self._GUIDE_GHOST_BGR, 2, cv2.LINE_AA)
            cv2.circle(frame, (tx, ty), 20, color, 3, cv2.LINE_AA)
            if ok:
                cv2.circle(frame, (tx, ty), 11, color, -1, cv2.LINE_AA)  # relleno = logrado

    def _reset_stretch(self) -> None:
        self._held_stretch = None
        self._held_stretch_started = 0.0
        self.state.active_stretch = None
        self.state.stretch_progress = 0.0

    def _read_body_reference(self, landmarks: list) -> Calibration:
        left_shoulder = landmarks[self._mp_pose.PoseLandmark.LEFT_SHOULDER]
        right_shoulder = landmarks[self._mp_pose.PoseLandmark.RIGHT_SHOULDER]
        return Calibration(
            shoulder_center_x=(left_shoulder.x + right_shoulder.x) / 2,
            shoulder_y=(left_shoulder.y + right_shoulder.y) / 2,
            shoulder_width=max(0.001, abs(right_shoulder.x - left_shoulder.x)),
        )

    def _has_visible_shoulders(self, landmarks: list) -> bool:
        required = (
            self._mp_pose.PoseLandmark.LEFT_SHOULDER,
            self._mp_pose.PoseLandmark.RIGHT_SHOULDER,
        )
        return all(landmarks[index].visibility >= self.min_visibility for index in required)

    def _has_visible_arms(self, landmarks: list) -> bool:
        required = (
            self._mp_pose.PoseLandmark.LEFT_ELBOW,
            self._mp_pose.PoseLandmark.RIGHT_ELBOW,
            self._mp_pose.PoseLandmark.LEFT_WRIST,
            self._mp_pose.PoseLandmark.RIGHT_WRIST,
        )
        return all(landmarks[index].visibility >= self.min_visibility for index in required)

    def _draw_pose_overlay(self, frame: object, landmarks: list) -> None:
        """Dibuja SOLO los landmarks de control: hombros y brazos. Nada de cara.

        Une hombro-hombro y cada brazo (hombro-codo-muñeca) para que se vea la
        postura relevante al juego. Los puntos poco visibles se omiten.
        """
        h, w = frame.shape[0], frame.shape[1]
        L = self._mp_pose.PoseLandmark

        def px(idx) -> tuple[int, int] | None:
            lm = landmarks[idx]
            if lm.visibility < self.min_visibility:
                return None
            return int(lm.x * w), int(lm.y * h)

        # Segmentos: torso (hombro-hombro) y ambos brazos.
        chains = (
            (L.LEFT_SHOULDER, L.RIGHT_SHOULDER),
            (L.LEFT_SHOULDER, L.LEFT_ELBOW, L.LEFT_WRIST),
            (L.RIGHT_SHOULDER, L.RIGHT_ELBOW, L.RIGHT_WRIST),
        )
        for chain in chains:
            pts = [px(i) for i in chain]
            for a, b in zip(pts, pts[1:]):
                if a is not None and b is not None:
                    cv2.line(frame, a, b, (120, 200, 255), 2, cv2.LINE_AA)

        # Puntos: hombros marcados más grandes (son la referencia del carril).
        big = (L.LEFT_SHOULDER, L.RIGHT_SHOULDER)
        small = (L.LEFT_ELBOW, L.RIGHT_ELBOW, L.LEFT_WRIST, L.RIGHT_WRIST)
        for idx in big:
            p = px(idx)
            if p is not None:
                cv2.circle(frame, p, 8, (86, 180, 233), -1, cv2.LINE_AA)
        for idx in small:
            p = px(idx)
            if p is not None:
                cv2.circle(frame, p, 5, (146, 210, 240), -1, cv2.LINE_AA)

    def _draw_debug_overlay(self, frame: object, current: Calibration, boss_mode: bool) -> None:
        assert self._calibration is not None
        dx = (current.shoulder_center_x - self._calibration.shoulder_center_x) / self._calibration.shoulder_width
        self._draw_text(frame, f"lane={self.state.lane} jump={self.state.jump} dx={dx:+.2f}", (20, 40), (0, 255, 0))
        mode = "JEFE" if boss_mode else "RUN"
        stretch = self.state.active_stretch or "-"
        self._draw_text(frame, f"modo={mode} stretch={stretch} {self.state.stretch_progress:.0%}", (20, 75), (0, 255, 0))

    @staticmethod
    def _draw_text(frame: object, text: str, origin: tuple[int, int], color: tuple[int, int, int]) -> None:
        cv2.putText(frame, text, origin, cv2.FONT_HERSHEY_SIMPLEX, 0.75, color, 2, cv2.LINE_AA)


# Alias con el nombre de la interexcambiabilidad: el juego instancia
# `CameraController()` igual que `KeyboardController()`.
CameraController = PoseCameraController
