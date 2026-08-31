"""Build the photo collage shown in the repository README.

Every image in ``photos/`` becomes one labelled cell of a square-ish grid. The
filename (``Firstname_Lastname.jpg``) becomes the caption, so the collage stays
in sync with the folder without anyone maintaining a list of names.

Run it from anywhere:

    python code/make_collage.py

Or point it at other locations:

    python code/make_collage.py --photos-dir /tmp/photos --output /tmp/out.jpg
"""

from __future__ import annotations

import argparse
import logging
import math
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_PHOTOS_DIR = REPO_ROOT / "photos"
DEFAULT_OUTPUT = REPO_ROOT / "collage.jpg"
FONT_PATH = Path(__file__).resolve().parent / "SourceCodePro-BoldItalic.ttf"

PHOTO_EXTENSIONS = (".jpg", ".jpeg", ".png")
CELL_SIZE = (300, 300)
CAPTION_COLOR = (255, 255, 255)
CAPTION_STROKE_COLOR = (0, 0, 0)
CAPTION_STROKE_WIDTH = 3
CAPTION_MARGIN = 8
CAPTION_MAX_SIZE = 26
CAPTION_MIN_SIZE = 12

logger = logging.getLogger(__name__)


def find_photos(photos_dir: Path) -> list[Path]:
    """Return the photos to include, sorted by filename for a stable layout.

    Args:
        photos_dir: Directory holding one image per person.

    Returns:
        Sorted list of image paths, ignoring subdirectories and non-images such
        as the folder's own README.
    """
    if not photos_dir.is_dir():
        raise NotADirectoryError(f"photos directory not found: {photos_dir}")

    photos = [
        path
        for path in sorted(photos_dir.iterdir())
        if path.is_file() and path.suffix.lower() in PHOTO_EXTENSIONS
    ]
    logger.info("Found %d photo(s) in %s", len(photos), photos_dir)
    return photos


def grid_shape(count: int) -> tuple[int, int]:
    """Choose a square-ish ``(rows, cols)`` grid with no empty trailing row.

    Args:
        count: Number of photos to place. Must be positive.

    Returns:
        Rows and columns, where ``rows * cols >= count`` and removing a row
        would leave too few cells.
    """
    assert count > 0, "grid_shape requires at least one photo"
    cols = math.ceil(math.sqrt(count))
    rows = math.ceil(count / cols)
    return rows, cols


def caption_for(path: Path) -> str:
    """Turn ``photos/Ada_Lovelace.jpg`` into the caption ``Ada Lovelace``."""
    return path.stem.replace("_", " ")


def fit_caption_font(text: str, max_width: int) -> ImageFont.FreeTypeFont:
    """Pick the largest caption font size that keeps ``text`` inside ``max_width``.

    Long names such as ``Santiago Ramon-y-Cajal`` would otherwise run off the
    edge of their cell.

    Args:
        text: Caption to be drawn.
        max_width: Width in pixels the caption must fit within.

    Returns:
        A loaded font, no smaller than ``CAPTION_MIN_SIZE`` even if the caption
        still does not fit at that size.
    """
    for size in range(CAPTION_MAX_SIZE, CAPTION_MIN_SIZE - 1, -1):
        font = ImageFont.truetype(str(FONT_PATH), size)
        left, _, right, _ = font.getbbox(text, stroke_width=CAPTION_STROKE_WIDTH)
        if right - left <= max_width:
            return font
    return ImageFont.truetype(str(FONT_PATH), CAPTION_MIN_SIZE)


def load_cell(path: Path, size: tuple[int, int]) -> Image.Image:
    """Load one photo as an RGB cell of exactly ``size``, captioned with its name.

    Applies the EXIF orientation tag first, so photos straight off a phone are
    not rotated 90 degrees, then centre-crops to fill the cell.

    Args:
        path: Image file to load.
        size: Target ``(width, height)`` in pixels.

    Returns:
        An ``RGB`` image of shape ``size`` with the person's name drawn on it.
    """
    with Image.open(path) as raw:
        oriented = ImageOps.exif_transpose(raw)
        cell = ImageOps.fit(
            oriented.convert("RGB"), size, method=Image.Resampling.LANCZOS
        )

    caption = caption_for(path)
    font = fit_caption_font(caption, size[0] - 2 * CAPTION_MARGIN)
    draw = ImageDraw.Draw(cell)
    draw.text(
        (CAPTION_MARGIN, CAPTION_MARGIN),
        caption,
        font=font,
        fill=CAPTION_COLOR,
        stroke_width=CAPTION_STROKE_WIDTH,
        stroke_fill=CAPTION_STROKE_COLOR,
    )
    return cell


def build_collage(
    photo_paths: list[Path], cell_size: tuple[int, int] = CELL_SIZE
) -> Image.Image:
    """Compose the photos into a single labelled grid image.

    Args:
        photo_paths: Images to place, in the order they should appear.
        cell_size: ``(width, height)`` each photo is resized to.

    Returns:
        An ``RGB`` collage of shape ``(cols * width, rows * height)``.
    """
    assert photo_paths, "build_collage requires at least one photo"

    rows, cols = grid_shape(len(photo_paths))
    cell_width, cell_height = cell_size
    collage = Image.new("RGB", (cell_width * cols, cell_height * rows))
    logger.info("Building a %dx%d grid for %d photo(s)", rows, cols, len(photo_paths))

    for index, path in enumerate(photo_paths):
        row, col = divmod(index, cols)
        collage.paste(load_cell(path, cell_size), (cell_width * col, cell_height * row))

    return collage


def build_placeholder(size: tuple[int, int] = (900, 300)) -> Image.Image:
    """Render a stand-in collage for when nobody has added a photo yet.

    Keeps ``collage.jpg`` a valid image at all times, so the README never shows
    a broken image to the first student who opens it.

    Args:
        size: ``(width, height)`` of the placeholder in pixels.

    Returns:
        An ``RGB`` image inviting the reader to add the first photo.
    """
    placeholder = Image.new("RGB", size, (32, 34, 40))
    draw = ImageDraw.Draw(placeholder)
    font = ImageFont.truetype(str(FONT_PATH), 34)
    message = "No photos yet.\nAdd yours to photos/ and be the first."
    draw.multiline_text(
        (size[0] // 2, size[1] // 2),
        message,
        font=font,
        fill=CAPTION_COLOR,
        anchor="mm",
        align="center",
        spacing=14,
    )
    return placeholder


def write_collage(photos_dir: Path, output: Path) -> Path:
    """Generate the collage for ``photos_dir`` and save it to ``output``.

    Args:
        photos_dir: Directory holding one image per person.
        output: Path of the JPEG to write. Parent directories must exist.

    Returns:
        The path that was written.
    """
    photo_paths = find_photos(photos_dir)
    collage = build_collage(photo_paths) if photo_paths else build_placeholder()
    if not photo_paths:
        logger.warning("No photos found, writing a placeholder collage instead")

    collage.save(output, "JPEG", quality=90)
    logger.info("Wrote %s (%dx%d)", output, collage.width, collage.height)
    return output


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command line arguments for the collage builder."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--photos-dir",
        type=Path,
        default=DEFAULT_PHOTOS_DIR,
        help=f"directory of photos to collage (default: {DEFAULT_PHOTOS_DIR})",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"JPEG to write (default: {DEFAULT_OUTPUT})",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Entry point. Returns a process exit code."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    args = parse_args(argv)

    if not FONT_PATH.is_file():
        logger.error("Caption font is missing: %s", FONT_PATH)
        return 1

    write_collage(args.photos_dir, args.output)
    return 0


if __name__ == "__main__":
    sys.exit(main())
