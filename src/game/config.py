"""
config.py — constantes tuneables del juego en un solo lugar.

Centralizamos aquí todo lo que afecta el "game feel" para poder ajustarlo
rápido el Día 3 (sensibilidad, timing de salto, distancia de reacción).
"""

from __future__ import annotations

# --- Ventana / tiempo ---
# SCREEN_WIDTH/HEIGHT son el ÁREA DE JUEGO (alimentan render.project()). NO tocar
# para ensanchar la ventana: el panel de cámara va aparte (CAM_PANEL_WIDTH) y la
# ventana real la arma game.py sumando ambos.
SCREEN_WIDTH: int = 540
SCREEN_HEIGHT: int = 900
FPS: int = 60
CAPTION: str = "Office Runner — Pausa Activa"

# Fuente de TODO el texto del juego. Lista de fallbacks multiplataforma (SysFont
# acepta nombres separados por coma): Consolas solo existe en Windows; en macOS
# cae a Menlo/Monaco y en Linux a DejaVu Sans Mono. Si ninguna existe, pygame
# usa su fuente por defecto (el juego no se rompe, solo cambia el look).
FONT_NAMES: str = "consolas,menlo,monaco,dejavusansmono,couriernew"

# Ajuste al monitor: el juego se compone a resolución NATIVA (panel + área de
# juego = 1020×900) y se escala como IMAGEN a la ventana real, para que su alto
# quede cerca del alto de la pantalla sin cortarse (ni tocar project()).
WINDOW_FIT_MARGIN: float = 0.92   # fracción del alto/ancho del monitor a ocupar
WINDOW_MAX_SCALE: float = 2.0     # tope de escala (evita gigantismo en 4K)

# Fundido corto al cambiar de estado. Es solo presentacion: no pausa ni altera
# la maquina de estados o la fisica.
TRANSITION_FRAMES: int = 14

# --- Carriles ---
LANE_COUNT: int = 3
# Margen lateral donde no hay carriles jugables (borde de pista).
LANE_MARGIN: int = 40


def lane_width() -> float:
    """Ancho de un carril considerando los márgenes laterales."""
    return (SCREEN_WIDTH - 2 * LANE_MARGIN) / LANE_COUNT


def lane_center_x(lane: int) -> float:
    """Posición X del centro del carril `lane` (0=izq, 1=centro, 2=der)."""
    return LANE_MARGIN + lane_width() * (lane + 0.5)


# --- Jugador ---
PLAYER_SIZE: int = 64
# Y base (línea de piso) donde se apoya el jugador — cerca de la parte baja.
PLAYER_BASE_Y: int = SCREEN_HEIGHT - 160
# Suavizado del cambio de carril: fracción de la distancia que se cubre por
# frame (0..1). Más alto = más rápido/tosco; más bajo = más suave/lento.
# Subido a 0.40: esquivar sillas se siente menos "pegajoso" (sales del carril
# en ~2 frames en vez de ~4), así los esquives tardíos alcanzan a salvarse.
LANE_LERP: float = 0.40
# Salto: altura del arco (px) y duración (frames).
JUMP_HEIGHT: int = 180
JUMP_FRAMES: int = 32

# --- Colores (RGB) ---
COLOR_BG = (24, 26, 33)
COLOR_TRACK = (34, 37, 46)
COLOR_LANE_LINE = (70, 74, 88)
COLOR_PLAYER = (86, 180, 233)       # camisa: el azul ES la identidad del jugador
COLOR_PLAYER_AIR = (146, 210, 240)  # tono más claro mientras está en el aire
# Resto de la paleta del empleado (se ve DE ESPALDAS: no lleva cara).
COLOR_PLAYER_SKIN = (222, 178, 140)
COLOR_PLAYER_HAIR = (52, 42, 40)
COLOR_PLAYER_PANTS = (52, 58, 74)
COLOR_PLAYER_SHOES = (28, 30, 36)
COLOR_PLAYER_BADGE = (230, 184, 64)  # gafete colgando del lanyard

