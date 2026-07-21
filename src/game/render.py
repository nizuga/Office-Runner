"""
render.py — CAPA DE DIBUJO pseudo-3D (perspectiva tipo Temple Run).

⚠️ SOLO DIBUJO. Aquí no se decide nada de gameplay: colisiones, spawn, timing,
velocidad y control por carril siguen en coordenadas LÓGICAS (carril + profundidad)
en el resto del código, sin tocar. Esta capa solo traduce (carril, z) -> pantalla.

`project(lane, z)` es la ÚNICA fuente de verdad mundo->pantalla. Carriles,
obstáculos, jugador y PDF pasan TODOS por ella (checklist #1).

    lane : índice de carril, puede ser fraccionario (0..LANE_COUNT-1) para
           interpolar suave el cambio de carril del jugador.
    z    : profundidad de cercanía. 0.0 = horizonte (lejos), 1.0 = frente (cerca).
"""

from __future__ import annotations

import math

import pygame

from game import assets as visual_assets
from game import config

# ============================================================================
#  CONSTANTES DE PERSPECTIVA  —  TUNEA EL "FEEL" AQUÍ
# ============================================================================
HORIZON_Y: int = int(config.SCREEN_HEIGHT * 0.30)   # y del horizonte / punto de fuga
VANISHING_X: int = config.SCREEN_WIDTH // 2         # x del punto de fuga (centro)
# y donde el frente (z=1) toca el suelo = fila del jugador. Se deja una banda
# inferior libre (hasta el borde) para el PDF, así el jugador queda por ENCIMA
# del PDF y se distinguen bien (no incrustados).
GROUND_Y: int = int(config.SCREEN_HEIGHT * 0.80)

# Exponente de profundidad (checklist #3): >1 hace que los objetos ACELEREN al
# acercarse (sensación de perspectiva). 1.0 = lineal (se siente falso). Sube para
# más agresividad, baja para más suave.
DEPTH_EXP: float = 2.4

# Escala del sprite por distancia (checklist #6: mínimo > 0 para no degenerar).
SCALE_MAX: float = 1.20    # escala en el frente (z=1)
SCALE_MIN: float = 0.045   # escala en el horizonte (z=0), pequeña pero > 0

# Separación entre centros de carril, independiente del tamaño del sprite. El
# fondo ilustrado conserva pasillo visible lejos, aunque los objetos sean pequeños.
LANE_SPREAD_FAR: float = 50.0
LANE_SPREAD_NEAR: float = 198.0

# Rieles transversales que corren hacia el jugador (dan sensación de avance).
STRIPE_COUNT: int = 16
STRIPE_SPEED: float = 0.010   # cuánto avanzan por unidad de `speed`

# Franja-clave de SALTO: zona del piso donde saltar un JUMP te libra de verdad.
# Está CALIBRADA a la ventana segura real: se midió (sim) que un salto salva si se
# pulsa con el obstáculo en z∈[0.75, 0.90]; antes que 0.75 caes demasiado pronto y
# después de 0.90 ya no libras. La franja se ajusta DENTRO de esa ventana, con el
# borde final adelantado (~6 frames de colchón) para absorber la latencia de la
# cámara: mientras el obstáculo esté sobre el amarillo, saltar = seguro.
# (Si cambias JUMP_FRAMES / JUMP_HEIGHT / OBSTACLE_JUMP_HEIGHT, re-mide la ventana.)
JUMP_CUE_Z0: float = 0.75
JUMP_CUE_Z1: float = 0.85
COLOR_JUMP_CUE = (230, 184, 64)   # ámbar (asocia "ámbar = saltar aquí")

# PDF perseguidor: se dibuja SIEMPRE en la sección inferior (pegado abajo,
# detrás del jugador). Su tamaño crece al acercarse (menos distancia).
PDF_SCALE_FAR: float = 0.5    # lejos/seguro (distance alta)
PDF_SCALE_NEAR: float = 2.1   # encima/te alcanza (distance ~0)

# Elevación cosmética del jugador sobre el suelo (px de mundo, se escala por la
# distancia como cualquier lift). Solo separa visualmente al muñeco del PDF; NO
# toca la física (el rect de colisión sigue en PLAYER_BASE_Y).
PLAYER_DRAW_LIFT: float = 46.0

# Tamaño del ARTE del jugador (px de mundo). Independiente de PLAYER_SIZE, que
# es la caja de colisión lógica: el empleado se dibuja más alto que ancho sin
# tocar la física. Dimensionado para que los obstáculos guarden proporción
# creíble: la silla (220) queda ~1.5x el empleado, la caja (34) ~0.23x.
PLAYER_ART_W: float = 92.0
PLAYER_ART_H: float = 146.0
# Velocidad del ciclo de carrera: fracción de ciclo por unidad de `speed`.
RUN_CYCLE_SPEED: float = 0.0065
RUN_FRAME_COUNT: int = 6

# Mamparas de cubículo a los lados. El offset se mide en carriles desde el
# centro: la pista llega a ±1.5, así que 1.9 las deja justo por fuera.
WALL_LANE_OFFSET: float = 1.9
WALL_HEIGHT: float = 165.0     # alto de la mampara (px de mundo, escala con z)
WALL_RAIL_HEIGHT: float = 14.0  # riel superior
WALL_POST_COUNT: int = 10       # postes que corren hacia el jugador

# Medidor de meta (barra superior) y jefe final.
PROGRESS_BAR_Y: int = 46
PROGRESS_BAR_H: int = 12
BOSS_W: int = 210               # tamaño del sprite del jefe (px de pantalla)
BOSS_H: int = 190
BOSS_BOTTOM_Y: int = HORIZON_Y + 34   # se apoya sobre el horizonte, arriba
BOSS_BOB_AMPLITUDE: float = 6.0       # balanceo vertical (respiración)
BOSS_BOB_SPEED: float = 0.06
# ============================================================================

# Llaves cuyos maestros son arte pixel: se re-escalan con nearest (transform.scale)
# en vez de smoothscale, para conservar el look chunky sin difuminar.
_PIXEL_KEYS: set[str] = {
    "jump", "dodge", "pdf", "boss",
    "player_run_a", "player_run_b", "player_air",
    *(f"player_run_{index}" for index in range(RUN_FRAME_COUNT)),
}

# Supersampling de los sprites maestros: se dibujan a alta resolución una vez y
# se re-escalan SIEMPRE desde el maestro con smoothscale (checklist #7), nunca
# desde una superficie ya escalada -> sin borrosidad acumulada ni temblor.
_SS: int = 4
_masters: dict[str, tuple[pygame.Surface, float, float]] = {}
_scroll: float = 0.0  # fase de los rieles (estado SOLO de render)
_run_phase: float = 0.0  # fase del ciclo de carrera (estado SOLO de render)
_boss_bob: float = 0.0  # fase del balanceo del jefe (estado SOLO de render)
_jump_cue_surf: pygame.Surface | None = None  # franja-clave de salto (cacheada)
_flash_surf: pygame.Surface | None = None      # overlay rojo de error (cacheado)
_vignette_surf: pygame.Surface | None = None   # marco atmosferico cacheado
_track_overlay_surf: pygame.Surface | None = None  # carriles exactos sobre fondo IA
_fonts: dict[tuple[int, bool], pygame.font.Font] = {}  # cache de fuentes (ver _font)


def _font(size: int, bold: bool = False) -> pygame.font.Font:
    """Fuente del juego, cacheada. SysFont hace matching + carga del TTF en CADA
    llamada (varios ms): crearlas dentro de las funciones de dibujo por frame
    costaba FPS reales. Todo el texto pide sus fuentes aquí. El nombre viene de
    config.FONT_NAMES (lista con fallbacks: Consolas solo existe en Windows)."""
    key = (size, bold)
    f = _fonts.get(key)
    if f is None:
        f = pygame.font.SysFont(config.FONT_NAMES, size, bold=bold)
        _fonts[key] = f
    return f


def project(lane: float, z: float) -> tuple[float, float, float]:
    """Convierte (carril, profundidad) -> (screen_x, screen_y, scale).

    - z=0 (horizonte): los carriles se estrechan sin colapsar antes que el fondo.
    - z=1 (frente): carriles bien separados.
    - screen_y sigue una curva no lineal (#3) => aceleración al acercarse.
    - scale nunca es <= 0 (#6).
    """
    z = 0.0 if z < 0.0 else 1.0 if z > 1.0 else z
    t = z ** DEPTH_EXP                                   # profundidad no lineal (#3)
    scale = SCALE_MIN + (SCALE_MAX - SCALE_MIN) * t      # escala clamped > 0 (#6)
    screen_y = HORIZON_Y + (GROUND_Y - HORIZON_Y) * t
    center = (config.LANE_COUNT - 1) / 2.0
    # La separación lateral sigue al pasillo del fondo; el tamaño del sprite usa
    # `scale` por separado para que ambas perspectivas no se desincronicen.
    lane_spread = LANE_SPREAD_FAR + (LANE_SPREAD_NEAR - LANE_SPREAD_FAR) * t
    screen_x = VANISHING_X + (lane - center) * lane_spread
    return screen_x, screen_y, scale


