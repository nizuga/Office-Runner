"""Exporta una galeria headless de todos los estados visuales del juego."""

from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import pygame  # noqa: E402
from PIL import Image  # noqa: E402

from game import config, render  # noqa: E402
from game.controller_state import ControllerState  # noqa: E402
from game.game import Game, GameState  # noqa: E402
from game.obstacle import Obstacle, ObstacleType  # noqa: E402


OUTPUT = ROOT / "output" / "previews"


def _compose(game: Game, state: ControllerState, name: str) -> None:
    game._transition_frames = 0
    game._draw(state)
    full = pygame.Surface((config.CAM_PANEL_WIDTH + config.SCREEN_WIDTH, config.SCREEN_HEIGHT))
    render.draw_camera_panel(full, None, game._action_cue(state))
    full.blit(game.canvas, (config.CAM_PANEL_WIDTH, 0))
    pygame.image.save(full, OUTPUT / f"{name}.png")


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    game = Game()
    neutral = ControllerState(calibrated=True, lane=1)

    game.state = GameState.INTRO
    game._intro_frames_left = 8 * config.FPS
    _compose(game, neutral, "01_intro")

    game.state = GameState.CALIBRATING
    _compose(game, ControllerState(calibrated=False), "02_calibrating")

    game.state = GameState.RUNNING
    game.distance = config.RUN_GOAL_DISTANCE * 0.42
    chair = Obstacle(ObstacleType.DODGE, 0)
    chair.y = config.PLAYER_BASE_Y * 0.70
    boxes = Obstacle(ObstacleType.JUMP, 1)
    boxes.y = config.PLAYER_BASE_Y * 0.82
    game.obstacles = [chair, boxes]
    _compose(game, neutral, "03_running")

    game.obstacles.clear()
    game.state = GameState.BOSS_FIGHT
    stretch = ControllerState(
        calibrated=True,
        active_stretch=game.boss.required_stretch,
        stretch_progress=0.64,
    )
    _compose(game, stretch, "04_boss_fight")

    game.boss.health = 0
    game.state = GameState.VICTORY
    _compose(game, neutral, "05_victory")

    game.state = GameState.GAME_OVER
    game.speed = 0.0
    game.chaser.distance = 0.0
    _compose(game, neutral, "06_game_over")

    game.state = GameState.WATER_BREAK
    game.boss_exit = config.BOSS_EXIT_FRAMES // 2
    _compose(game, neutral, "07_water_break")

    # Los seis cuadros permiten revisar contacto, apoyo e impulso de cada pierna.
    game._reset_run()
    game.state = GameState.RUNNING
    cycle = pygame.Surface((config.SCREEN_WIDTH * render.RUN_FRAME_COUNT, config.SCREEN_HEIGHT))
    for index in range(render.RUN_FRAME_COUNT):
        phase = (index + 0.01) / render.RUN_FRAME_COUNT
        render._run_phase = phase
        game._draw(neutral)
        cycle.blit(game.canvas, (index * config.SCREEN_WIDTH, 0))
    pygame.image.save(cycle, OUTPUT / "08_run_cycle.png")

    # Diagnostico de los tres centros de carril cerca y a media distancia.
    lanes = pygame.Surface((config.SCREEN_WIDTH, config.SCREEN_HEIGHT))
    render.draw_ground(lanes, 0.0)
    for lane in range(config.LANE_COUNT):
        render.draw_sprite(lanes, "dodge", lane, 0.52)
        render.draw_sprite(lanes, "player_run_0", lane, 1.0,
                           y_lift=render.PLAYER_DRAW_LIFT,
                           rest_lift=render.PLAYER_DRAW_LIFT)
    pygame.image.save(lanes, OUTPUT / "09_lane_alignment.png")

    # GIF del render real: verifica la ilusion temporal, no solo poses aisladas.
    game._reset_run()
    game.state = GameState.RUNNING
    game.obstacles.clear()
    animated_frames = []
    crop_rect = pygame.Rect(70, 460, 400, 440)
    for _ in range(30):
        # Dos frames de motor por cuadro GIF = 30 FPS conservando el ritmo de
        # animacion calculado para los 60 FPS del juego.
        game._draw(neutral)
        game._draw(neutral)
        crop = game.canvas.subsurface(crop_rect)
        frame = Image.frombytes("RGB", crop.get_size(), pygame.image.tobytes(crop, "RGB"))
        animated_frames.append(frame)
    animated_frames[0].save(
        OUTPUT / "10_run_animation.gif",
        save_all=True,
        append_images=animated_frames[1:],
        duration=33,
        loop=0,
        disposal=2,
        optimize=True,
    )

    pygame.quit()
    print(f"10 previews exportados en {OUTPUT}")


if __name__ == "__main__":
    main()