# --- Entorno de oficina (mamparas de cubículo + pared de fondo) ---
COLOR_CUBICLE = (74, 80, 96)         # tela de la mampara
COLOR_CUBICLE_RAIL = (122, 128, 146)  # riel superior
COLOR_CUBICLE_POST = (46, 50, 62)    # postes divisorios
COLOR_WALL = (32, 35, 46)            # pared del fondo (sobre el horizonte)
COLOR_WALL_TRIM = (50, 54, 68)
COLOR_CLOCK = (214, 216, 224)
COLOR_EXIT_SIGN = (96, 190, 128)
COLOR_TEXT = (230, 232, 238)
COLOR_TEXT_DIM = (150, 154, 166)

# --- Feedback de error (flash rojo al chocar) ---
# Al chocar un obstáculo la pantalla parpadea roja y se desvanece en unos frames,
# para que el jugador registre "me equivoqué" además del castigo del PDF.
HIT_FLASH_FRAMES: int = 18        # duración del destello (frames)
HIT_FLASH_ALPHA_MAX: int = 120    # opacidad máxima del rojo (0..255)
COLOR_HIT_FLASH = (200, 30, 30)

# --- Velocidad (px/frame) ---
# FIJA: SPEED_ACCEL = 0 => la velocidad se mantiene constante en SPEED_START
# todo el run (sin rampa). Para tunear el ritmo, cambia SPEED_START.
# (Para reactivar la rampa progresiva: sube SPEED_ACCEL, p.ej. 0.0025.)
SPEED_START: float = 6.0
SPEED_MAX: float = 11.0
SPEED_ACCEL: float = 0.0  # 0 = velocidad fija

# --- Spawn de obstáculos ---
# Espaciado vertical (px) entre obstáculos. Al descontar `speed` px por frame,
# el espaciado en pantalla queda constante aunque suba la velocidad => la
# distancia de reacción no se degrada (§7 "distancia de reacción justa").
SPAWN_SPACING: float = 360.0
SPAWN_JITTER: float = 90.0  # variación aleatoria (±) del espaciado

# --- Obstáculos ---
# Ancho más angosto que el carril para dejar margen visual.
def obstacle_width() -> float:
    return lane_width() * 0.72


OBSTACLE_JUMP_HEIGHT: int = 34    # bajo, a ras de piso  -> SALTAR
# Debe ser MÁS ALTO que JUMP_HEIGHT para que no se pueda saltar por encima:
# un DODGE obliga a cambiar de carril, nunca se libra saltando (§7).
OBSTACLE_DODGE_HEIGHT: int = 220  # alto, bloquea el carril -> ESQUIVAR
COLOR_OBSTACLE_JUMP = (230, 184, 64)   # ámbar: la forma baja dice "salta"
COLOR_OBSTACLE_DODGE = (206, 84, 84)   # rojo/alto dice "cámbiate de carril"

# --- Perseguidor (PDF) ---
# distancia 1.0 = lejos/seguro, 0.0 = te alcanzó -> GAME_OVER.
CHASER_START: float = 0.6
CHASER_MAX: float = 1.0
CHASER_HIT_PENALTY: float = 0.22   # chocar duele
CHASER_DODGE_REWARD: float = 0.06  # esquivar bien premia (menos que el castigo)
COLOR_CHASER = (206, 84, 84)
COLOR_CHASER_BAR_BG = (44, 34, 34)

# --- Meta del run (medidor superior) ---
# Distancia (px de mundo) a recorrer antes de encontrar al jefe. Se acumula
# `speed` por frame: a SPEED_START=6 y 60 FPS son ~17 s de carrera.
RUN_GOAL_DISTANCE: float = 6000.0
COLOR_PROGRESS_BG = (40, 44, 54)
COLOR_PROGRESS_FILL = (110, 200, 140)
COLOR_GOAL = (230, 184, 64)

