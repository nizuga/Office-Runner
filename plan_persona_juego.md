# Plan de Trabajo — Persona B: Módulo de Juego 🎮

Tu misión: construir el *runner* completo en **pygame**. Todo lo tuyo consume un objeto `ControllerState` que te entrega la persona de cámara. Gracias a eso puedes **desarrollar y probar el juego entero sin necesitar la webcam**, usando un stub de teclado que produce ese mismo objeto.

> **Regla clave:** no dependes de la cámara para trabajar. Construyes contra la *interfaz*, no contra el módulo de visión. La integración real es solo el Día 3 y consiste en cambiar la fuente del estado.

---

## 1. Tu alcance (lo que "owns")

| Sí es tuyo | No es tuyo (Persona A) |
|---|---|
| Loop de juego, render, FPS | OpenCV / webcam |
| 3 carriles, personaje, animación de salto | MediaPipe / detección de pose |
| Spawn y colisiones de obstáculos | Calibración, histéresis |
| PDF perseguidor (barra de distancia) | Reconocimiento de gestos del jefe |
| Velocidad progresiva con tope | Poblar `ControllerState` |
| Lógica del jefe (vida, secuencia de estiramientos) | |
| UI, máquina de estados, pantallas | |
| Assets/sprites de oficina | |

**Entregas:** un juego que corre de inicio a fin consumiendo `ControllerState`.

---

## 2. La interfaz que consumes — `ControllerState` ⭐

Esto lo acuerdan **ambos el Día 1** y vive en `controller_state.py`. Es tu única frontera con la cámara. Tú **lees** estos campos cada frame; nunca los escribes (salvo en tu stub).

```python
class ControllerState:
    calibrated: bool          # ¿ya se fijó la línea base? (mostrar pantalla de calibración si es False)
    lane: int                 # 0 = izquierda, 1 = centro, 2 = derecha
    jump: bool                # evento de UN frame (flanco de subida). Consumir y actuar una vez.

    # --- solo en modo jefe ---
    active_stretch: str | None      # id del estiramiento sostenido detectado, ej. "arm_cross_L"
    stretch_progress: float         # 0.0 a 1.0: cuánto lleva sostenida la postura
```

### Cómo lo consumes
```python
# En tu game loop, cada frame:
state = controller.get_state()   # da igual si es cámara o teclado: misma interfaz

if not state.calibrated:
    show_calibration_screen()
else:
    player.set_lane(state.lane)          # mover al carril indicado
    if state.jump:                       # evento: disparar salto una sola vez
        player.start_jump()
```

> **Ojo con `jump`:** es un evento de un frame, no un estado. Ya viene "desbotonado" por la persona de cámara. Tú solo reaccionas cuando llega `True`.

---

## 3. Tu stack

| Tecnología | Nota |
|---|---|
| **Python 3.11** en `venv` | Mismo entorno que el proyecto. No usar 3.13. |
| **pygame** | `pip install pygame`. Tu motor: loop, render, colisiones, sonido, eventos. |
| **Assets de oficina** | PDF perseguidor, obstáculos (archivador, impresora, cooler / bandeja, grapadora), jefe estresado, UI. **Empieza con rectángulos de colores** y cambia el arte después (ver §6). |

---

## 4. Arquitectura del juego

### Máquina de estados
Todo el juego es una máquina de estados. Define un enum y despacha el loop según el estado activo:

```
INTRO ──► CALIBRATING ──► RUNNING ──► BOSS_FIGHT ──► VICTORY ──► WATER_BREAK
                             │                                    (pantalla final:
                             └──────────► GAME_OVER                "ve por agua")
```

- **INTRO:** título y "presiona para empezar".
- **CALIBRATING:** esperar a `state.calibrated == True` (la cámara hace el trabajo; tú solo muestras "siéntate derecho").
- **RUNNING:** el core del runner.
- **BOSS_FIGHT:** consumir estiramientos para bajar vida al jefe.
- **VICTORY / GAME_OVER:** resultado.
- **WATER_BREAK:** *"¡Ve por agua para estirar las piernas!"* — el remate.

### Entidades
| Clase | Estado que guarda | Comportamiento |
|---|---|---|
| `Player` | carril actual, si está en el aire, rect de colisión | Se mueve entre carriles; animación de salto (offset en Y durante N frames). |
| `Obstacle` | tipo (`JUMP` / `DODGE`), carril(es) que ocupa, posición Y | Baja hacia el jugador; sprite según tipo. |
| `Chaser` (PDF) | distancia 0.0–1.0 | Se acerca al fallar, se aleja al esquivar bien. En 0.0 → GAME_OVER. |
| `Boss` | vida, estiramiento requerido actual | Baja vida cuando se completa el estiramiento pedido. |

### Sistemas
- **Mapeo de carril:** `state.lane` → posición X del jugador (con una pequeña interpolación para que el cambio no sea instantáneo/feo).
- **Salto:** al recibir `state.jump`, el jugador queda "en el aire" N frames (inmune a obstáculos `JUMP`).
- **Spawn:** por temporizador; elige tipo + carril. **Nunca generar algo imposible** (un obstáculo alto que bloquee los 3 carriles a la vez). Dar distancia de reacción suficiente.
- **Colisión:** cuando un obstáculo llega a la fila del jugador:
  - `JUMP` → seguro si el jugador está en el aire.
  - `DODGE` → seguro si el jugador NO está en el carril del obstáculo.
