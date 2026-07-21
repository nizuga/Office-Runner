"""Construye los PNG finales a partir de las fuentes generadas con IA.

Antes de ejecutar este script, los archivos ``*_chroma.png`` deben pasar por
``remove_chroma_key.py`` (skill imagegen), dejando sus pares ``*_alpha.png`` en
``assets/source``. El script solo recorta, normaliza y redimensiona; nunca
inventa transparencia por tolerancia propia.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageEnhance


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "assets" / "source"
SPRITES = ROOT / "assets" / "sprites"
BACKGROUNDS = ROOT / "assets" / "backgrounds"
UI = ROOT / "assets" / "ui"


def _alpha_bbox(image: Image.Image) -> tuple[int, int, int, int]:
    bbox = image.getchannel("A").getbbox()
    if bbox is None:
        raise ValueError("La imagen no contiene pixeles visibles")
    return bbox


def _fit_pixel(
    image: Image.Image,
    size: tuple[int, int],
    *,
    padding: int = 2,
    scale: float | None = None,
) -> Image.Image:
    """Recorta alfa y centra al pie usando nearest-neighbor."""
    crop = image.crop(_alpha_bbox(image))
    avail_w = size[0] - 2 * padding
    avail_h = size[1] - 2 * padding
    factor = scale if scale is not None else min(avail_w / crop.width, avail_h / crop.height)
    w = max(1, round(crop.width * factor))
    h = max(1, round(crop.height * factor))
    resized = crop.resize((w, h), Image.Resampling.NEAREST)
    canvas = Image.new("RGBA", size, (0, 0, 0, 0))
    canvas.alpha_composite(resized, ((size[0] - w) // 2, size[1] - padding - h))
    return canvas


def _build_player() -> None:
    run_sheet = Image.open(SOURCE / "run_cycle_6_alpha.png").convert("RGBA")
    run_cells = []
    for row in range(2):
        for col in range(3):
            box = (
                round(run_sheet.width * col / 3),
                round(run_sheet.height * row / 2),
                round(run_sheet.width * (col + 1) / 3),
                round(run_sheet.height * (row + 1) / 2),
            )
            run_cells.append(run_sheet.crop(box))

    # Todos los cuadros comparten escala para que el cuerpo no cambie de
    # tamano durante la animacion. El anclaje inferior sigue siendo identico.
    run_crops = [cell.crop(_alpha_bbox(cell)) for cell in run_cells]
    common_scale = min(
        88 / max(c.width for c in run_crops),
        142 / max(c.height for c in run_crops),
    )
    for index, cell in enumerate(run_cells):
        sprite = _fit_pixel(cell, (92, 146), scale=common_scale)
        sprite.save(SPRITES / f"player_run_{index}.png", optimize=True)

    # Mantener los nombres anteriores facilita abrir proyectos/previews viejos.
    _fit_pixel(run_cells[0], (92, 146), scale=common_scale).save(
        SPRITES / "player_run_a.png", optimize=True
    )
    _fit_pixel(run_cells[3], (92, 146), scale=common_scale).save(
        SPRITES / "player_run_b.png", optimize=True
    )

    old_sheet = Image.open(SOURCE / "player_sheet_alpha.png").convert("RGBA")
    air_cell = old_sheet.crop((round(old_sheet.width * 2 / 3), 0, old_sheet.width, old_sheet.height))
    _fit_pixel(air_cell, (92, 146)).save(SPRITES / "player_air.png", optimize=True)


def _build_ui() -> None:
    sheet = Image.open(SOURCE / "ui_sheet_alpha.png").convert("RGBA")
    names = (("logo.png", "jump.png"), ("dodge.png", "stretch.png"))
    for row in range(2):
        for col in range(2):
            box = (
                round(sheet.width * col / 2),
                round(sheet.height * row / 2),
                round(sheet.width * (col + 1) / 2),
                round(sheet.height * (row + 1) / 2),
            )
            _fit_pixel(sheet.crop(box), (72, 72), padding=1).save(UI / names[row][col])


def _build_background(source_name: str, output_name: str, *, darken: float = 1.0) -> None:
    image = Image.open(SOURCE / source_name).convert("RGB")
    target_ratio = 540 / 900
    source_ratio = image.width / image.height
    if source_ratio > target_ratio:
        width = round(image.height * target_ratio)
        left = (image.width - width) // 2
        image = image.crop((left, 0, left + width, image.height))
    elif source_ratio < target_ratio:
        height = round(image.width / target_ratio)
        top = (image.height - height) // 2
        image = image.crop((0, top, image.width, top + height))
    image = image.resize((540, 900), Image.Resampling.LANCZOS)
    if darken != 1.0:
        image = ImageEnhance.Brightness(image).enhance(darken)
    image.save(BACKGROUNDS / output_name, optimize=True)


def main() -> None:
    for directory in (SPRITES, BACKGROUNDS, UI):
        directory.mkdir(parents=True, exist_ok=True)

    _build_player()
    _fit_pixel(Image.open(SOURCE / "boss_alpha.png").convert("RGBA"), (210, 190)).save(
        SPRITES / "boss.png"
    )
    _fit_pixel(Image.open(SOURCE / "chair_alpha.png").convert("RGBA"), (110, 220)).save(
        SPRITES / "chair.png"
    )
    _fit_pixel(Image.open(SOURCE / "pdf_alpha.png").convert("RGBA"), (126, 118)).save(
        SPRITES / "pdf.png"
    )

    boxes_source = Image.open(SOURCE / "boxes_alpha.png").convert("RGBA")
    boxes = boxes_source.crop(_alpha_bbox(boxes_source))
    # La barrera logica es deliberadamente muy baja y ocupa todo el ancho.
    boxes.resize((495, 34), Image.Resampling.NEAREST).save(SPRITES / "boxes.png")

    _build_ui()
    _build_background("office_background_clean.png", "office.png")
    _build_background("intro_background.png", "intro.png", darken=0.82)
    _build_background("water_background.png", "water_break.png")

    print("Assets visuales construidos en assets/{sprites,backgrounds,ui}")


if __name__ == "__main__":
    main()