# --- Jefe final ---
# Cada estiramiento completado le quita 1 de vida. La secuencia se recorre en
# orden; los ids DEBEN coincidir con los que emite la fuente de ControllerState
# (el stub de teclado hoy, la cámara el Día 3). Cinco estiramientos reales de
# pausa activa: un abrazo, cuello a cada lado y cada brazo estirado en diagonal.
BOSS_STRETCH_SEQUENCE = (
    "arms_cross",
    "neck_tilt_L",
    "neck_tilt_R",
    "arm_reach_L",
    "arm_reach_R",
)
BOSS_MAX_HEALTH: int = len(BOSS_STRETCH_SEQUENCE)
BOSS_STRETCH_LABELS = {
    "arms_cross": "Cruza AMBOS brazos",
    "neck_tilt_L": "Inclina la cabeza IZQUIERDA",
    "neck_tilt_R": "Inclina la cabeza DERECHA",
    "arm_reach_L": "Estira el brazo IZQUIERDO arriba",
    "arm_reach_R": "Estira el brazo DERECHO arriba",
}
# Segundos que hay que SOSTENER cada postura para dañar al jefe. Fuente ÚNICA del
# hold: la cámara (stretch_progress) y el stub de teclado (STRETCH_HOLD_FRAMES) la
# leen de aquí para tardar lo mismo. Con 5 posturas => jefe de ~15 s.
BOSS_STRETCH_HOLD_SECONDS: float = 3.0
# Teclas del stub que simulan cada estiramiento (solo para el cartel de ayuda).
BOSS_STRETCH_HINT = "Manten 1..5"

# Animación de daño al jefe (cada estiramiento completado). Un único temporizador
# `boss_hit` (frames) del que render deriva TODO: retroceso, estallido, "-1"
# flotante, destello y sacudida de escena. 1 en el impacto -> 0 al terminar.
BOSS_HIT_ANIM_FRAMES: int = 26
BOSS_HIT_RECOIL: float = 26.0     # px que el jefe salta hacia atrás/arriba al recibir
BOSS_HIT_SHAKE: float = 10.0      # amplitud de la sacudida de la escena (px)
COLOR_BOSS_HIT = (255, 236, 150)  # color del estallido / "-1" / segmento perdido

# --- Guía-fantasma del estiramiento (sobre el feed, modo jefe) ---
# Para quien nunca ha estirado: dibujamos las posiciones OBJETIVO de las
# articulaciones clave sobre su propio video, y esa es TAMBIÉN la prueba de
# acierto (lo que ves es lo que se mide). Cada objetivo se expresa como offset
# (dx, dy) en unidades de ANCHO-DE-HOMBROS respecto al centro de hombros EN VIVO
# (dx>0 = derecha, dy>0 = abajo, en la imagen ya espejada). La articulación real
# "acierta" (verde) si cae dentro de STRETCH_GUIDE_TOL*ancho del objetivo; la
# postura CUENTA cuando TODAS aciertan. La detección de la cámara se deriva de
# aquí, así que si un lado sale invertido en cámara, cambiar el signo aquí
# corrige a la vez el trazo Y la detección.
STRETCH_GUIDE_TOL: float = 0.35
# Punto especial "EAR_CENTER" = punto medio de las orejas (para la cabeza).
STRETCH_GUIDE_TARGETS = {
    "arms_cross": (
        ("brazo izq", "LEFT_WRIST", 0.33, 0.22),
        ("brazo der", "RIGHT_WRIST", -0.33, 0.22),
    ),
    "arm_reach_L": (("brazo izq", "LEFT_WRIST", -0.75, -0.85),),
    "arm_reach_R": (("brazo der", "RIGHT_WRIST", 0.75, -0.85),),
    "neck_tilt_L": (("cabeza", "EAR_CENTER", -0.33, -0.70),),
    "neck_tilt_R": (("cabeza", "EAR_CENTER", 0.33, -0.70),),
}
# Brillo aditivo del destello (0..255). Alto lo deja blanco y borra el sprite.
# (La duración del destello la marca BOSS_HIT_ANIM_FRAMES, más abajo.)
BOSS_HIT_FLASH_ADD: int = 110

