# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Qué es esto

Runner de oficina en **pygame**, controlado por poses de cámara. Proyecto de dos personas
divididas por una única interfaz (`ControllerState`):

- **Persona A** (fuera de este código todavía): OpenCV + MediaPipe → detección de pose,
  calibración, gestos. Su trabajo es *poblar* un `ControllerState`.
- **Persona B** (este código): el juego completo — loop, render, carriles, salto, obstáculos,
  perseguidor, jefe. *Consume* un `ControllerState` cada frame.

El plan de trabajo día-por-día de Persona B está en [plan_persona_juego.md](plan_persona_juego.md)
— léelo antes de agregar features; define alcance, orden de recorte y checkpoints.

## Comandos

Requiere **Python 3.11** (no 3.13 — restricción del venv compartido por MediaPipe de Persona A).

```bash
# Setup (una vez)
py -3.11 -m venv .venv
./.venv/Scripts/python.exe -m pip install -r requirements.txt

# Correr el juego
./.venv/Scripts/python.exe main.py
```

No hay framework de tests aún. La lógica se valida con scripts headless usando
`SDL_VIDEODRIVER=dummy` (+ `pygame.display.set_mode` para render) para instanciar pygame sin
ventana: se ejercitan el evento de salto de un frame, el clamp de carriles, la colisión JUMP/DODGE
(incluido el invariante "DODGE no saltable"), el tope/fijeza de velocidad, los invariantes de
`project()` (estrechamiento de carriles, no-linealidad, escala>0) y un run completo con render.
Para inspección visual, `pygame.image.save(screen, ...)` a PNG bajo el driver dummy.

## Arquitectura

**La frontera es `ControllerState`** ([src/game/controller_state.py](src/game/controller_state.py)):
un dataclass de solo-lectura que el juego lee una vez por frame. Todo lo que el juego necesita
saber del jugador pasa por aquí — `lane` (0/1/2), `jump` (evento de UN frame), `calibrated`, y
en modo jefe `active_stretch`/`stretch_progress`. **El juego nunca escribe estos campos.**

**La fuente del estado es intercambiable.** Hoy la produce [keyboard_controller.py](src/game/keyboard_controller.py)
(stub de teclado). El Día 3 se cambia `KeyboardController()` por el controlador de cámara real
y *nada más del juego cambia*. Cualquier fuente debe exponer `handle_event(event)` +
`get_state() -> ControllerState`; opcionalmente `reset()` (el juego la llama al reiniciar un run
para re-centrar el carril — sin eso el carril recordado del run anterior arrastra al jugador) y
`close()` (liberar recursos al salir). **La cámara lee la webcam en un HILO propio**: su
`get_state()` nunca bloquea (devuelve una foto del último estado) y el flanco de `jump` se acumula
como latch hasta que el juego lo consume. Sin el hilo, `capture.read()` + MediaPipe frenaban el
loop al ritmo de la webcam y, con física por-frame, todo el juego corría en cámara lenta.

**`jump` es un evento de un frame, no un estado.** Patrón crítico: se acumula en `handle_event`
(al recibir el KEYDOWN) y se limpia en `get_state`. Así una tecla/pose mantenida dispara el salto
exactamente una vez. No romper esto — es el contrato con la cámara (que ya entrega el flanco
"desbotonado").

**`active_stretch`/`stretch_progress` son lo contrario: estado SOSTENIDO, no evento.** El stub de
teclado rampa `stretch_progress` mientras la tecla 1/2/3 sigue abajo (`STRETCH_HOLD_FRAMES`) y lo
resetea en el KEYUP — imitando a la cámara, que reporta cuánto lleva sostenida la postura. No
"consumirlos" en `get_state`.

