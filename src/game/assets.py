"""Carga y cache de assets visuales externos.

El render puede seguir funcionando sin ningun PNG: ante un archivo ausente o
invalido devuelve ``None`` y ``render.py`` usa su dibujo procedural anterior.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pygame


ASSET_ROOT = Path(__file__).resolve().parents[2] / "assets"


@dataclass(frozen=True, slots=True)
class SpriteSpec:
    path: Path
    base_size: tuple[float, float]
    pixelated: bool = True


SPRITES: dict[str, SpriteSpec] = {
    **{
        f"player_run_{index}": SpriteSpec(
            ASSET_ROOT / "sprites" / f"player_run_{index}.png", (92.0, 146.0)
        )
        for index in range(6)
    },
    "player_run_a": SpriteSpec(ASSET_ROOT / "sprites" / "player_run_a.png", (92.0, 146.0)),
    "player_run_b": SpriteSpec(ASSET_ROOT / "sprites" / "player_run_b.png", (92.0, 146.0)),
    "player_air": SpriteSpec(ASSET_ROOT / "sprites" / "player_air.png", (92.0, 146.0)),
    "boss": SpriteSpec(ASSET_ROOT / "sprites" / "boss.png", (210.0, 190.0)),
    "jump": SpriteSpec(ASSET_ROOT / "sprites" / "boxes.png", (495.0, 34.0)),
    "dodge": SpriteSpec(ASSET_ROOT / "sprites" / "chair.png", (110.0, 220.0)),
    "pdf": SpriteSpec(ASSET_ROOT / "sprites" / "pdf.png", (126.0, 118.0)),
}

BACKGROUNDS: dict[str, Path] = {
    "office": ASSET_ROOT / "backgrounds" / "office.png",
    "intro": ASSET_ROOT / "backgrounds" / "intro.png",
    "water_break": ASSET_ROOT / "backgrounds" / "water_break.png",
}

ICONS: dict[str, Path] = {
    "logo": ASSET_ROOT / "ui" / "logo.png",
    "jump": ASSET_ROOT / "ui" / "jump.png",
    "dodge": ASSET_ROOT / "ui" / "dodge.png",
    "stretch": ASSET_ROOT / "ui" / "stretch.png",
}

_sprite_cache: dict[str, tuple[pygame.Surface, float, float] | None] = {}
_background_cache: dict[str, pygame.Surface | None] = {}
_icon_cache: dict[str, pygame.Surface | None] = {}
_disk_loads: int = 0


def _load(path: Path, *, alpha: bool) -> pygame.Surface | None:
    global _disk_loads
    if not path.is_file():
        return None
    try:
        image = pygame.image.load(str(path))
        _disk_loads += 1
        return image.convert_alpha() if alpha else image.convert()
    except (pygame.error, OSError):
        return None


def load_sprite(key: str) -> tuple[pygame.Surface, float, float] | None:
    if key not in _sprite_cache:
        spec = SPRITES.get(key)
        image = _load(spec.path, alpha=True) if spec else None
        _sprite_cache[key] = (
            (image, spec.base_size[0], spec.base_size[1]) if image is not None and spec else None
        )
    return _sprite_cache[key]


def load_background(key: str) -> pygame.Surface | None:
    if key not in _background_cache:
        path = BACKGROUNDS.get(key)
        _background_cache[key] = _load(path, alpha=False) if path else None
    return _background_cache[key]


def load_icon(key: str) -> pygame.Surface | None:
    if key not in _icon_cache:
        path = ICONS.get(key)
        _icon_cache[key] = _load(path, alpha=True) if path else None
    return _icon_cache[key]


def preload() -> None:
    """Carga todo una vez, despues de que pygame haya creado el display."""
    for key in SPRITES:
        load_sprite(key)
    for key in BACKGROUNDS:
        load_background(key)
    for key in ICONS:
        load_icon(key)


def cache_info() -> dict[str, int]:
    return {
        "sprites": len(_sprite_cache),
        "backgrounds": len(_background_cache),
        "icons": len(_icon_cache),
        "disk_loads": _disk_loads,
    }