COLOR_BOSS_SUIT = (70, 60, 96)
COLOR_BOSS_SKIN = (222, 178, 140)
COLOR_BOSS_SHIRT = (230, 232, 238)
COLOR_BOSS_TIE = (206, 84, 84)
COLOR_BOSS_HEALTH = (206, 84, 84)
COLOR_BOSS_HEALTH_BG = (44, 34, 34)
COLOR_STRETCH_FILL = (110, 200, 140)

# --- Pausa de agua (cierre del juego) ---
# Al entrar a WATER_BREAK el jefe hace MUTIS: se desliza hacia la SALIDA y
# desaparece, dejando la escena tranquila para el mensaje de hidratación.
BOSS_EXIT_FRAMES: int = 110   # duración del mutis (frames)
WATER_BREAK_TITLE = "Ve por un vaso de agua"
WATER_BREAK_SUBTITLE = "y estira las piernas"
WATER_BREAK_HINT = "Brazos arriba: otra ronda"

# --- Panel de cámara + pistas (sección izquierda, alto completo) ---
# El jugador se ve a sí mismo (feed con esqueleto de MediaPipe) y lee la pista de
# acción grande debajo. Es SOLO vista: se compone al lado del juego (game.py) y no
# toca la lógica ni render.project(). El frame viaja por controller.last_frame,
# fuera del ControllerState (el contrato con la cámara sigue puro).
CAM_PANEL_WIDTH: int = 480
COLOR_PANEL_BG = (18, 20, 26)
COLOR_PANEL_PLACEHOLDER = (40, 44, 54)   # caja "sin feed" en modo teclado

# Colores de la pista de acción (reusan la semántica de color del juego).
COLOR_CUE_JUMP = COLOR_OBSTACLE_JUMP     # ámbar: saltar
COLOR_CUE_DODGE = COLOR_CHASER           # rojo: cambiar de carril
COLOR_CUE_STRETCH = COLOR_STRETCH_FILL   # verde: estiramiento del jefe
COLOR_CUE_IDLE = COLOR_TEXT_DIM          # sin amenaza / neutro

# Amenaza DODGE para la pista "MUÉVETE": z (profundidad de render) a partir de la
# cual un DODGE en tu carril ya amerita avisar. Se elige un poco antes de la
# ventana de salto para dar tiempo de reacción con la latencia de la cámara.
CUE_DODGE_Z_MIN: float = 0.55
# Ventana más ANCHA (empieza más lejos) para elegir el carril libre que sugiere
# "MUÉVETE": descarta carriles cuyo DODGE aún no amerita aviso pero llegaría en
# seguida, evitando que la pista cambie de lado a mitad del esquive.
CUE_FREE_Z_MIN: float = 0.40

# Leyenda de gestos que se muestra bajo la pista (recordatorio permanente).
GESTURE_LEGEND = (
    "Inclina el torso  ->  cambiar de carril",
    "Sube ambos brazos ->  saltar",
    "Sosten la postura ->  danar al jefe",
)

# --- Onboarding (pantalla inicial de reglas + ubicación) ---
# Segundos de la pantalla de reglas antes de calibrar. Da tiempo a leer y, sobre
# todo, a colocarse frente a la cámara (medio cuerpo en el recuadro). Se puede
# saltar con cualquier tecla.
INTRO_SECONDS: int = 20
INTRO_TITLE = "OFFICE RUNNER"
INTRO_SUBTITLE = "Pausa activa: los controles SON los ejercicios"
# Historia: qué está pasando (se muestra arriba de las reglas en la intro).
# Líneas CORTAS: el área de juego es angosta (540px), frases largas no caben.
INTRO_STORY = (
    "Es viernes y un PDF no te deja salir.",
    "Corre por la oficina: esquiva y salta.",
    "No dejes que el PDF te alcance.",
    "Al final, tu jefe molesto te espera:",
    "cumple sus estiramientos para poder irte.",
)
INTRO_RULES = (
    "Alejate: cabeza y hombros dentro del recuadro",
    "Inclina el torso -> cambiar de carril",
    "Sube ambos brazos -> saltar los obstaculos bajos",
    "Esquiva los altos cambiandote de carril",
    "Un PDF te persigue: fallar lo acerca",
    "Al final, un jefe: vencelo sosteniendo estiramientos",
)