**Todo el juego es una máquina de estados** ([game.py](src/game/game.py), enum `GameState`):
`INTRO → CALIBRATING → RUNNING → BOSS_FIGHT → VICTORY → WATER_BREAK`, con `GAME_OVER` como salida
de RUNNING. `Game.run()` hace: poll de eventos → `controller.get_state()` → `_update(state)` según
el estado activo → `_draw(state)`. Todos los estados están implementados. VICTORY, WATER_BREAK y
GAME_OVER avanzan/reinician también con el gesto de salto (`state.jump` = brazos arriba), no solo
con el teclado: en modo cámara el jugador está lejos de las teclas. WATER_BREAK relanza un run
nuevo (no es un callejón sin salida); al entrar, el jefe vencido hace MUTIS hacia la SALIDA
(`Game.boss_exit` frames, `render.draw_boss_exit`) y el mensaje pide ir por un vaso de agua y
estirar las piernas (textos en `config.WATER_BREAK_*`). Con teclado (sin `start_calibration`) la INTRO salta directo
a RUNNING, sin el frame suelto de "Calibrando...". Al pasar a GAME_OVER se pone `speed = 0` para
congelar piso y zancada tras el texto de derrota, y `hit_flash` se sigue desvaneciendo ahí (si no,
el flash rojo del golpe final quedaba congelado tiñendo la pantalla).

**RUNNING termina por distancia, no por tiempo.** `Game.distance` acumula `speed` por frame y
`run_progress` (0..1) alimenta el medidor superior de meta. Al llegar a `RUN_GOAL_DISTANCE` se
limpian los obstáculos y se pasa a `BOSS_FIGHT` (perder contra el PDF tiene prioridad). El spawn
se corta cuando un obstáculo nuevo ya no alcanzaría a llegar al jugador antes de la meta
(`distance < RUN_GOAL_DISTANCE − PLAYER_BASE_Y`): así el corte de escena nunca borra obstáculos
aún visibles a mitad de pista.

**Entidades** llevan su propio estado LÓGICO y **no se dibujan solas** (el render está
centralizado, ver abajo):
- `Player` ([player.py](src/game/player.py)): interpola su X hacia el centro del carril objetivo
  (lerp, no salto instantáneo) y anima el salto como un arco `sin(pi·p)` sobre `JUMP_FRAMES`;
  expone `rect` (huella carril×profundidad; **no sube al saltar** — la altura del salto NO es
  profundidad) para colisiones.
- `Obstacle` ([obstacle.py](src/game/obstacle.py)): tipo `JUMP` (barra baja que cruza los 3
  carriles → OBLIGA a saltar) o `DODGE` (alto, un solo carril → cambiarse de carril). Baja en `y`
  (profundidad) a `speed` px/frame. **La colisión separa profundidad de altura:** los `rect` (AABB)
  resuelven el plano carril×profundidad, y el choque solo cuenta si además
  `player.jump_offset < obstacle.height` (la altura decide si el salto libra). **El `rect` del JUMP
  ocupa TODO el ancho de la pista** (`LANE_MARGIN`..`SCREEN_WIDTH-LANE_MARGIN`): no se puede
  esquivar de lado, hay que saltarlo — pero es jumpable, así que tapar los 3 carriles NO lo vuelve
  "imposible". El del DODGE ocupa un carril. **Invariante de diseño:** `OBSTACLE_DODGE_HEIGHT >
  JUMP_HEIGHT` para que un DODGE NUNCA se pueda saltar. Su render acompaña: el JUMP se dibuja como
  barra ancha (`_draw_jump_bar`), el DODGE como sprite de carril. `has_passed_player()` corta la
  ventana de peligro cuando el borde inferior cruza la línea del jugador — el MISMO umbral del
  culling de render (`z>1`), y se evalúa antes que el choque: lo que ya no se ve no hace daño.
- `Chaser` ([chaser.py](src/game/chaser.py)): el "PDF perseguidor". `distance` 0..1 (1=lejos,
  0=GAME_OVER). Chocar llama `on_hit` (–`CHASER_HIT_PENALTY`), pasar bien un obstáculo llama
  `on_dodge` (+`CHASER_DODGE_REWARD`). El castigo pesa más que el premio a propósito. **La barra
  HUD del PDF muestra AMENAZA (`1 - distance`): se llena roja cuando el PDF se acerca** (lectura
  intuitiva); la lógica de `distance` no cambia, es solo la vista (`_draw_chaser_bar`).
