from __future__ import annotations

import os
import sys
import time
import unittest
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import pygame  # noqa: E402

from game import assets, config, render  # noqa: E402
from game.controller_state import ControllerState  # noqa: E402
from game.game import Game, GameState  # noqa: E402
from game.obstacle import Obstacle, ObstacleType  # noqa: E402


class VisualAssetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        pygame.init()
        pygame.display.set_mode((1, 1))
        assets.preload()

    @classmethod
    def tearDownClass(cls) -> None:
        pygame.quit()

    def test_all_assets_load_with_expected_dimensions(self) -> None:
        for key, spec in assets.SPRITES.items():
            loaded = assets.load_sprite(key)
            self.assertIsNotNone(loaded, key)
            image, base_w, base_h = loaded
            self.assertEqual(image.get_size(), (round(base_w), round(base_h)), key)
            self.assertEqual(image.get_flags() & pygame.SRCALPHA, pygame.SRCALPHA, key)

        for key in assets.BACKGROUNDS:
            image = assets.load_background(key)
            self.assertIsNotNone(image, key)
            self.assertEqual(image.get_size(), (config.SCREEN_WIDTH, config.SCREEN_HEIGHT), key)

        for key in assets.ICONS:
            image = assets.load_icon(key)
            self.assertIsNotNone(image, key)
            self.assertEqual(image.get_size(), (72, 72), key)

    def test_cache_prevents_frame_by_frame_disk_reads(self) -> None:
        before = assets.cache_info()["disk_loads"]
        for _ in range(100):
            for key in assets.SPRITES:
                assets.load_sprite(key)
            for key in assets.BACKGROUNDS:
                assets.load_background(key)
            for key in assets.ICONS:
                assets.load_icon(key)
        self.assertEqual(assets.cache_info()["disk_loads"], before)

    def test_run_cycle_has_six_distinct_ordered_frames(self) -> None:
        pixels = []
        game = Game()
        for index in range(render.RUN_FRAME_COUNT):
            key = f"player_run_{index}"
            image, _base_w, _base_h = assets.load_sprite(key)
            pixels.append(pygame.image.tobytes(image, "RGBA"))
            render._run_phase = (index + 0.01) / render.RUN_FRAME_COUNT
            self.assertEqual(render._player_key(game.player), key)
        self.assertEqual(len(set(pixels)), render.RUN_FRAME_COUNT)

    def test_depth_projection_and_layer_render(self) -> None:
        canvas = pygame.Surface((config.SCREEN_WIDTH, config.SCREEN_HEIGHT))
        render.draw_ground(canvas, config.SPEED_START)
        for z in (0.15, 0.5, 0.9):
            render.draw_sprite(canvas, "dodge", 1, z)
        far = render.project(1, 0.15)
        near = render.project(1, 0.9)
        self.assertGreater(near[2], far[2])

    def test_full_flow_and_render_performance(self) -> None:
        game = Game()
        neutral = ControllerState(calibrated=True, lane=1)
        game.state = GameState.RUNNING
        game._spawn_gap = 10**9

        for _ in range(int(config.RUN_GOAL_DISTANCE / config.SPEED_START) + 5):
            game._update_running(neutral)
            if game.state is GameState.BOSS_FIGHT:
                break
        self.assertIs(game.state, GameState.BOSS_FIGHT)

        for stretch in config.BOSS_STRETCH_SEQUENCE:
            game._update_boss(
                ControllerState(calibrated=True, active_stretch=stretch, stretch_progress=1.0)
            )
            game._update_boss(neutral)
        self.assertIs(game.state, GameState.VICTORY)

        game._reset_run()
        game.state = GameState.RUNNING
        chair = Obstacle(ObstacleType.DODGE, 0)
        chair.y = config.PLAYER_BASE_Y * 0.65
        game.obstacles = [chair]
        started = time.perf_counter()
        frames = 180
        for _ in range(frames):
            game._draw(neutral)
        fps = frames / (time.perf_counter() - started)
        self.assertGreaterEqual(fps, 60.0, f"render headless demasiado lento: {fps:.1f} FPS")


if __name__ == "__main__":
    unittest.main()