# --- Sprites maestros (placeholders de color, listos para cambiar por arte) ---

def _make_master(base_w: float, base_h: float, color, label: str | None = None):
    w, h = max(1, int(base_w * _SS)), max(1, int(base_h * _SS))
    surf = pygame.Surface((w, h), pygame.SRCALPHA)
    radius = max(2, min(w, h) // 6)
    pygame.draw.rect(surf, color, (0, 0, w, h), border_radius=radius)
    # Banda de brillo superior: da volumen (lectura de "objeto 3D").
    hi = tuple(min(255, c + 34) for c in color)
    pygame.draw.rect(surf, hi, (0, 0, w, int(h * 0.30)), border_radius=radius)
    # Contorno oscuro para separar del fondo.
    pygame.draw.rect(surf, (16, 18, 22), (0, 0, w, h),
                     width=max(2, _SS), border_radius=radius)
    if label:
        f = _font(int(h * 0.42), bold=True)
        t = f.render(label, True, (255, 255, 255))
        surf.blit(t, t.get_rect(center=(w // 2, h // 2)))
    return surf, float(base_w), float(base_h)


def _shift(color, d: int):
    """Aclara (d>0) u oscurece (d<0) un color, clampeado a [0,255]."""
    return tuple(max(0, min(255, c + d)) for c in color)


def _shaded_box(surf, rect, color, *, hi: int = 30, lo: int = 26) -> None:
    """Rect con volumen barato: banda de brillo arriba + sombra abajo (3 tonos).

    Convierte un bloque plano en algo con lectura de forma sin usar gradientes
    reales (que el nearest-scale del arte pixel volvería sucios de todos modos)."""
    x, y, w, h = (int(v) for v in rect)
    band = max(1, int(h * 0.26))
    pygame.draw.rect(surf, color, (x, y, w, h))
    pygame.draw.rect(surf, _shift(color, hi), (x, y, w, band))
    pygame.draw.rect(surf, _shift(color, -lo), (x, y + h - band, w, band))


def _make_box_master(base_w: float, base_h: float):
    """Caja de cartón/mudanza (obstáculo JUMP): baja, ancha, a ras de piso.

    Bloques planos (look pixel) con la paleta ámbar de COLOR_OBSTACLE_JUMP para
    conservar la lectura "ámbar = salta". Se dibuja a resolución base (sin _SS)
    y se re-escala con nearest en draw_sprite -> pixels crocantes.
    """
    w, h = max(4, int(base_w)), max(4, int(base_h))
    surf = pygame.Surface((w, h), pygame.SRCALPHA)
    body = config.COLOR_OBSTACLE_JUMP
    lid = _shift(body, 30)          # tapa superior más clara
    tape = _shift(body, -70)        # cinta más oscura
    outline = (16, 18, 22)

    pygame.draw.rect(surf, body, (0, 0, w, h))                 # cuerpo
    lid_h = max(2, int(h * 0.32))
    pygame.draw.rect(surf, lid, (0, 0, w, lid_h))              # tapa
    # Cintas en cruz (vertical al centro + horizontal donde cierra la tapa).
    tw = max(2, w // 12)
    pygame.draw.rect(surf, tape, (w // 2 - tw // 2, 0, tw, h))
    pygame.draw.rect(surf, tape, (0, lid_h - max(1, tw // 2), w, max(2, tw)))
    pygame.draw.rect(surf, outline, (0, 0, w, h), width=max(2, w // 40))
    return surf, float(base_w), float(base_h)


def _make_chair_master(base_w: float, base_h: float):
    """Silla de oficina (obstáculo DODGE): alta, bloquea el carril -> esquivar.

    Respaldo + asiento en paleta roja (COLOR_OBSTACLE_DODGE, "rojo = esquivar"),
    columna y base metálicas con ruedas. Bloques planos, re-escalado nearest.
    """
    w, h = max(6, int(base_w)), max(8, int(base_h))
    surf = pygame.Surface((w, h), pygame.SRCALPHA)
    red = config.COLOR_OBSTACLE_DODGE
    red_hi = _shift(red, 28)
    red_lo = _shift(red, -46)
    metal = (92, 96, 108)
    metal_lo = (60, 63, 72)
    outline = (16, 18, 22)

    cx = w // 2
    # Respaldo (tercio superior, angosto y centrado).
    back_w = int(w * 0.62)
    back_h = int(h * 0.42)
    back_x = cx - back_w // 2
    pygame.draw.rect(surf, red, (back_x, 0, back_w, back_h))
    pygame.draw.rect(surf, red_hi, (back_x, 0, back_w, max(2, back_h // 4)))  # brillo
    pygame.draw.rect(surf, outline, (back_x, 0, back_w, back_h), width=max(2, w // 30))

    # Asiento (slab horizontal ancho, justo debajo del respaldo).
    seat_y = int(h * 0.46)
    seat_h = int(h * 0.14)
    pygame.draw.rect(surf, red, (0, seat_y, w, seat_h))
    pygame.draw.rect(surf, red_lo, (0, seat_y + seat_h - max(2, seat_h // 3), w, max(2, seat_h // 3)))
    pygame.draw.rect(surf, outline, (0, seat_y, w, seat_h), width=max(2, w // 30))

    # Columna central (metálica) desde el asiento hacia la base.
    col_w = max(3, w // 10)
    col_top = seat_y + seat_h
    col_bottom = int(h * 0.86)
    pygame.draw.rect(surf, metal, (cx - col_w // 2, col_top, col_w, col_bottom - col_top))

    # Base con patas/ruedas (barra + ruedas a los extremos y centro).
    base_y = col_bottom
    legs_h = h - base_y
    pygame.draw.rect(surf, metal, (int(w * 0.12), base_y, int(w * 0.76), max(2, legs_h // 2)))
    wheel_r = max(2, legs_h // 3)
    for wx in (int(w * 0.15), cx, int(w * 0.85)):
        pygame.draw.rect(surf, metal_lo, (wx - wheel_r, h - 2 * wheel_r, 2 * wheel_r, 2 * wheel_r))
    return surf, float(base_w), float(base_h)


def _make_employee_master(shirt, pose: str):
    """El jugador: un empleado visto DE ESPALDAS (corre hacia el fondo).

    Por eso no lleva cara — se ve nuca, camisa, lanyard con gafete y zapatos.
    `pose` ∈ {"run_a", "run_b", "air"}: las dos primeras alternan el paso; la
    tercera encoge las piernas y sube los brazos durante el salto.

    Ojo: el tamaño del arte (PLAYER_ART_*) NO es la caja de colisión
    (PLAYER_SIZE). Aquí solo se dibuja.
    """
    w, h = int(PLAYER_ART_W), int(PLAYER_ART_H)
    surf = pygame.Surface((w, h), pygame.SRCALPHA)
    skin = config.COLOR_PLAYER_SKIN
    hair = config.COLOR_PLAYER_HAIR
    pants = config.COLOR_PLAYER_PANTS
    shoes = config.COLOR_PLAYER_SHOES
    badge = config.COLOR_PLAYER_BADGE
    shirt_hi = _shift(shirt, 30)
    shirt_lo = _shift(shirt, -30)
    outline = (16, 18, 22)
    cx = w // 2

    # Cabeza REDONDEADA (de espaldas: casi todo pelo) con brillo, nuca y orejas.
    head_w, head_h = int(w * 0.46), int(h * 0.26)
    hx = cx - head_w // 2
    pygame.draw.ellipse(surf, hair, (hx, 0, head_w, head_h))
    pygame.draw.ellipse(surf, _shift(hair, 20),
                        (hx + int(head_w * 0.16), int(head_h * 0.10),
                         int(head_w * 0.42), int(head_h * 0.34)))     # remolino de pelo
    nape_h = max(2, int(head_h * 0.24))
    pygame.draw.rect(surf, skin, (hx + int(head_w * 0.14), head_h - nape_h,
                                  int(head_w * 0.72), nape_h))         # nuca (piel)
    for ex in (hx - 1, hx + head_w - int(head_w * 0.14)):              # orejas
        pygame.draw.ellipse(surf, skin, (ex, int(head_h * 0.44),
                                         int(head_w * 0.16), int(head_h * 0.28)))
    pygame.draw.ellipse(surf, outline, (hx, 0, head_w, head_h), width=2)

    # Cuello corto + cuello de la camisa (una V clara sobre los hombros).
    neck_w = int(head_w * 0.42)
    neck_y = head_h - max(1, int(h * 0.01))
    pygame.draw.rect(surf, _shift(skin, -14), (cx - neck_w // 2, neck_y, neck_w, int(h * 0.04)))

    # Torso / camisa CON VOLUMEN (banda de brillo arriba, sombra abajo).
    torso_y = head_h + max(1, int(h * 0.03))
    torso_h = int(h * 0.34)
    torso_w = int(w * 0.72)
    tx = cx - torso_w // 2
    _shaded_box(surf, (tx, torso_y, torso_w, torso_h), shirt, hi=30, lo=30)
    # Costura de hombros + columna (dan lectura de "espalda").
    pygame.draw.line(surf, shirt_lo, (tx, torso_y + 2), (tx + torso_w, torso_y + 2), 1)
    pygame.draw.line(surf, shirt_lo, (cx, torso_y + 4), (cx, torso_y + torso_h - 4), 1)
    # Lanyard en V (dos tiras desde los hombros al gafete) — así se lee de espaldas.
    badge_cx, badge_cy = cx, torso_y + int(torso_h * 0.52)
    pygame.draw.line(surf, outline, (cx - int(torso_w * 0.22), torso_y), (badge_cx, badge_cy), 2)
    pygame.draw.line(surf, outline, (cx + int(torso_w * 0.22), torso_y), (badge_cx, badge_cy), 2)
    bw_, bh_ = max(4, int(w * 0.14)), max(4, int(h * 0.075))
    pygame.draw.rect(surf, badge, (badge_cx - bw_ // 2, badge_cy, bw_, bh_))
    pygame.draw.rect(surf, _shift(badge, 30), (badge_cx - bw_ // 2, badge_cy, bw_, max(1, bh_ // 3)))
    pygame.draw.rect(surf, outline, (badge_cx - bw_ // 2, badge_cy, bw_, bh_), width=1)
    pygame.draw.rect(surf, outline, (tx, torso_y, torso_w, torso_h), width=2)

    # Brazos a los costados (2 tonos: cara externa en sombra) + mano redondeada.
    arm_w = max(3, int(w * 0.13))
    arm_h = int(torso_h * 0.80)
    if pose == "air":
        offs = (-int(h * 0.10), -int(h * 0.10))   # ambos arriba
    elif pose == "run_a":
        offs = (int(h * 0.01), int(h * 0.07))
    else:
        offs = (int(h * 0.07), int(h * 0.01))
    for side, dy in zip((-1, 1), offs):
        ax = tx - arm_w if side < 0 else tx + torso_w
        ay = torso_y + dy
        pygame.draw.rect(surf, shirt, (ax, ay, arm_w, arm_h))
        shadow_x = ax if side < 0 else ax + arm_w - max(2, arm_w // 3)
        pygame.draw.rect(surf, shirt_lo, (shadow_x, ay, max(2, arm_w // 3), arm_h))
        pygame.draw.ellipse(surf, skin, (ax, ay + arm_h - arm_w, arm_w, arm_w))   # mano
        pygame.draw.rect(surf, outline, (ax, ay, arm_w, arm_h), width=1)

    # Cinturón entre camisa y pantalón.
    pants_y = torso_y + torso_h
    pygame.draw.rect(surf, _shift(pants, -30), (tx, pants_y - max(2, int(h * 0.02)),
                                                torso_w, max(2, int(h * 0.02))))

    # Piernas: la zancada es la diferencia de largo entre ambas (2 tonos + zapatos).
    shoe_h = max(3, int(h * 0.055))
    full = h - pants_y - shoe_h
    leg_w = max(4, int(w * 0.22))
    if pose == "air":
        lengths = (int(full * 0.55), int(full * 0.55))
        gap = leg_w // 2                     # piernas recogidas y juntas
    elif pose == "run_a":
        lengths = (full, int(full * 0.62))
        gap = leg_w
    else:
        lengths = (int(full * 0.62), full)
        gap = leg_w

    for side, length in zip((-1, 1), lengths):
        lx = cx + side * gap - (leg_w if side < 0 else 0)
        pygame.draw.rect(surf, pants, (lx, pants_y, leg_w, length))
        pygame.draw.rect(surf, _shift(pants, 16), (lx, pants_y, max(2, leg_w // 4), length))  # pliegue
        pygame.draw.rect(surf, shoes, (lx - 1, pants_y + length, leg_w + 2, shoe_h))
        pygame.draw.rect(surf, _shift(shoes, 26), (lx - 1, pants_y + length, leg_w + 2, max(1, shoe_h // 3)))
        pygame.draw.rect(surf, outline, (lx, pants_y, leg_w, length), width=1)

    return surf, PLAYER_ART_W, PLAYER_ART_H


def _make_boss_master(base_w: float, base_h: float):
    """El jefe estresado: cabeza, cejas de enojo, traje y corbata.

    Bloques planos (mismo lenguaje pixel que caja/silla). Se dibuja a tamaño
    final, así que se blitea directo sin re-escalar.
    """
    w, h = int(base_w), int(base_h)
    surf = pygame.Surface((w, h), pygame.SRCALPHA)
    skin = config.COLOR_BOSS_SKIN
    skin_lo = _shift(skin, -20)
    suit = config.COLOR_BOSS_SUIT
    suit_hi = _shift(suit, 24)
    suit_lo = _shift(suit, -26)
    shirt = config.COLOR_BOSS_SHIRT
    tie = config.COLOR_BOSS_TIE
    hair_c = (48, 40, 38)
    outline = (16, 18, 22)
    cx = w // 2

    suit_y = int(h * 0.52)
    shoulder_r = int(w * 0.16)

    # Cuello (piel) que baja de la cabeza al traje.
    neck_w = int(w * 0.20)
    pygame.draw.rect(surf, skin_lo, (cx - neck_w // 2, suit_y - int(h * 0.07), neck_w, int(h * 0.12)))

    # Torso / traje con HOMBROS anchos y redondeados + volumen.
    pygame.draw.rect(surf, suit, (0, suit_y, w, h - suit_y), border_radius=shoulder_r)
    pygame.draw.rect(surf, suit_hi, (int(w * 0.05), suit_y + 2, w - int(w * 0.10), int(h * 0.06)),
                     border_radius=int(w * 0.08))
    pygame.draw.rect(surf, suit_lo, (0, h - int(h * 0.10), w, int(h * 0.10)),
                     border_radius=shoulder_r)

    # Camisa: cuña central + solapas (V) del saco.
    sh_w = int(w * 0.28)
    pygame.draw.polygon(surf, shirt, [
        (cx - sh_w // 2, suit_y), (cx + sh_w // 2, suit_y), (cx, h)])
    for sgn in (-1, 1):                                   # solapas del saco
        pygame.draw.polygon(surf, suit_lo, [
            (cx + sgn * sh_w // 2, suit_y),
            (cx + sgn * int(w * 0.20), suit_y),
            (cx, suit_y + int(h * 0.20))])
    # Nudo + corbata roja (corta: el resto queda tras los brazos cruzados).
    tie_w = max(4, int(w * 0.07))
    pygame.draw.polygon(surf, tie, [
        (cx - tie_w, suit_y + int(h * 0.02)), (cx + tie_w, suit_y + int(h * 0.02)),
        (cx + int(tie_w * 0.7), suit_y + int(h * 0.16)), (cx - int(tie_w * 0.7), suit_y + int(h * 0.16))])

    # Brazos CRUZADOS sobre el pecho (postura imponente de jefe).
    th = int(w * 0.16)
    hand_y = suit_y + int(h * 0.17)
    arms = (
        (int(w * 0.84), h - 2, int(w * 0.40), hand_y),   # der: codo abajo-der -> mano izq
        (int(w * 0.16), h - 2, int(w * 0.60), hand_y),   # izq: por encima
    )
    for x0, y0, x1, y1 in arms:
        pygame.draw.line(surf, suit_lo, (x0, y0), (x1, y1), th + 4)
        pygame.draw.line(surf, suit, (x0, y0), (x1, y1), th)
        pygame.draw.line(surf, suit_hi, (x0, int(y0 - th * 0.2)), (x1, int(y1 - th * 0.2)), max(2, th // 6))
    for hx_ in (int(w * 0.40), int(w * 0.60)):           # manos (puños) de piel
        pygame.draw.circle(surf, skin, (hx_, hand_y), int(th * 0.55))
        pygame.draw.circle(surf, skin_lo, (hx_, hand_y), int(th * 0.55), width=2)

    # --- Cabeza (mitad superior, centrada y redondeada) ---
    head_w = int(w * 0.44)
    head_h = int(h * 0.52)
    head_x = cx - head_w // 2
    for ex in (head_x - int(head_w * 0.08), head_x + head_w - int(head_w * 0.08)):   # orejas
        pygame.draw.ellipse(surf, skin, (ex, int(head_h * 0.42), int(head_w * 0.18), int(head_h * 0.24)))
    pygame.draw.ellipse(surf, skin, (head_x, 0, head_w, head_h))
    pygame.draw.ellipse(surf, hair_c, (head_x, -int(head_h * 0.06), head_w, int(head_h * 0.46)))  # pelo
    pygame.draw.ellipse(surf, outline, (head_x, 0, head_w, head_h), width=3)

    # Ojos (blanco + pupila) + cejas fruncidas hacia el centro.
    eye_w = max(4, int(head_w * 0.22))
    eye_h = max(4, int(head_h * 0.13))
    eye_y = int(head_h * 0.46)
    for sign in (-1, 1):
        ex = cx + sign * int(head_w * 0.22) - eye_w // 2
        pygame.draw.ellipse(surf, shirt, (ex, eye_y, eye_w, eye_h))
        pygame.draw.circle(surf, outline, (ex + eye_w // 2 - sign * eye_w // 6, eye_y + eye_h // 2), max(2, eye_h // 2))
        brow_y = eye_y - int(eye_h * 1.1)
        inner = (cx + sign * int(head_w * 0.10), brow_y + eye_h)
        outer = (cx + sign * int(head_w * 0.34), brow_y - eye_h // 2)
        pygame.draw.line(surf, hair_c, outer, inner, max(3, eye_h // 2))

    # Boca: ceño tenso, comisuras hacia abajo (arco de enojo).
    mouth_w = int(head_w * 0.38)
    my = int(head_h * 0.74)
    pygame.draw.lines(surf, outline, False, [
        (cx - mouth_w // 2, my), (cx, my - max(2, eye_h // 3)), (cx + mouth_w // 2, my)], 3)

    # Gota de sudor (estrés de deadline) en la sien.
    sweat_x = head_x + head_w - int(head_w * 0.02)
    sweat_y = int(head_h * 0.40)
    pygame.draw.circle(surf, (150, 205, 235), (sweat_x, sweat_y), max(3, int(head_w * 0.06)))
    pygame.draw.polygon(surf, (150, 205, 235), [
        (sweat_x - int(head_w * 0.05), sweat_y), (sweat_x + int(head_w * 0.05), sweat_y),
        (sweat_x, sweat_y - int(head_h * 0.09))])
    return surf, float(base_w), float(base_h)


def _ensure_masters() -> None:
    if _masters:
        return
    ow = config.obstacle_width()
    fallbacks = {
        "boss": lambda: _make_boss_master(BOSS_W, BOSS_H),
        "player_run_0": lambda: _make_employee_master(config.COLOR_PLAYER, "run_a"),
        "player_run_1": lambda: _make_employee_master(config.COLOR_PLAYER, "run_a"),
        "player_run_2": lambda: _make_employee_master(config.COLOR_PLAYER, "run_a"),
        "player_run_3": lambda: _make_employee_master(config.COLOR_PLAYER, "run_b"),
        "player_run_4": lambda: _make_employee_master(config.COLOR_PLAYER, "run_b"),
        "player_run_5": lambda: _make_employee_master(config.COLOR_PLAYER, "run_b"),
        "player_run_a": lambda: _make_employee_master(config.COLOR_PLAYER, "run_a"),
        "player_run_b": lambda: _make_employee_master(config.COLOR_PLAYER, "run_b"),
        "player_air": lambda: _make_employee_master(config.COLOR_PLAYER_AIR, "air"),
        "jump": lambda: _make_box_master(ow, config.OBSTACLE_JUMP_HEIGHT),
        "dodge": lambda: _make_chair_master(ow, config.OBSTACLE_DODGE_HEIGHT),
        "pdf": lambda: _make_master(ow * 1.15, 96, config.COLOR_CHASER, label="PDF"),
    }
    for key, fallback in fallbacks.items():
        _masters[key] = visual_assets.load_sprite(key) or fallback()


def _draw_contact_shadow(surface, cx: float, ground_y: float, w: float, risen: float) -> None:
    """Elipse tenue en el SUELO bajo un sprite (lo asienta, evita el 'flotar').

    `ground_y` es la fila del suelo (antes del salto); `risen` son los px que el
    sprite subió por el salto: la sombra se encoge y aclara con la altura.
    """
    t = 0.0 if w <= 0 else min(0.6, risen / 150.0)   # 0 en el piso -> 0.6 en lo alto
    sw = max(4, int(w * (1.0 - 0.5 * t)))
    sh = max(3, int(w * 0.16 * (1.0 - 0.35 * t)))
    alpha = int(85 * (1.0 - 0.55 * t))
    shadow = pygame.Surface((sw, sh), pygame.SRCALPHA)
    pygame.draw.ellipse(shadow, (0, 0, 0, alpha), (0, 0, sw, sh))
    surface.blit(shadow, (int(cx - sw / 2), int(ground_y - sh / 2)))


def draw_sprite(surface, key: str, lane: float, z: float, *,
                y_lift: float = 0.0, rest_lift: float = 0.0, shadow: bool = True,
                x_shift: float = 0.0, y_scale: float = 1.0) -> None:
    """Dibuja un sprite anclado por su BORDE INFERIOR-CENTRO al suelo (#4).

    y_lift: desplazamiento vertical total (px de mundo), se escala por la
    distancia para que el arco encoja con la perspectiva.
    rest_lift: parte de `y_lift` que es elevación COSMÉTICA de reposo (no salto).
    La sombra se ancla bajo los pies (a esa altura de reposo) y solo se encoge
    con la porción de SALTO, para no verse despegada del personaje elevado.
    """
    _ensure_masters()
    master, bw, bh = _masters[key]
    sx, ground_y, scale = project(lane, z)
    sx += x_shift * scale
    sy = ground_y - y_lift * scale
    w = max(1, int(bw * scale))
    h = max(1, int(bh * scale * y_scale))
    # Sombra bajo los pies (altura de reposo); se achica con el salto real.
    if shadow:
        foot_y = ground_y - rest_lift * scale
        jump_risen = max(0.0, (y_lift - rest_lift) * scale)
        _draw_contact_shadow(surface, sx, foot_y, w, jump_risen)
    # Re-escala SIEMPRE desde el maestro (#7). Arte pixel -> nearest (chunky);
    # el resto -> smoothscale (suave, sin borrosidad acumulada).
    if key in _PIXEL_KEYS:
        img = pygame.transform.scale(master, (w, h))
    else:
        img = pygame.transform.smoothscale(master, (w, h))
    surface.blit(img, (int(sx - w / 2), int(sy - h)))   # ancla inferior-centro (#4)


# --- Suelo / carriles ---

def draw_static_background(surface, key: str) -> None:
    """Fondo ilustrado exacto 540x900, con fallback al escenario procedural."""
    background = visual_assets.load_background(key)
    if background is None:
        draw_ground(surface, 0.0, jump_cue=False)
        return
    if background.get_size() == surface.get_size():
        surface.blit(background, (0, 0))
    else:
        surface.blit(pygame.transform.smoothscale(background, surface.get_size()), (0, 0))

def _draw_back_wall(surface) -> None:
    """Pared de oficina sobre el horizonte (donde aparece el jefe).

    El centro se deja libre a propósito: ahí se dibuja el jefe.
    """
    pygame.draw.rect(surface, config.COLOR_WALL, (0, 0, config.SCREEN_WIDTH, HORIZON_Y))
    # Zócalo: separa pared de piso y refuerza la línea del horizonte.
    pygame.draw.rect(surface, config.COLOR_WALL_TRIM,
                     (0, HORIZON_Y - 8, config.SCREEN_WIDTH, 8))

    # Reloj de pared, a la izquierda.
    ccx, ccy, r = 90, 96, 26
    pygame.draw.circle(surface, config.COLOR_WALL_TRIM, (ccx, ccy), r)
    pygame.draw.circle(surface, config.COLOR_CLOCK, (ccx, ccy), r, 3)
    pygame.draw.line(surface, config.COLOR_CLOCK, (ccx, ccy), (ccx, ccy - 15), 2)
    pygame.draw.line(surface, config.COLOR_CLOCK, (ccx, ccy), (ccx + 11, ccy + 6), 2)

    # Cartel de SALIDA, a la derecha (el chiste: nunca llegas).
    sx, sy, sw, sh = config.SCREEN_WIDTH - 132, 80, 96, 32
    pygame.draw.rect(surface, config.COLOR_EXIT_SIGN, (sx, sy, sw, sh), border_radius=4)
    txt = _font(17, bold=True).render("SALIDA", True, (18, 30, 22))
    surface.blit(txt, txt.get_rect(center=(sx + sw // 2, sy + sh // 2)))


def _draw_cubicle_side(surface, lane: float) -> None:
    """Una mampara de cubículo corriendo hacia el horizonte, con postes cíclicos.

    `project` es lineal en la profundidad interpolada `t`, así que la base y el
    borde superior de la mampara son rectas en pantalla: basta un trapecio.
    Los postes usan la MISMA fase `_scroll` que los rieles, así corren a la par.
    """
    x0, y0, s0 = project(lane, 0.0)
    x1, y1, s1 = project(lane, 1.0)
    top0 = y0 - WALL_HEIGHT * s0
    top1 = y1 - WALL_HEIGHT * s1

    pygame.draw.polygon(surface, config.COLOR_CUBICLE,
                        [(x0, top0), (x1, top1), (x1, y1), (x0, y0)])
    # Riel superior: engrosa el borde de arriba para leerlo como mampara.
    pygame.draw.polygon(surface, config.COLOR_CUBICLE_RAIL, [
        (x0, top0), (x1, top1),
        (x1, top1 + WALL_RAIL_HEIGHT * s1), (x0, top0 + WALL_RAIL_HEIGHT * s0),
    ])

    # Postes divisorios que avanzan hacia el jugador.
    for k in range(WALL_POST_COUNT):
        z = (k + _scroll) / WALL_POST_COUNT
        if z < 0.05:          # demasiado cerca del punto de fuga: solo ruido
            continue
        px, py, ps = project(lane, z)
        pygame.draw.line(surface, config.COLOR_CUBICLE_POST,
                         (px, py - WALL_HEIGHT * ps), (px, py), max(1, int(7 * ps)))


def _edge_line(surface, edge: float, color, width: int) -> None:
    x0, y0, _ = project(edge, 0.0)
    x1, y1, _ = project(edge, 1.0)
    pygame.draw.line(surface, color, (x0, y0), (x1, y1), width)


def _get_illustrated_track_overlay() -> pygame.Surface:
    """Pista alineada con project(); atenua las lineas imperfectas del fondo IA."""
    global _track_overlay_surf
    if _track_overlay_surf is not None:
        return _track_overlay_surf

    overlay = pygame.Surface((config.SCREEN_WIDTH, config.SCREEN_HEIGHT), pygame.SRCALPHA)
    lane_colors = ((9, 28, 54, 58), (12, 34, 64, 42), (9, 28, 54, 58))
    for lane in range(config.LANE_COUNT):
        left = lane - 0.5
        right = lane + 0.5
        polygon = [
            project(left, 0.0)[:2], project(right, 0.0)[:2],
            project(right, 1.0)[:2], project(left, 1.0)[:2],
        ]
        pygame.draw.polygon(overlay, lane_colors[lane], polygon)

    line_color = (125, 151, 184, 150)
    edge_color = (76, 104, 141, 135)
    for edge in (0.5, 1.5):
        pygame.draw.line(overlay, line_color, project(edge, 0.0)[:2],
                         project(edge, 1.0)[:2], 2)
    for edge in (-0.5, 2.5):
        pygame.draw.line(overlay, edge_color, project(edge, 0.0)[:2],
                         project(edge, 1.0)[:2], 3)
    _track_overlay_surf = overlay
    return overlay


def _get_jump_cue_surf() -> pygame.Surface:
    """Superficie translúcida con la franja-clave de salto (se calcula una vez)."""
    global _jump_cue_surf
    if _jump_cue_surf is not None:
        return _jump_cue_surf
    surf = pygame.Surface((config.SCREEN_WIDTH, config.SCREEN_HEIGHT), pygame.SRCALPHA)
    left, right = -0.5, config.LANE_COUNT - 0.5
    poly = [
        project(left, JUMP_CUE_Z0)[:2], project(right, JUMP_CUE_Z0)[:2],
        project(right, JUMP_CUE_Z1)[:2], project(left, JUMP_CUE_Z1)[:2],
    ]
    pygame.draw.polygon(surf, (*COLOR_JUMP_CUE, 46), poly)          # relleno tenue
    # Bordes de la franja para que se lea el "entra aquí / sal aquí".
    pygame.draw.line(surf, (*COLOR_JUMP_CUE, 140), poly[0], poly[1], 2)
    pygame.draw.line(surf, (*COLOR_JUMP_CUE, 140), poly[3], poly[2], 2)
    _jump_cue_surf = surf
    return surf


def draw_ground(surface, speed: float, *, jump_cue: bool = True) -> None:
    """Dibuja pared/horizonte, la pista en perspectiva y rieles que avanzan.

    `jump_cue=False` oculta la franja ámbar: fuera del run no se salta, así que
    mostrarla sería una señal falsa.
    """
    global _scroll

    # El PNG conserva la perspectiva y el arte de oficina. Todo este bloque
    # procedural queda activo como fallback si el asset no esta disponible.
    background = visual_assets.load_background("office")
    illustrated = background is not None
    if illustrated:
        surface.blit(background, (0, 0))
    else:
        surface.fill(config.COLOR_BG)
        _draw_back_wall(surface)

    # Pista como trapecio (bordes exteriores de los carriles).
    left, right = -0.5, config.LANE_COUNT - 0.5
    tl_x, tl_y, _ = project(left, 0.0)
    tr_x, tr_y, _ = project(right, 0.0)
    bl_x, bl_y, _ = project(left, 1.0)
    br_x, br_y, _ = project(right, 1.0)
    if not illustrated:
        pygame.draw.polygon(surface, config.COLOR_TRACK,
                            [(tl_x, tl_y), (tr_x, tr_y), (br_x, br_y), (bl_x, bl_y)])
    else:
        surface.blit(_get_illustrated_track_overlay(), (0, 0))

    # Rieles transversales que corren hacia el jugador (sensación de avance).
    _scroll = (_scroll + speed * STRIPE_SPEED) % 1.0
    for k in range(STRIPE_COUNT):
        z = ((k + _scroll) / STRIPE_COUNT)
        lx, ly, _ = project(left, z)
        rx, ry, _ = project(right, z)
        if illustrated:
            color = (52, 72, 101) if (k % 2 == 0) else (35, 51, 76)
        else:
            shade = 44 if (k % 2 == 0) else 30
            color = (shade, shade + 3, shade + 8)
        pygame.draw.line(surface, color, (lx, ly), (rx, ry), 1)

    # Mamparas de cubículo a ambos lados (después de `_scroll`, van sincronizadas).
    center = (config.LANE_COUNT - 1) / 2.0
    if not illustrated:
        _draw_cubicle_side(surface, center - WALL_LANE_OFFSET)
        _draw_cubicle_side(surface, center + WALL_LANE_OFFSET)

    # Líneas divisorias / bordes de carril (siguen la perspectiva calibrada).
    if not illustrated:
        for e in (0.5, config.LANE_COUNT - 1.5):
            _edge_line(surface, e, config.COLOR_LANE_LINE, 2)
        _edge_line(surface, left, config.COLOR_LANE_LINE, 3)
        _edge_line(surface, right, config.COLOR_LANE_LINE, 3)

    # Franja-clave de salto encima del piso (clave visual de "salta aquí").
    if jump_cue:
        surface.blit(_get_jump_cue_surf(), (0, 0))


def _draw_jump_bar(surface, z: float) -> None:
    """Obstáculo JUMP dibujado como barra baja que cruza los 3 carriles.

    Coherente con la física: el rect lógico también ocupa todo el ancho (obliga a
    saltar). Se extiende de borde a borde de la pista en perspectiva (project en
    carriles fraccionarios -0.5 y LANE_COUNT-0.5) y se ancla por su base al suelo.
    """
    xL, ground_y, scale = project(-0.5, z)
    xR, _, _ = project(config.LANE_COUNT - 0.5, z)
    bar_h = max(4, int(config.OBSTACLE_JUMP_HEIGHT * scale))
    left, width = int(xL), max(4, int(xR - xL))
    top = int(ground_y - bar_h)
    _ensure_masters()
    master, _bw, _bh = _masters["jump"]
    img = pygame.transform.scale(master, (width, bar_h))
    surface.blit(img, (left, top))


def _draw_jump_chevron(surface, lane: float, z: float) -> None:
    """Flecha ámbar sobre un JUMP dentro de la franja: 'salta AHORA'."""
    sx, sy, scale = project(lane, z)
    size = max(8, int(26 * scale))
    top = sy - int(config.OBSTACLE_JUMP_HEIGHT * scale) - size - 6
    pygame.draw.polygon(surface, COLOR_JUMP_CUE, [
        (sx, top), (sx - size, top + size), (sx + size, top + size),
    ])


# --- Helpers de conversión de estado lógico -> parámetros de proyección ---

def lane_of_player(player) -> float:
    """Carril fraccionario del jugador desde su X lógica (para lerp visual)."""
    return (player.x - config.LANE_MARGIN) / config.lane_width() - 0.5


def z_of_obstacle(obs) -> float:
    """Profundidad de cercanía del obstáculo desde su Y lógica (0 lejos, 1 cerca)."""
    return obs.y / config.PLAYER_BASE_Y


def _player_key(player) -> str:
    """Pose del jugador: en el aire, o el paso que toque del ciclo de carrera."""
    if player.in_air:
        return "player_air"
    frame = min(RUN_FRAME_COUNT - 1, int(_run_phase * RUN_FRAME_COUNT))
    return f"player_run_{frame}"


def _draw_runner_dust(surface, game) -> None:
    """Particulas pixel bajo los pies; decorativas y deterministas."""
    if game.speed <= 0 or game.player.in_air:
        return
    cx, ground_y, _ = project(lane_of_player(game.player), 1.0)
    phase = int(_run_phase * 12)
    colors = ((206, 220, 232), (128, 154, 180), (82, 105, 134))
    for i in range(7):
        age = (phase + i * 3) % 12
        side = -1 if i % 2 == 0 else 1
        x = int(cx + side * (12 + age * 2.4))
        y = int(ground_y + 12 - age * 1.8)
        size = max(1, 4 - age // 4)
        pygame.draw.rect(surface, colors[i % len(colors)], (x, y, size, size))


def _get_vignette() -> pygame.Surface:
    global _vignette_surf
    if _vignette_surf is None:
        vignette = pygame.Surface((config.SCREEN_WIDTH, config.SCREEN_HEIGHT), pygame.SRCALPHA)
        for i in range(18):
            alpha = max(1, 4 - i // 5)
            pygame.draw.rect(
                vignette, (4, 8, 18, alpha * 6),
                (i, i, config.SCREEN_WIDTH - i * 2, config.SCREEN_HEIGHT - i * 2), width=1,
            )
        _vignette_surf = vignette
    return _vignette_surf


def draw_running(surface, game, state) -> None:
    """Dibuja un frame completo del run en perspectiva, con orden de pintor (#5)."""
    global _run_phase
    draw_ground(surface, game.speed)
    # El ciclo de carrera avanza con la velocidad: más rápido = pasos más rápidos.
    _run_phase = (_run_phase + game.speed * RUN_CYCLE_SPEED) % 1.0

    # Reunir todo lo del mundo con su z y ordenar de lejano a cercano (#5).
    drawables: list[tuple[float, callable]] = []

    for obs in game.obstacles:
        z = z_of_obstacle(obs)
        # Culling: al llegar al frente (sección inferior) desaparece, no se
        # queda amontonado; su lógica de colisión ya se resolvió en ese punto.
        if z > 1.0:
            continue
        if obs.type.name == "JUMP":
            in_cue = JUMP_CUE_Z0 <= z <= JUMP_CUE_Z1
            drawables.append((z, lambda s, z=z, cue=in_cue: (
                _draw_jump_bar(s, z),
                [_draw_jump_chevron(s, ln, z) for ln in range(config.LANE_COUNT)]
                if cue else None,
            )))
        else:
            drawables.append((z, lambda s, o=obs, z=z: draw_sprite(s, "dodge", o.lane, z)))

    # Jugador: siempre en la fila del frente (z=1), con su offset de salto.
    p = game.player
    pkey = _player_key(p)
    if p.in_air:
        run_bob = 0.0
        run_sway = 0.0
        run_scale_y = 1.0
    else:
        stride = math.sin(math.tau * _run_phase)
        # Las seis poses ya contienen contacto, compresion e impulso. Este
        # movimiento secundario es intencionalmente leve: evita el deslizamiento
        # sin deformar el personaje ni competir con el flipbook.
        run_bob = 2.0 * abs(math.sin(math.tau * _run_phase * 2.0))
        run_sway = 1.25 * stride
        run_scale_y = 1.0
    drawables.append((1.0, lambda s: draw_sprite(s, pkey, lane_of_player(p), 1.0,
                                                  y_lift=p.jump_offset + PLAYER_DRAW_LIFT + run_bob,
                                                  rest_lift=PLAYER_DRAW_LIFT,
                                                  x_shift=run_sway,
                                                  y_scale=run_scale_y)))

    # PDF perseguidor: en la sección inferior, DETRÁS del jugador y de los
    # obstáculos (persigue desde atrás). Se dibuja antes para que el cuadrado
    # amarillo (JUMP) y el jugador queden por encima y no los tape.
    _draw_pdf(surface, game)

    drawables.sort(key=lambda d: d[0])   # lejano primero
    for _z, fn in drawables:
        fn(surface)

    _draw_runner_dust(surface, game)
    surface.blit(_get_vignette(), (0, 0))
    _draw_chaser_bar(surface, game.chaser)
    _draw_hud(surface, game, state)
    _draw_damage_flash(surface, game.hit_flash)   # tiñe toda la escena al chocar


def _draw_pdf(surface, game) -> None:
    """PDF pegado al borde inferior, siguiendo el carril del jugador."""
    _ensure_masters()
    master, bw, bh = _masters["pdf"]
    proximity = 1.0 - game.chaser.distance          # 0 lejos, 1 encima
    scale = PDF_SCALE_FAR + (PDF_SCALE_NEAR - PDF_SCALE_FAR) * proximity
    x, _sy, _s = project(lane_of_player(game.player), 1.0)
    y_bottom = config.SCREEN_HEIGHT - 4
    w = max(1, int(bw * scale))
    h = max(1, int(bh * scale))
    img = pygame.transform.scale(master, (w, h))
    surface.blit(img, (int(x - w / 2), int(y_bottom - h)))


def _draw_chaser_bar(surface, chaser) -> None:
    """Barra de AMENAZA del PDF (HUD). Se LLENA cuando el PDF se acerca.

    Muestra `1 - distance` (0 = lejos/seguro, 1 = te alcanza) para que sea
    intuitivo con la etiqueta 'PDF': roja llena = peligro. La lógica de distancia
    no cambia; esto es solo la lectura visual.
    """
    bar_w, bar_h = 14, config.SCREEN_HEIGHT - 140
    bx = config.SCREEN_WIDTH - config.LANE_MARGIN + 8
    by = 78
    pygame.draw.rect(surface, config.COLOR_CHASER_BAR_BG, (bx, by, bar_w, bar_h), border_radius=6)
    threat = 1.0 - chaser.distance
    fill_h = int(bar_h * threat)
    # Crece desde abajo: a más amenaza, más barra roja hacia arriba.
    pygame.draw.rect(surface, config.COLOR_CHASER,
                     (bx, by + (bar_h - fill_h), bar_w, fill_h), border_radius=6)
    label = _font(16, bold=True).render("PDF", True, config.COLOR_CHASER)
    surface.blit(label, label.get_rect(center=(bx + bar_w // 2, by - 14)))


def _get_flash_surf() -> pygame.Surface:
    """Overlay rojo full-screen (relleno una vez; el alpha se varía por frame)."""
    global _flash_surf
    if _flash_surf is None:
        surf = pygame.Surface((config.SCREEN_WIDTH, config.SCREEN_HEIGHT))
        surf.fill(config.COLOR_HIT_FLASH)
        _flash_surf = surf
    return _flash_surf


def _draw_damage_flash(surface, frames: int) -> None:
    """Destello rojo de error que se desvanece con los frames restantes."""
    if frames <= 0:
        return
    surf = _get_flash_surf()
    alpha = int(config.HIT_FLASH_ALPHA_MAX * frames / config.HIT_FLASH_FRAMES)
    surf.set_alpha(alpha)
    surface.blit(surf, (0, 0))


def draw_progress_meter(surface, progress: float) -> None:
    """Barra superior: distancia recorrida hasta la meta (donde espera el jefe)."""
    progress = 0.0 if progress < 0.0 else 1.0 if progress > 1.0 else progress
    x0 = config.LANE_MARGIN
    # Deja aire a la derecha para no chocar con la barra vertical del PDF.
    x1 = config.SCREEN_WIDTH - config.LANE_MARGIN - 24
    w = x1 - x0

    pygame.draw.rect(surface, config.COLOR_PROGRESS_BG,
                     (x0, PROGRESS_BAR_Y, w, PROGRESS_BAR_H), border_radius=6)
    fill = int(w * progress)
    if fill > 0:
        pygame.draw.rect(surface, config.COLOR_PROGRESS_FILL,
                         (x0, PROGRESS_BAR_Y, fill, PROGRESS_BAR_H), border_radius=6)
    # Marca de meta al final de la barra (a la derecha no cabe texto: ahí está
    # la etiqueta "PDF" de la barra del perseguidor).
    pygame.draw.rect(surface, config.COLOR_GOAL,
                     (x1 - 3, PROGRESS_BAR_Y - 5, 5, PROGRESS_BAR_H + 10))

    label = _font(15, bold=True).render(f"META {int(progress * 100)}%", True, config.COLOR_GOAL)
    surface.blit(label, label.get_rect(midbottom=(x0 + w // 2, PROGRESS_BAR_Y - 2)))


def _boss_hit_t(boss_hit: int) -> float:
    """Progreso de la animación de golpe: 1.0 en el impacto -> 0.0 al terminar."""
    frames = config.BOSS_HIT_ANIM_FRAMES
    return (boss_hit / frames) if (frames and boss_hit > 0) else 0.0


def _draw_boss(surface, boss_hit: int) -> None:
    """El jefe, arriba de la pantalla, con balanceo y animación de daño.

    Al recibir un golpe (boss_hit>0): RETROCEDE hacia arriba con un tirón, destella
    en aditivo, y sobre él aparece un estallido de impacto + un "-1" que sube."""
    global _boss_bob
    _ensure_masters()
    master, bw, bh = _masters["boss"]
    _boss_bob += BOSS_BOB_SPEED
    bob = math.sin(_boss_bob) * BOSS_BOB_AMPLITUDE
    x = VANISHING_X - int(bw) // 2
    y = int(BOSS_BOTTOM_Y + bob) - int(bh)

    t = _boss_hit_t(boss_hit)
    bx = x + int(6 * t * math.sin(boss_hit * 2.0))       # jitter horizontal
    by = y - int(config.BOSS_HIT_RECOIL * t)             # retroceso hacia arriba
    surface.blit(master, (bx, by))
    if t > 0:
        # Destello blanco aditivo sobre la silueta (alpha 0 preserva la forma). Con
        # t*t el brillo cae rápido: fogonazo corto en vez de un jefe lavado.
        hit = master.copy()
        add = int(config.BOSS_HIT_FLASH_ADD * t * t)
        hit.fill((add, add, add, 0), special_flags=pygame.BLEND_RGBA_ADD)
        surface.blit(hit, (bx, by))
        _draw_hit_fx(surface, x + int(bw) // 2, y + int(bh) // 2, bw, int(bh), t)


def _draw_hit_fx(surface, cx: int, cy: int, bw: float, bh: int, t: float) -> None:
    """Estallido de impacto (aro + rayos) que crece y se desvanece, + "-1" que sube."""
    burst_r = int(bw * (0.30 + (1.0 - t) * 0.55))
    alpha = int(210 * t)
    pad = burst_r + 12
    ov = pygame.Surface((pad * 2, pad * 2), pygame.SRCALPHA)
    col = (*config.COLOR_BOSS_HIT, alpha)
    pygame.draw.circle(ov, col, (pad, pad), burst_r, width=max(2, int(7 * t)))
    for k in range(8):                                    # rayos de "pow"
        ang = math.tau * k / 8
        p0 = (pad + math.cos(ang) * burst_r * 0.72, pad + math.sin(ang) * burst_r * 0.72)
        p1 = (pad + math.cos(ang) * burst_r * 1.18, pad + math.sin(ang) * burst_r * 1.18)
        pygame.draw.line(ov, col, p0, p1, max(2, int(5 * t)))
    surface.blit(ov, (cx - pad, cy - pad))

    # "-1" flotante: sube DESDE arriba del jefe (fondo oscuro) y se desvanece. Con
    # contorno negro para leerse aunque pase sobre el sprite.
    font = _font(38, bold=True)
    ty = cy - int(bh * 0.42) - int((1.0 - t) * 44)
    a = int(255 * t)
    outline = font.render("-1", True, (10, 10, 12)); outline.set_alpha(a)
    for ox, oy in ((-2, 0), (2, 0), (0, -2), (0, 2)):
        surface.blit(outline, outline.get_rect(center=(cx + ox, ty + oy)))
    txt = font.render("-1", True, config.COLOR_BOSS_HIT); txt.set_alpha(a)
    surface.blit(txt, txt.get_rect(center=(cx, ty)))


def draw_boss_exit(surface, t: float) -> None:
    """Mutis del jefe vencido: se retira hacia la SALIDA (borde derecho) dando
    pasitos, hasta salir de pantalla. `t` es el progreso 0.0 (recién vencido,
    aún al centro) -> 1.0 (ya se fue). Se usa al entrar a WATER_BREAK."""
    _ensure_masters()
    master, bw, bh = _masters["boss"]
    start_x = VANISHING_X - bw / 2
    end_x = config.SCREEN_WIDTH + bw * 0.2          # justo fuera del borde
    x = start_x + (end_x - start_x) * t
    bob = math.sin(t * math.tau * 3.0) * 5.0        # zarandeo de caminata
    y = BOSS_BOTTOM_Y - bh + bob
    surface.blit(master, (int(x), int(y)))


def _draw_boss_health(surface, boss, boss_hit: int = 0) -> None:
    """Barra de vida del jefe, arriba (segmentada: un tramo por estiramiento)."""
    x0 = config.LANE_MARGIN
    w = config.SCREEN_WIDTH - 2 * config.LANE_MARGIN
    y, h = PROGRESS_BAR_Y, 16
    pygame.draw.rect(surface, config.COLOR_BOSS_HEALTH_BG, (x0, y, w, h), border_radius=6)
    fill = int(w * boss.health_ratio)
    if fill > 0:
        pygame.draw.rect(surface, config.COLOR_BOSS_HEALTH, (x0, y, fill, h), border_radius=6)
    # Separadores entre tramos de vida.
    for i in range(1, boss.max_health):
        sx = x0 + w * i // boss.max_health
        pygame.draw.line(surface, config.COLOR_BG, (sx, y), (sx, y + h), 2)

    # Parpadeo del segmento recién perdido (el tramo vacío inmediato a la vida).
    t = _boss_hit_t(boss_hit)
    if t > 0 and boss.health < boss.max_health:
        seg = boss.health
        sx0 = x0 + w * seg // boss.max_health
        sx1 = x0 + w * (seg + 1) // boss.max_health
        flash = pygame.Surface((max(1, sx1 - sx0), h), pygame.SRCALPHA)
        flash.fill((*config.COLOR_BOSS_HIT, int(190 * t)))
        surface.blit(flash, (sx0, y))

    label = _font(16, bold=True).render("JEFE", True, config.COLOR_TEXT)
    surface.blit(label, label.get_rect(midbottom=(config.SCREEN_WIDTH // 2, y - 3)))


def _draw_stretch_prompt(surface, boss, state) -> None:
    """Qué estiramiento pide el jefe y cuánto llevas sosteniéndolo."""
    cx = config.SCREEN_WIDTH // 2
    y = config.SCREEN_HEIGHT - 150

    title = _font(24, bold=True).render(boss.required_label, True, config.COLOR_TEXT)
    surface.blit(title, title.get_rect(center=(cx, y)))

    # El progreso solo cuenta si la postura sostenida es la que el jefe pide.
    active = state.active_stretch == boss.required_stretch
    progress = state.stretch_progress if active else 0.0

    bar_w, bar_h = 260, 14
    bx = cx - bar_w // 2
    by = y + 24
    pygame.draw.rect(surface, config.COLOR_PROGRESS_BG, (bx, by, bar_w, bar_h), border_radius=7)
    fill = int(bar_w * progress)
    if fill > 0:
        pygame.draw.rect(surface, config.COLOR_STRETCH_FILL, (bx, by, fill, bar_h), border_radius=7)

    hint = _font(16).render(config.BOSS_STRETCH_HINT, True, config.COLOR_TEXT_DIM)
    surface.blit(hint, hint.get_rect(center=(cx, by + bar_h + 16)))


def _draw_boss_scene(surface, game, state) -> None:
    """Contenido de la escena del jefe: pista quieta, jefe, jugador y prompt."""
    draw_ground(surface, 0.0, jump_cue=False)   # speed=0: los rieles no corren
    _draw_boss(surface, game.boss_hit)
    _draw_boss_health(surface, game.boss, game.boss_hit)

    p = game.player
    draw_sprite(surface, _player_key(p), lane_of_player(p), 1.0,
                y_lift=PLAYER_DRAW_LIFT, rest_lift=PLAYER_DRAW_LIFT)

    # Vencido: ya no pide posturas (la pantalla de victoria toma el relevo).
    if not game.boss.defeated:
        _draw_stretch_prompt(surface, game.boss, state)


def draw_boss_fight(surface, game, state) -> None:
    """Escena del jefe. Al recibir daño, SACUDE la escena (offset amortiguado)."""
    t = _boss_hit_t(game.boss_hit)
    if t <= 0:
        _draw_boss_scene(surface, game, state)
        return
    # Golpe: render a una escena aparte y blit con desplazamiento que decae con t.
    amp = config.BOSS_HIT_SHAKE * t
    dx = int(amp * math.sin(game.boss_hit * 1.7))
    dy = int(amp * 0.6 * math.cos(game.boss_hit * 2.3))
    scene = pygame.Surface((config.SCREEN_WIDTH, config.SCREEN_HEIGHT))
    scene.fill(config.COLOR_BG)
    _draw_boss_scene(scene, game, state)
    surface.fill(config.COLOR_BG)                # borde expuesto por la sacudida
    surface.blit(scene, (dx, dy))


def _draw_hud(surface, game, state) -> None:
    # (El texto "vel:" de desarrollo se quitó: con velocidad fija no informa nada.)
    draw_progress_meter(surface, game.run_progress)


# ============================================================================
#  PANEL DE CÁMARA + PISTAS  —  sección izquierda (alto completo)
# ============================================================================
# Puro dibujo, igual que el resto de render.py. `window` es la ventana REAL (ancha);
# el panel ocupa su franja izquierda [0, CAM_PANEL_WIDTH). El juego se dibuja aparte
# a su lienzo 540×900 y game.py lo blitea a la derecha. No pasa por project().

_PANEL_MARGIN: int = 20


def _render_fit(text: str, max_w: int, size: int, color, *, bold: bool = False,
                min_size: int = 12) -> pygame.Surface:
    """Renderiza `text` encogiendo la fuente hasta que quepa en `max_w` (px).

    Evita que etiquetas largas (p. ej. 'Cruza el brazo IZQUIERDO') se salgan del
    panel. Baja de a 2 px hasta `min_size`; si aun así no cabe, devuelve a min_size.
    """
    s = size
    while s > min_size:
        surf = _font(s, bold=bold).render(text, True, color)
        if surf.get_width() <= max_w:
            return surf
        s -= 2
    return _font(min_size, bold=bold).render(text, True, color)


def _frame_to_surface(frame) -> pygame.Surface:
    """Convierte un frame de OpenCV (numpy BGR, HxWx3) a Surface de pygame (RGB).

    Import de numpy PEREZOSO: solo hay frame en modo cámara, así render.py sigue
    siendo importable sin numpy en pruebas de lógica pura.
    """
    import numpy as np

    rgb = np.ascontiguousarray(frame[:, :, ::-1])   # BGR -> RGB, contiguo
    h, w = rgb.shape[0], rgb.shape[1]
    return pygame.image.frombuffer(rgb.tobytes(), (w, h), "RGB")


def _draw_panel_feed(window, frame, feed_x: int, feed_y: int, feed_w: int) -> int:
    """Dibuja el feed (o el placeholder) y devuelve la Y del borde inferior."""
    if frame is not None:
        surf = _frame_to_surface(frame)
        fw, fh = surf.get_width(), surf.get_height()
        feed_h = int(feed_w * fh / fw) if fw else int(feed_w * 3 / 4)
        img = pygame.transform.smoothscale(surf, (feed_w, feed_h))
        window.blit(img, (feed_x, feed_y))
        pygame.draw.rect(window, config.COLOR_GOAL,
                         (feed_x - 3, feed_y - 3, feed_w + 6, feed_h + 6),
                         width=3, border_radius=10)
        pygame.draw.rect(window, config.COLOR_TEXT_DIM,
                         (feed_x, feed_y, feed_w, feed_h), width=1, border_radius=8)
        return feed_y + feed_h

    # Sin cámara (modo teclado): caja placeholder 4:3 + aviso.
    feed_h = int(feed_w * 3 / 4)
    pygame.draw.rect(window, config.COLOR_PANEL_PLACEHOLDER,
                     (feed_x, feed_y, feed_w, feed_h), border_radius=8)
    pygame.draw.rect(window, config.COLOR_GOAL,
                     (feed_x - 3, feed_y - 3, feed_w + 6, feed_h + 6),
                     width=3, border_radius=10)
    label = _font(22, bold=True).render("CAMARA OFF", True, config.COLOR_TEXT_DIM)
    window.blit(label, label.get_rect(center=(feed_x + feed_w // 2, feed_y + feed_h // 2)))
    return feed_y + feed_h


def _draw_gesture_legend(window, cx: int, y: int) -> None:
    """Recordatorio permanente de los gestos, bajo la pista."""
    font = _font(15)
    for i, line in enumerate(config.GESTURE_LEGEND):
        txt = font.render(line, True, config.COLOR_TEXT_DIM)
        window.blit(txt, txt.get_rect(center=(cx, y + i * 22)))


def draw_camera_panel(window, frame, cue) -> None:
    """Panel izquierdo: feed del jugador (arriba) + pista de acción (abajo).

    frame : numpy BGR de OpenCV con el esqueleto ya dibujado, o None (modo teclado).
    cue   : (texto_principal, subtexto, color) — lo produce game._action_cue().
    """
    panel_w = config.CAM_PANEL_WIDTH
    cx = panel_w // 2
    pygame.draw.rect(window, config.COLOR_PANEL_BG, (0, 0, panel_w, config.SCREEN_HEIGHT))

    feed_w = panel_w - 2 * _PANEL_MARGIN
    feed_bottom = _draw_panel_feed(window, frame, _PANEL_MARGIN, _PANEL_MARGIN, feed_w)

    # --- Zona de pista, bajo el feed ---
    main_text, sub_text, color = cue
    normalized = main_text.upper()
    if "SALTA" in normalized:
        icon_key = "jump"
    elif "MUEVETE" in normalized or "ALCANZO" in normalized:
        icon_key = "dodge"
    elif any(word in normalized for word in ("BRAZO", "CABEZA", "GANASTE", "AGUA")):
        icon_key = "stretch"
    else:
        icon_key = "logo"

    icon = visual_assets.load_icon(icon_key)
    icon_size = 64
    icon_y = feed_bottom + 16
    if icon is not None:
        image = pygame.transform.scale(icon, (icon_size, icon_size))
        window.blit(image, image.get_rect(midtop=(cx, icon_y)))

    zone_top = feed_bottom + 102
    text_max_w = panel_w - 2 * _PANEL_MARGIN   # margen a ambos lados: nunca se corta

    title = _render_fit(main_text, text_max_w, 48, color, bold=True)
    window.blit(title, title.get_rect(center=(cx, zone_top)))

    if sub_text:
        sub = _render_fit(sub_text, text_max_w, 22, config.COLOR_TEXT)
        window.blit(sub, sub.get_rect(center=(cx, zone_top + 44)))

    # Leyenda de gestos anclada más abajo (recordatorio fijo).
    _draw_gesture_legend(window, cx, config.SCREEN_HEIGHT - 120)


def draw_intro(surface, seconds_left: int) -> None:
    """Pantalla de reglas rápidas + cuenta atrás, sobre el lienzo del juego (540 ancho).

    Da tiempo a leer y a ubicarse frente a la cámara (el feed en vivo está en el
    panel izquierdo). Cualquier tecla la salta.
    """
    cx = config.SCREEN_WIDTH // 2
    max_w = config.SCREEN_WIDTH - 2 * _PANEL_MARGIN

    # Velo oscuro para que el texto resalte sobre la pista dibujada detrás.
    veil = pygame.Surface((config.SCREEN_WIDTH, config.SCREEN_HEIGHT), pygame.SRCALPHA)
    veil.fill((14, 16, 22, 210))
    surface.blit(veil, (0, 0))

    logo = visual_assets.load_icon("logo")
    if logo is not None:
        mark = pygame.transform.scale(logo, (62, 62))
        surface.blit(mark, mark.get_rect(center=(78, 118)))

    title = _render_fit(config.INTRO_TITLE, max_w - 64, 44, config.COLOR_TEXT, bold=True)
    surface.blit(title, title.get_rect(center=(cx, 118)))
    sub = _render_fit(config.INTRO_SUBTITLE, max_w, 18, config.COLOR_TEXT_DIM)
    surface.blit(sub, sub.get_rect(center=(cx, 154)))

    # Historia: qué está pasando, en una "tarjeta" narrativa sobre las reglas.
    story_top, story_line = 188, 30
    card_h = story_line * len(config.INTRO_STORY) + 24
    card = pygame.Surface((max_w, card_h), pygame.SRCALPHA)
    card.fill((0, 0, 0, 0))
    pygame.draw.rect(card, (34, 38, 50, 235), (0, 0, max_w, card_h), border_radius=10)
    pygame.draw.rect(card, config.COLOR_GOAL, (0, 0, 4, card_h))   # filo de acento
    surface.blit(card, (_PANEL_MARGIN, story_top))
    y = story_top + 22
    for line in config.INTRO_STORY:
        row = _render_fit(line, max_w - 28, 17, config.COLOR_TEXT)
        surface.blit(row, row.get_rect(midleft=(_PANEL_MARGIN + 16, y)))
        y += story_line

    # Encabezado + reglas, alineadas a la izquierda con bullet.
    y = story_top + card_h + 26
    header = _render_fit("Como se juega:", max_w, 20, config.COLOR_GOAL, bold=True)
    surface.blit(header, header.get_rect(midleft=(_PANEL_MARGIN + 6, y)))
    y += 34
    for line in config.INTRO_RULES:
        row = _render_fit(f"-  {line}", max_w, 18, config.COLOR_TEXT)
        surface.blit(row, row.get_rect(midleft=(_PANEL_MARGIN + 6, y)))
        y += 40

    # Cuenta atrás + cómo saltarla.
    count = _render_fit(f"Empieza en {max(0, seconds_left)}s", max_w, 28,
                        config.COLOR_GOAL, bold=True)
    surface.blit(count, count.get_rect(center=(cx, config.SCREEN_HEIGHT - 128)))
    skip = _render_fit("(cualquier tecla para empezar ya)", max_w, 17, config.COLOR_TEXT_DIM)
    surface.blit(skip, skip.get_rect(center=(cx, config.SCREEN_HEIGHT - 96)))


def draw_transition(surface, frames: int) -> None:
    """Fundido de entrada corto al cambiar de estado, sin pausar gameplay."""
    if frames <= 0 or config.TRANSITION_FRAMES <= 0:
        return
    ratio = min(1.0, frames / config.TRANSITION_FRAMES)
    veil = pygame.Surface((config.SCREEN_WIDTH, config.SCREEN_HEIGHT), pygame.SRCALPHA)
    veil.fill((5, 8, 16, int(190 * ratio * ratio)))
    surface.blit(veil, (0, 0))