- `Boss` ([boss.py](src/game/boss.py)): el jefe final. Pide un estiramiento a la vez
  (`required_stretch`, de `BOSS_STRETCH_SEQUENCE` — 5 posturas de pausa activa: `arms_cross`,
  `neck_tilt_L`, `neck_tilt_R`, `arm_reach_L`, `arm_reach_R`); cuando el jugador SOSTIENE esa
  postura `BOSS_STRETCH_HOLD_SECONDS` (hasta `stretch_progress == 1.0`), pierde 1 de vida.
  `BOSS_MAX_HEALTH` se DERIVA de la longitud de la secuencia (cambiar la secuencia reajusta la
  vida y las teclas 1..N del stub, sin tocar `Boss`). El flag interno `_armed` garantiza **un
  golpe por postura**: hay que soltar o cambiar de pose para volver a dañar (análogo a "jump es
  un evento de un frame"). Vida a 0 → VICTORY. La detección de cada postura vive en
  `camera_controller._detect_stretch` (umbrales relativos a `shoulder_width`); el stub de teclado
  las simula con teclas 1..5.

La lógica de spawn/colisión/perseguidor/velocidad vive en `Game._update_running`. **Velocidad fija:**
`SPEED_ACCEL = 0` mantiene `speed` constante en `SPEED_START` (la rampa progresiva está desactivada;
subir `SPEED_ACCEL` la reactiva).

**La colisión es LÓGICA, el dibujo es pseudo-3D — y no se mezclan.** La física corre en
coordenadas de gameplay (`rect` = carril + profundidad Y), nunca en píxeles de pantalla. Toda la
vista en perspectiva vive en [render.py](src/game/render.py), cuya función `project(lane, z) ->
(screen_x, screen_y, scale)` es el ÚNICO punto de conversión mundo→pantalla (carriles, obstáculos,
jugador y PDF pasan todos por ella). `render.draw_running` ordena por profundidad (painter's
algorithm), ancla cada sprite por su borde inferior-centro al suelo, hace culling de obstáculos que
pasan el frente (`z>1`), dibuja el PDF en la banda inferior (detrás del jugador) y una **franja-clave
de salto** (`JUMP_CUE_Z0/Z1`) con chevron para señalizar cuándo saltar (se oculta con
`draw_ground(..., jump_cue=False)` fuera del run: sería una señal falsa). Re-escala los sprites
SIEMPRE desde un maestro, con `smoothscale` salvo los de `_PIXEL_KEYS`, que usan nearest para no
difuminar el arte pixel. Todas las fuentes salen de `render._font` (cache a nivel de módulo; crear
SysFont por frame costaba FPS) y el nombre viene de `config.FONT_NAMES`, una lista con fallbacks
multiplataforma (Consolas solo existe en Windows; en macOS cae a Menlo/Monaco). **Regla:** al
cambiar gameplay, no tocar render.py; al cambiar la vista, no
tocar la lógica de colisión/spawn/velocidad. Las constantes de perspectiva (`HORIZON_Y`,
`VANISHING_X`, `GROUND_Y`, `DEPTH_EXP`, `SCALE_MAX/MIN`, `LANE_SPREAD_FAR/NEAR`) están agrupadas arriba
de render.py.

**La ventana se compone: panel de cámara (izq) + juego (der).** El juego se dibuja SIEMPRE a un
lienzo propio de `SCREEN_WIDTH×SCREEN_HEIGHT` (`Game.canvas`) — por eso `project()` y todo render.py
siguen creyendo que la pantalla mide 540×900 —, y `Game.run()` lo blitea a la derecha de la ventana
real (ancha = `CAM_PANEL_WIDTH + SCREEN_WIDTH`). A la izquierda, `render.draw_camera_panel` pinta el
feed de la webcam (con el esqueleto de MediaPipe, arriba) y la **pista de acción** grande debajo
(¡SALTA!, ¡MUÉVETE!, el estiramiento pedido) + una leyenda de gestos. La pista la calcula
`Game._action_cue` LEYENDO el estado (obstáculos, jugador, jefe) y reusando `z_of_obstacle` /
`lane_of_player` / la ventana del chevron, así el texto queda sincronizado con la señal del piso;
no decide gameplay. **El frame de la cámara viaja por `controller.last_frame`, un canal LATERAL
fuera del `ControllerState`** (el contrato con Persona A sigue puro); con teclado no hay frame y el
panel muestra un placeholder "CÁMARA OFF" (las pistas igual funcionan, derivan del juego).

**La guía-fantasma del jefe (para quien nunca ha estirado).** En BOSS_FIGHT la cámara dibuja sobre
el feed una **diana por articulación** de la postura pedida, anclada a los hombros EN VIVO y escalada
por su ancho (invariante a la distancia): pones el brazo/cabeza sobre el trazo y esa parte se pone
**verde** (ámbar + flecha "hacia aquí" mientras falta). Esa MISMA comparación es la detección —
`camera_controller._evaluate_pose` mide cada punto contra `config.STRETCH_GUIDE_TARGETS` con
tolerancia `STRETCH_GUIDE_TOL`; la postura CUENTA (y la barra sube) solo cuando TODAS aciertan. Lo
que ves es lo que se mide, así que **corregir un lado invertido en cámara = cambiar el signo del
offset en config** (arregla trazo y detección a la vez). Para saber qué dibujar, el juego escribe la
postura pedida en `controller.target_stretch` — otro canal LATERAL, ahora de ENTRADA (análogo a
`last_frame` de salida), sin tocar `ControllerState`. El teclado no tiene ese atributo (no hay feed).

**El entorno de oficina es procedural, sin assets.** `_draw_back_wall` pinta la pared sobre el
horizonte (reloj, cartel de SALIDA; el centro se deja libre porque ahí aparece el jefe) y
`_draw_cubicle_side` dibuja las mamparas laterales. Como `project()` es lineal en la profundidad
interpolada, la base y el borde superior de una mampara son rectas en pantalla: basta un trapecio.
Sus postes reusan la fase `_scroll` de los rieles, así corren sincronizados. El jugador es un
**empleado visto de espaldas** (no lleva cara) con ciclo de carrera de dos poses que alternan según
`_run_phase`, más una pose de aire. Ese arte se mide con `PLAYER_ART_W/H`, **deliberadamente
distintos de `PLAYER_SIZE`** (la caja de colisión lógica): el sprite puede ser más alto que ancho
—y se dimensiona para que los obstáculos guarden proporción creíble contra él— sin tocar la física.
`_scroll`, `_run_phase` y `_boss_bob` son estado SOLO de render y avanzan al dibujar.

`draw_sprite` pinta una **sombra de contacto** (elipse tenue) bajo cada sprite para asentarlo. Su
parámetro `rest_lift` separa la elevación cosmética de reposo (`PLAYER_DRAW_LIFT`) del salto: la
sombra se ancla bajo los pies y solo se encoge/aclara con la porción de SALTO, así no se ve
despegada del personaje elevado. Obstáculos: `rest_lift=0`.

**Todo el "game feel" vive en [config.py](src/game/config.py)** — tamaños, FPS, geometría de
carriles, `LANE_LERP`, `JUMP_HEIGHT`, `JUMP_FRAMES`, velocidad (`SPEED_*`), spawn (`SPAWN_*`),
obstáculos (`OBSTACLE_*`), perseguidor (`CHASER_*`) y colores. Ajustar aquí, no hardcodear en
la lógica. (Las constantes puramente de perspectiva son la excepción: viven arriba de render.py.)

**Imports:** `main.py` (raíz) agrega `src/` al `sys.path`, luego los módulos se importan como
`from game.xxx import ...`. Mantener ese prefijo `game.` en imports internos.

## Convenciones

- Desarrollo guiado por placeholders: **rectángulos de colores primero**, arte después (Día 4).
  No bloquear gameplay esperando sprites.
- Nunca generar un obstáculo IMPOSIBLE de superar. Un JUMP tapa los 3 carriles a propósito, pero
  se libra saltando (no es imposible); un DODGE deja siempre ≥1 carril libre. Lo prohibido es algo
  que no se pueda ni saltar ni esquivar. Dejar distancia de reacción que considere la latencia de
  la cámara, no solo reacción humana.
- Comentarios y nombres en español (consistente con el código existente).
