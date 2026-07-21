"""
game.py — clase Game y máquina de estados.

Todo el juego es una máquina de estados (§4). Día 1: INTRO -> CALIBRATING ->
RUNNING. Día 2: el core del runner dentro de RUNNING (spawn de obstáculos,
colisiones, PDF perseguidor, velocidad progresiva) y salida a GAME_OVER cuando
el PDF alcanza al jugador. BOSS_FIGHT/VICTORY/WATER_BREAK quedan sembrados.
"""

from __future__ import annotations

import random
from enum import Enum, auto

import pygame

from game import assets, config, render
from game.boss import Boss
from game.chaser import Chaser
from game.keyboard_controller import KeyboardController
from game.obstacle import Obstacle
from game.player import Player


class GameState(Enum):
    INTRO = auto()
    CALIBRATING = auto()
    RUNNING = auto()
    # --- futuros (§4) ---
    BOSS_FIGHT = auto()
    VICTORY = auto()
    GAME_OVER = auto()
    WATER_BREAK = auto()


class Game:
    def __init__(self, controller=None) -> None:
        pygame.init()
        # Composición NATIVA = panel de cámara (izq) + área de juego (der). Todo se
        # dibuja a esta resolución fija (render.py no se entera de nada), y luego se
        # ESCALA como imagen a la ventana real para caber en el monitor.
        native_w = config.CAM_PANEL_WIDTH + config.SCREEN_WIDTH
        native_h = config.SCREEN_HEIGHT
        # `pygame.display.Info()` tras init y antes de set_mode = resolución del
        # monitor. Escalamos para que el alto de la ventana quede cerca del alto de
        # la pantalla (con margen), sin deformar (misma escala en x/y) ni cortarse.
        info = pygame.display.Info()
        desk_w, desk_h = info.current_w, info.current_h
        self._scale = min(
            desk_h * config.WINDOW_FIT_MARGIN / native_h,
            desk_w * config.WINDOW_FIT_MARGIN / native_w,
            config.WINDOW_MAX_SCALE,
        )
        if self._scale <= 0:                 # resolución no reportada: sin escalar
            self._scale = 1.0
        win_w, win_h = round(native_w * self._scale), round(native_h * self._scale)
        print(f"[pantalla] monitor {desk_w}x{desk_h} -> ventana {win_w}x{win_h} "
              f"(escala {self._scale:.2f})")
        self.window = pygame.display.set_mode((win_w, win_h))
        # `self.screen` es el destino de dibujo de siempre (ahora una Surface, no el
        # display): panel + juego se componen aquí a resolución nativa.
        self.screen = pygame.Surface((native_w, native_h))
        self.canvas = pygame.Surface((config.SCREEN_WIDTH, config.SCREEN_HEIGHT))
        pygame.display.set_caption(config.CAPTION)
        self.clock = pygame.time.Clock()
        # Todos los PNG se convierten/cachean una vez, despues de crear display.
        # Si falta alguno, render.py conserva su fallback procedural.
        assets.preload()

        # Fuente del ControllerState inyectable (teclado por defecto, cámara
        # opcional). Ambas exponen handle_event + get_state: el juego no distingue.
        self.controller = controller if controller is not None else KeyboardController()
        self.state = GameState.INTRO
        # Frames restantes de la pantalla de onboarding (reglas + ubicación).
        self._intro_frames_left = config.INTRO_SECONDS * config.FPS
        self._transition_frames: int = 0
        self.running = True
        self._reset_run()

    def _reset_run(self) -> None:
        """Deja el runner en su estado inicial (nuevo run o reinicio)."""
        # Re-centrar también la FUENTE: sin esto el carril recordado del run
        # anterior (o la flecha con que se saltó la intro) arrastra al jugador
        # fuera del centro apenas arranca el run nuevo.
        if hasattr(self.controller, "reset"):
            self.controller.reset()
        self.player = Player()
        self.chaser = Chaser()
        self.boss = Boss()
        self.obstacles: list[Obstacle] = []
        self.speed: float = config.SPEED_START
        self._spawn_gap: float = config.SPAWN_SPACING
        # Frames restantes del flash rojo de error (0 = sin destello).
        self.hit_flash: int = 0
        # Distancia recorrida hacia la meta (donde espera el jefe).
        self.distance: float = 0.0
        # Frames restantes de la animación de daño del jefe (retroceso + estallido
        # + "-1" + destello + sacudida). 0 = sin animación.
        self.boss_hit: int = 0
        # Frames restantes del MUTIS del jefe (se retira hacia la SALIDA al
        # empezar la pausa de agua). 0 = ya se fue / no aplica.
        self.boss_exit: int = 0

    @property
    def run_progress(self) -> float:
        """Avance hacia la meta, 0..1 (lo que muestra el medidor superior)."""
        return min(1.0, self.distance / config.RUN_GOAL_DISTANCE)

    # --- Loop principal ---

    def run(self) -> None:
        while self.running:
            events = pygame.event.get()
            for event in events:
                if event.type == pygame.QUIT:
                    self.running = False
                elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                    self.running = False
                else:
                    self.controller.handle_event(event)

            # Canal lateral de ENTRADA a la cámara: qué estiramiento pide el jefe
            # AHORA, para que dibuje su guía-fantasma y mida contra esa pose. None
            # fuera del jefe (sin guía). El teclado ignora este atributo.
            if hasattr(self.controller, "target_stretch"):
                self.controller.target_stretch = (
                    self.boss.required_stretch
                    if self.state == GameState.BOSS_FIGHT and not self.boss.defeated
                    else None
                )

            state = self.controller.get_state()
            self._update(state, events)
            self._draw(state)   # dibuja el juego en self.canvas

            # Composición NATIVA en self.screen: panel de cámara (izq) + juego (der).
            frame = getattr(self.controller, "last_frame", None)
            render.draw_camera_panel(self.screen, frame, self._action_cue(state))
            self.screen.blit(self.canvas, (config.CAM_PANEL_WIDTH, 0))

            # Escalar la composición a la ventana real (ajuste al monitor).
            if self.window.get_size() == self.screen.get_size():
                self.window.blit(self.screen, (0, 0))
            else:
                pygame.transform.smoothscale(self.screen, self.window.get_size(), self.window)

            pygame.display.flip()
            self.clock.tick(config.FPS)

        # Liberar la fuente al salir (la cámara suelta webcam + hilo lector; el
        # teclado no expone close). Antes la webcam quedaba tomada hasta que
        # muriera el proceso.
        if hasattr(self.controller, "close"):
            self.controller.close()
        pygame.quit()

    # --- Actualización por estado ---

    def _update(self, state, events) -> None:
        previous_state = self.state
        if self.state == GameState.INTRO:
            # Pantalla de reglas + tiempo para ubicarse frente a la cámara. Se
            # cuenta hacia atrás; cualquier tecla la salta.
            self._intro_frames_left -= 1
            if self._intro_frames_left <= 0 or self._any_key_pressed(events):
                # Recalibrar AHORA: la línea base se fija con el jugador ya ubicado.
                if hasattr(self.controller, "start_calibration"):
                    self.controller.start_calibration()
                    self.state = GameState.CALIBRATING
                else:
                    # Fuente sin calibración (teclado): directo al run, sin el
                    # parpadeo de un frame de "Calibrando...".
                    self._reset_run()
                    self.state = GameState.RUNNING
        elif self.state == GameState.CALIBRATING:
            # La cámara hace el trabajo; con teclado calibrated ya es True.
            if state.calibrated:
                self._reset_run()
                self.state = GameState.RUNNING
        elif self.state == GameState.RUNNING:
            self._update_running(state)
        elif self.state == GameState.BOSS_FIGHT:
            self._update_boss(state)
        elif self.state == GameState.VICTORY:
            # Deja terminar la animación del último golpe antes de asentar la escena.
            self.boss_hit = max(0, self.boss_hit - 1)
            # Avanza con tecla O con el gesto de salto (brazos arriba): en modo
            # cámara el jugador está lejos del teclado.
            if state.jump or self._any_key_pressed(events):
                self.boss_exit = config.BOSS_EXIT_FRAMES   # el jefe hace mutis
                self.state = GameState.WATER_BREAK
        elif self.state == GameState.WATER_BREAK:
            self.boss_exit = max(0, self.boss_exit - 1)
            # Antes era un callejón sin salida (solo ESC). Ahora brazos arriba o
            # cualquier tecla relanzan un run nuevo.
            if state.jump or self._any_key_pressed(events):
                self._reset_run()
                self.state = GameState.RUNNING
        elif self.state == GameState.GAME_OVER:
            # El flash rojo del golpe final sigue desvaneciéndose aquí: sin esto
            # quedaba CONGELADO tiñendo de rojo toda la pantalla de derrota
            # (perder siempre coincide con un choque, así que pasaba siempre).
            self.hit_flash = max(0, self.hit_flash - 1)
            # R (teclado) o brazos arriba (cámara) reinician un nuevo run.
            restart_key = any(
                e.type == pygame.KEYDOWN and e.key == pygame.K_r for e in events)
            if restart_key or state.jump:
                self._reset_run()
                self.state = GameState.RUNNING

        if self.state is not previous_state:
            self._transition_frames = config.TRANSITION_FRAMES
        else:
            self._transition_frames = max(0, self._transition_frames - 1)

    def _update_running(self, state) -> None:
        # Movimiento del jugador.
        self.player.set_lane(state.lane)
        if state.jump:
            self.player.start_jump()
        self.player.update()

        # Velocidad progresiva con tope (§7).
        self.speed = min(config.SPEED_MAX, self.speed + config.SPEED_ACCEL)

        # Avance hacia la meta (alimenta el medidor superior).
        self.distance += self.speed

        # Spawn por distancia recorrida => espaciado en pantalla constante.
        # Se deja de generar cuando un obstáculo nuevo ya NO alcanzaría a llegar
        # al jugador antes de la meta (necesita caer PLAYER_BASE_Y px): así al
        # cortar a la escena del jefe no hay obstáculos visibles que desaparezcan
        # de golpe a mitad de pista.
        self._spawn_gap -= self.speed
        can_reach = self.distance < config.RUN_GOAL_DISTANCE - config.PLAYER_BASE_Y
        if self._spawn_gap <= 0 and can_reach:
            self.obstacles.append(Obstacle.random())
            jitter = random.uniform(-config.SPAWN_JITTER, config.SPAWN_JITTER)
            self._spawn_gap = config.SPAWN_SPACING + jitter

        # Mover y resolver obstáculos.
        for obs in self.obstacles:
            obs.update(self.speed)
            if obs.resolved:
                continue
            if obs.has_passed_player():
                # Cruzó la línea del jugador (render ya lo culleó, z>1):
                # esquive/salto exitoso. Va ANTES del choque para que un
                # obstáculo que ya no se ve nunca haga daño.
                obs.resolved = True
                self.chaser.on_dodge()
            elif (self.player.rect.colliderect(obs.rect)
                  and self.player.jump_offset < obs.height):
                # Solapa en carril×profundidad Y el jugador no va lo bastante
                # alto para librar la ALTURA del obstáculo. Como DODGE (220) >
                # JUMP_HEIGHT (180), un DODGE nunca se salva saltando.
                obs.resolved = True
                obs.hit = True
                self.chaser.on_hit()
                self.hit_flash = config.HIT_FLASH_FRAMES   # dispara el flash rojo

        # Limpiar obstáculos fuera de pantalla.
        self.obstacles = [o for o in self.obstacles if not o.is_off_screen()]

        # Desvanecer el flash rojo (siempre, esté o no en choque este frame).
        self.hit_flash = max(0, self.hit_flash - 1)

        # ¿El PDF alcanzó al jugador? (perder tiene prioridad sobre llegar)
        if self.chaser.caught:
            # Velocidad a 0: congela piso, postes y zancada en la pantalla de
            # derrota (el mundo no sigue "corriendo" detrás del texto).
            self.speed = 0.0
            self.state = GameState.GAME_OVER
        elif self.distance >= config.RUN_GOAL_DISTANCE:
            # Llegaste a la meta: te espera el jefe. La pista se limpia para
            # que ningún obstáculo quede a medio camino en la escena del jefe.
            self.obstacles.clear()
            self.state = GameState.BOSS_FIGHT

    def _update_boss(self, state) -> None:
        """Pelea contra el jefe: sostener la postura que pide baja su vida."""
        self.player.update()   # sigue animando (aterriza un salto pendiente)

        if self.boss.update(state.active_stretch, state.stretch_progress):
            self.boss_hit = config.BOSS_HIT_ANIM_FRAMES

        self.boss_hit = max(0, self.boss_hit - 1)

        if self.boss.defeated:
            self.state = GameState.VICTORY

    @staticmethod
    def _any_key_pressed(events) -> bool:
        return any(e.type == pygame.KEYDOWN for e in events)

    # --- Render ---

    def _draw(self, state) -> None:
        # Todo el juego se dibuja al LIENZO (self.canvas); la composición con el
        # panel de cámara la hace run(). render.py sigue viendo un 540×900 normal.
        if self.state == GameState.INTRO:
            render.draw_static_background(self.canvas, "intro")
            secs = self._intro_frames_left // config.FPS + 1
            render.draw_intro(self.canvas, secs)
        elif self.state == GameState.CALIBRATING:
            render.draw_ground(self.canvas, config.SPEED_START, jump_cue=False)
            self._draw_center_text("Calibrando...", "Siéntate derecho y quieto")
        elif self.state == GameState.RUNNING:
            render.draw_running(self.canvas, self, state)
        elif self.state == GameState.BOSS_FIGHT:
            render.draw_boss_fight(self.canvas, self, state)
        elif self.state == GameState.VICTORY:
            render.draw_boss_fight(self.canvas, self, state)
            self._draw_center_text("¡Venciste al jefe!", "Brazos arriba o una tecla")
        elif self.state == GameState.WATER_BREAK:
            render.draw_static_background(self.canvas, "water_break")
            # El jefe vencido se retira hacia la SALIDA antes de asentarse la escena.
            if self.boss_exit > 0:
                t = 1.0 - self.boss_exit / config.BOSS_EXIT_FRAMES
                render.draw_boss_exit(self.canvas, t)
            self._draw_center_text(config.WATER_BREAK_TITLE,
                                   config.WATER_BREAK_SUBTITLE,
                                   hint=config.WATER_BREAK_HINT)
        elif self.state == GameState.GAME_OVER:
            render.draw_running(self.canvas, self, state)
            self._draw_center_text("¡Te alcanzó el PDF!", "Brazos arriba o R: reiniciar")

        render.draw_transition(self.canvas, self._transition_frames)

    def _draw_center_text(self, title: str, subtitle: str,
                          hint: str | None = None) -> None:
        # _render_fit encoge la fuente si el texto no cabe en el lienzo (540px):
        # así los mensajes largos ("Ve por un vaso de agua") nunca se cortan.
        cx = config.SCREEN_WIDTH // 2
        cy = config.SCREEN_HEIGHT // 2
        max_w = config.SCREEN_WIDTH - 24
        t = render._render_fit(title, max_w, 44, config.COLOR_TEXT, bold=True)
        s = render._render_fit(subtitle, max_w, 26, config.COLOR_TEXT_DIM)
        self.canvas.blit(t, t.get_rect(center=(cx, cy - 20)))
        self.canvas.blit(s, s.get_rect(center=(cx, cy + 30)))
        if hint:
            h = render._render_fit(hint, max_w, 18, config.COLOR_TEXT_DIM)
            self.canvas.blit(h, h.get_rect(center=(cx, cy + 68)))

    # --- Pista de acción para el panel de cámara ---

    def _action_cue(self, state) -> tuple[str, str, tuple[int, int, int]]:
        """Texto de pista según el estado del juego: (principal, subtexto, color).

        Es PRESENTACIÓN: solo lee estado (obstáculos, jugador, jefe), no decide
        gameplay. Reusa los helpers puros de render para que el "¡SALTA!" quede
        sincronizado con el chevron ámbar del piso.
        """
        if self.state == GameState.INTRO:
            return ("COLOCATE", "cabeza y hombros en el recuadro", config.COLOR_CUE_IDLE)
        if self.state == GameState.CALIBRATING:
            return ("NO TE MUEVAS", "sientate derecho, calibrando...", config.COLOR_CUE_IDLE)
        if self.state == GameState.RUNNING:
            return self._running_cue()
        if self.state == GameState.BOSS_FIGHT:
            if self.boss.defeated:
                return ("¡GANASTE!", "", config.COLOR_CUE_STRETCH)
            return (self.boss.required_label, "sosten la postura", config.COLOR_CUE_STRETCH)
        if self.state == GameState.VICTORY:
            return ("¡GANASTE!", "brazos arriba para seguir", config.COLOR_CUE_STRETCH)
        if self.state == GameState.GAME_OVER:
            return ("¡TE ALCANZO!", "brazos arriba o R: reiniciar", config.COLOR_CUE_DODGE)
        if self.state == GameState.WATER_BREAK:
            return ("¡VE POR AGUA!", "brazos arriba: otra ronda", config.COLOR_CUE_STRETCH)
        return ("PREPARATE", "", config.COLOR_CUE_IDLE)   # INTRO

    def _running_cue(self) -> tuple[str, str, tuple[int, int, int]]:
        """Amenaza más cercana en el carril del jugador -> pista de esquive/salto."""
        player_lane = round(render.lane_of_player(self.player))

        best_z = -1.0
        best_kind: str | None = None
        for obs in self.obstacles:
            if obs.resolved:
                continue
            z = render.z_of_obstacle(obs)
            if z > 1.0:
                continue
            if obs.type.name == "JUMP":
                # Barra full-width: amenaza estés en el carril que estés.
                relevant = render.JUMP_CUE_Z0 <= z <= render.JUMP_CUE_Z1
            else:  # DODGE: solo si está en MI carril
                relevant = obs.lane == player_lane and z >= config.CUE_DODGE_Z_MIN
            if relevant and z > best_z:   # la más cercana manda
                best_z, best_kind = z, obs.type.name

        if best_kind == "DODGE":
            side = "IZQUIERDO" if self._free_direction(player_lane) < 0 else "DERECHO"
            return ("¡MUEVETE!", f"al carril {side}", config.COLOR_CUE_DODGE)
        if best_kind == "JUMP":
            return ("¡SALTA!", "sube los brazos", config.COLOR_CUE_JUMP)
        return ("CORRE", "", config.COLOR_CUE_IDLE)

    def _free_direction(self, lane: int) -> int:
        """-1 (izquierda) o +1 (derecha) hacia un carril adyacente sin DODGE cercano."""
        def blocked(target: int) -> bool:
            # Mira MÁS lejos (CUE_FREE_Z_MIN < CUE_DODGE_Z_MIN) que la ventana de
            # aviso: si el carril sugerido tiene un DODGE a punto de entrar en
            # ella, la pista diría "muévete allá" y frames después "muévete acá".
            for obs in self.obstacles:
                if (obs.lane == target and obs.type.name == "DODGE" and not obs.resolved
                        and config.CUE_FREE_Z_MIN <= render.z_of_obstacle(obs) <= 1.0):
                    return True
            return False

        left_ok = lane - 1 >= 0
        right_ok = lane + 1 <= config.LANE_COUNT - 1
        if left_ok and not blocked(lane - 1):
            return -1
        if right_ok and not blocked(lane + 1):
            return 1
        return -1 if left_ok else 1