- **Perseguidor (PDF):** esquivar bien aleja (hasta un tope), fallar acerca, tocar 0 = perder.
- **Velocidad:** sube con el tiempo hasta un **tope** (cap). Pasado cierto punto sería injusto por lag, no por dificultad.
- **Jefe:** secuencia de estiramientos requeridos. Consumir `state.active_stretch` + `state.stretch_progress`; cuando el estiramiento pedido llega a `progress == 1.0` → daño al jefe y siguiente estiramiento. Vida a 0 → VICTORY.

---

## 5. Tu stub de teclado (tu herramienta de independencia)

Escríbelo el Día 1. Produce el **mismo** `ControllerState` que la cámara, pero desde el teclado. Así juegas y depuras todo sin webcam.

```python
# keyboard_controller.py
# Flechas ← → = carril | ESPACIO = salto (un frame) | teclas 1/2/3 = simular estiramientos (modo jefe)
class KeyboardController:
    def get_state(self) -> ControllerState:
        # leer teclas de pygame y rellenar lane, jump, active_stretch, stretch_progress
        # calibrated = True siempre (no hay calibración por teclado)
        ...
```

El Día 3, cambias `KeyboardController()` por el controlador real de la cámara. **Nada más del juego cambia.**

---

## 6. Plan día por día (tu carril)

> Consejo de tiempo: **desarrollo guiado por placeholders.** Todo con rectángulos de colores primero (jugable = prioridad); el arte bonito entra el Día 4. No bloquees el gameplay esperando sprites.

### DÍA 1 — Esqueleto jugable con teclado
- 🤝 **Primera hora, con Persona A:** acordar y commitear `controller_state.py`.
- `venv` Python 3.11 + `pip install pygame`.
- Ventana, game loop, reloj/FPS.
- Render de 3 carriles + personaje (rectángulos).
- **`KeyboardController`** produciendo `ControllerState`.
- Mover el personaje entre carriles + animación básica de salto.
- ✅ *Checkpoint:* te mueves entre carriles y saltas con el teclado.

### DÍA 2 — Runner completo (con teclado)
- **Spawn de obstáculos:** `JUMP` (ras de piso) vs. `DODGE` (altos). Señalización legible: la forma dice qué hacer.
- **Colisiones** con su consecuencia.
- **PDF perseguidor:** barra de distancia (acerca al fallar, aleja al esquivar).
- **Velocidad progresiva con tope.**
- ✅ *Checkpoint:* run completo y justo jugado con teclado; el PDF te alcanza si chocas y pierdes.

### DÍA 3 — 🤝 Integración (día de mayor riesgo)
- Cambiar el stub de teclado por el controlador de cámara real.
- Jugar de verdad y ayudar a **tunear el game feel** (sensibilidad, timing de salto, distancia de reacción).
- Resolver sincronía de FPS cámara ↔ juego.
- ✅ *Checkpoint conjunto:* run entero jugado con el cuerpo, sentado, y se siente justo.
- **Desde hoy: graba cada sesión** (respaldo + B-roll para el video).

### DÍA 4 — Jefe final + pulido
- **Lógica del jefe:** consumir `active_stretch` / `stretch_progress`; cada estiramiento completado le baja vida.
- **Pulido temático:** sprites de oficina, PDF, UI, transiciones.
- **Pantallas:** intro, run → jefe → victoria/derrota → **"ve por agua para estirar las piernas"**.
- ✅ *Checkpoint conjunto:* juego de inicio a fin: run → PDF aprieta → jefe → se vence estirando → pantalla de agua.

### DÍA 5 — 🤝 Video (+ buffer)
- Grabar gameplay limpio.
- Aportar tu parte de la narración (el diseño del juego, la máquina de estados, el bucle del perseguidor).
- Ayudar a editar. El buffer absorbe retrasos.

---

## 7. Tus retos técnicos

- **Señalización legible de obstáculos:** de un vistazo, el jugador debe saber si salta o esquiva. `JUMP` bajos y a ras de piso; `DODGE` altos y sólidos. Nunca un obstáculo imposible.
- **Distancia de reacción justa:** deja margen suficiente considerando la latencia de la cámara (no todo es reacción humana).
- **Bucle del perseguidor:** simple (una barra), pero es lo que da toda la tensión. Balancéalo: fallar debe doler, esquivar bien debe premiar.
- **Curva de dificultad con tope:** sube velocidad, pero con cap. Injusto por lag ≠ difícil.
- **Máquina de estados limpia:** que los controles no se pisen entre estados (en el run, brazos = saltar; en el jefe, brazos = estirar — pero eso lo maneja la cámara; tú solo cambias de estado correctamente).
- **Interpolación de carril:** el cambio de carril instantáneo se ve tosco. Un pequeño *lerp* lo hace fluido.
- **Salto como evento:** actúa una sola vez por cada `jump == True`; no dejes que se repita mientras el jugador tiene los brazos arriba.

---

## 8. Válvula de recorte (si el tiempo aprieta)

Recorta **en este orden**:
1. **Primero:** simplificar el jefe — de 3 estiramientos a 1.
2. **Después:** menos variedad de obstáculos / assets (los rectángulos sobreviven).
3. **NUNCA:** la fluidez del run. Es lo que se ve y se juzga en el video.

**Seguro de vida:** graba gameplay desde el Día 3. Si el Día 5 algo falla, ya tienes metraje de que funcionó.

---

*Frontera con Persona A: `controller_state.py`. Mientras respetes esa interfaz, tu mitad avanza sola.*
