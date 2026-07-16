# Office Runner — Pausa Activa

Es viernes por la tarde y un **PDF con deadline** no te deja salir de la oficina.
Corre entre los cubículos esquivando sillas y saltando cajas mientras el PDF te
persigue; al final del pasillo te espera tu **jefe estresado**, y la única forma
de vencerlo es completar sus **estiramientos de pausa activa**. Si lo logras, el
juego te manda a lo importante: *ve por un vaso de agua y estira las piernas*.

Es un runner de tres carriles al estilo *Temple Run*, hecho en **pygame** con
perspectiva pseudo-3D, que se juega **con el cuerpo**: una webcam +
**OpenCV/MediaPipe** detectan tu pose y la convierten en los controles del juego.

## Propósito

Proyecto del curso de **Computación Visual**. La idea central: **los controles
SON los ejercicios**. En vez de jugar sentado con un teclado, el juego convierte
una pausa activa de oficina en gameplay:

- **Inclinar el torso** a los lados → cambiar de carril (movilidad lateral).
- **Subir ambos brazos** → saltar los obstáculos bajos (activación de hombros).
- **Sostener posturas de estiramiento** (cruzar brazos, inclinar el cuello,
  estirar cada brazo) → dañar al jefe final (estiramientos reales de pausa activa).

Técnicamente, el proyecto integra dos mitades a través de una única interfaz
(`ControllerState`): un módulo de **visión** (webcam + MediaPipe Pose:
calibración, detección de inclinación, brazos arriba y posturas guiadas sobre el
propio video) y un módulo de **juego** (loop, render en perspectiva, colisiones,
perseguidor y jefe). El panel izquierdo muestra tu cámara con el esqueleto
detectado y las pistas de acción (¡SALTA!, ¡MUÉVETE!); el derecho, el juego.

## Requisitos

- **Python 3.11** (obligatorio: MediaPipe no tiene wheel para 3.13).
- Una **webcam** (solo para el modo cámara; el juego también corre con teclado).
- Dependencias en [requirements.txt](requirements.txt): pygame, opencv-python,
  mediapipe, numpy. Funcionan en Windows, macOS (Intel y Apple Silicon) y Linux.

## Cómo iniciar la app

### 1. Crear el entorno virtual (una sola vez)

**Windows:**

```bash
py -3.11 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

**macOS / Linux:**

```bash
python3.11 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

### 2. Ejecutar el juego

**Con cámara (la experiencia completa):**

```bash
# Windows
.venv\Scripts\python.exe main.py --camera

# macOS / Linux
.venv/bin/python main.py --camera
```

**Con teclado (sin webcam, para probar o desarrollar):**

```bash
# Windows
.venv\Scripts\python.exe main.py

# macOS / Linux
.venv/bin/python main.py
```

> **Nota macOS:** la primera vez que se ejecute con `--camera`, el sistema pedirá
> permiso de cámara para la Terminal (o el editor desde el que se lance). Si el
> feed sale negro, revisa *Ajustes del Sistema → Privacidad y seguridad → Cámara*.

### 3. Jugar

1. **Intro (20 s):** lee las reglas y ubícate frente a la cámara con cabeza y
   hombros dentro del encuadre (cualquier tecla salta la intro).
2. **Calibración (~2 s):** siéntate/párate derecho y quieto; se fija tu postura
   neutral de referencia.
3. **Corre:** inclínate para cambiar de carril, sube ambos brazos para saltar
   las cajas (la franja ámbar del piso marca el momento seguro). Chocar acerca
   al PDF; esquivar bien lo aleja. Si el PDF te alcanza: game over (brazos
   arriba o `R` para reintentar).
4. **El jefe:** sostén cada estiramiento que pida durante 3 segundos, guiándote
   por las dianas dibujadas sobre tu propio video (verde = esa parte del cuerpo
   ya está en posición). Cinco posturas y queda vencido.
5. **Final:** el jefe se retira y el juego te despide con la verdadera misión —
   **ve por un vaso de agua y estira las piernas**. (Brazos arriba: otra ronda.)

### Controles de teclado (modo sin cámara)

| Tecla | Acción |
|---|---|
| ← / → | Cambiar de carril |
| Espacio | Saltar |
| 1..5 (mantener) | Sostener cada estiramiento del jefe |
| R | Reiniciar tras el game over |
| Esc | Salir |
