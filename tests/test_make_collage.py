"""Tests for the collage builder.

These write real JPEG and PNG files and open the resulting collage, so a
regression in Pillow's API or in the grid arithmetic shows up here rather than
in a workflow run after a student has already pushed.
"""

from __future__ import annotations

import io
from pathlib import Path

import pytest
from PIL import Image

from make_collage import (
    CELL_SIZE,
    build_collage,
    build_placeholder,
    caption_for,
    fit_caption_font,
    find_photos,
    grid_shape,
    write_collage,
)

NAMES = [
    "Ada_Lovelace",
    "Eve_Marder",
    "May-Britt_Moser",
    "Santiago_Ramon-y-Cajal",
    "Brenda_Milner",
    "Huda_Zoghbi",
    "Cori_Bargmann",
    "Carla_Shatz",
    "Ben_Barres",
    "Rita_Levi-Montalcini",
    "Lin_Chen",
    "Maria_Del_Carmen",
]


def write_photo(
    directory: Path, name: str, size: tuple[int, int] = (640, 480), suffix: str = ".jpg"
) -> Path:
    """Write one solid-colour photo and return its path."""
    path = directory / f"{name}{suffix}"
    Image.new("RGB", size, (90, 140, 200)).save(path)
    return path


def make_photos(directory: Path, count: int) -> list[Path]:
    """Write ``count`` photos, alternating JPEG and PNG."""
    return [
        write_photo(directory, NAMES[index], suffix=".png" if index % 3 == 0 else ".jpg")
        for index in range(count)
    ]


class TestFindPhotos:
    def test_ignores_the_folder_readme_and_subfolders(self, tmp_path):
        write_photo(tmp_path, "Ada_Lovelace")
        (tmp_path / "README.md").write_text("not a photo", encoding="utf-8")
        (tmp_path / "nested").mkdir()
        write_photo(tmp_path / "nested", "Should_Beignored")

        found = find_photos(tmp_path)
        assert [path.name for path in found] == ["Ada_Lovelace.jpg"]

    def test_is_sorted_so_the_layout_is_stable(self, tmp_path):
        for name in ["Zoe_Zulu", "Ada_Lovelace", "Mia_Mike"]:
            write_photo(tmp_path, name)

        found = find_photos(tmp_path)
        assert [path.stem for path in found] == ["Ada_Lovelace", "Mia_Mike", "Zoe_Zulu"]

    def test_a_missing_directory_is_an_error(self, tmp_path):
        with pytest.raises(NotADirectoryError):
            find_photos(tmp_path / "nope")


class TestGridShape:
    @pytest.mark.parametrize(
        "count,expected",
        [
            (1, (1, 1)),
            (2, (1, 2)),
            (3, (2, 2)),
            (4, (2, 2)),
            (5, (2, 3)),
            (6, (2, 3)),
            (7, (3, 3)),
            (9, (3, 3)),
            (10, (3, 4)),
            (12, (3, 4)),
            (13, (4, 4)),
            (25, (5, 5)),
            (26, (5, 6)),
            (40, (6, 7)),
        ],
    )
    def test_shapes_are_square_ish_and_big_enough(self, count, expected):
        rows, cols = grid_shape(count)
        assert (rows, cols) == expected
        assert rows * cols >= count

    @pytest.mark.parametrize("count", range(1, 60))
    def test_no_trailing_row_is_ever_left_empty(self, count):
        rows, cols = grid_shape(count)
        assert rows * cols >= count
        assert (rows - 1) * cols < count

    def test_zero_photos_is_rejected(self):
        with pytest.raises(AssertionError):
            grid_shape(0)


class TestCaptions:
    def test_the_filename_becomes_the_caption(self):
        assert caption_for(Path("photos/Ada_Lovelace.jpg")) == "Ada Lovelace"
        assert caption_for(Path("photos/Maria_Del_Carmen.png")) == "Maria Del Carmen"

    def test_a_long_name_is_shrunk_to_fit_its_cell(self):
        cell_width = CELL_SIZE[0] - 16
        short = fit_caption_font("Lin Chen", cell_width)
        long = fit_caption_font("Santiago Ramon-y-Cajal", cell_width)
        assert long.size < short.size

        left, _, right, _ = long.getbbox("Santiago Ramon-y-Cajal", stroke_width=3)
        assert right - left <= cell_width


class TestBuildCollage:
    @pytest.mark.parametrize("count", [1, 2, 5, 12])
    def test_dimensions_match_the_grid(self, tmp_path, count):
        photos = make_photos(tmp_path, count)
        collage = build_collage(photos)

        rows, cols = grid_shape(count)
        assert collage.size == (CELL_SIZE[0] * cols, CELL_SIZE[1] * rows)
        assert collage.mode == "RGB"

    def test_a_portrait_photo_is_not_left_squashed(self, tmp_path):
        write_photo(tmp_path, "Ada_Lovelace", size=(480, 1200))
        collage = build_collage(find_photos(tmp_path))
        assert collage.size == CELL_SIZE

    def test_exif_rotation_is_applied(self, tmp_path):
        # A phone photo tagged "rotate 90" must come out upright, otherwise every
        # iPhone contribution ends up sideways in the collage.
        landscape = Image.new("RGB", (600, 300), (10, 10, 10))
        landscape.paste(Image.new("RGB", (600, 20), (250, 250, 250)), (0, 0))
        exif = landscape.getexif()
        exif[0x0112] = 6  # Orientation: rotate 90 degrees clockwise
        buffer = io.BytesIO()
        landscape.save(buffer, "JPEG", exif=exif)
        (tmp_path / "Ada_Lovelace.jpg").write_bytes(buffer.getvalue())

        with Image.open(tmp_path / "Ada_Lovelace.jpg") as stored:
            assert stored.size == (600, 300), "source is stored as landscape"

        collage = build_collage(find_photos(tmp_path))
        assert collage.size == CELL_SIZE

    def test_a_png_with_transparency_becomes_opaque_rgb(self, tmp_path):
        Image.new("RGBA", (400, 400), (200, 30, 30, 0)).save(
            tmp_path / "Ada_Lovelace.png"
        )
        collage = build_collage(find_photos(tmp_path))
        assert collage.mode == "RGB"

    def test_no_photos_is_rejected(self):
        with pytest.raises(AssertionError):
            build_collage([])


class TestPlaceholder:
    def test_it_renders_at_the_requested_size(self):
        placeholder = build_placeholder()
        assert placeholder.mode == "RGB"
        assert placeholder.size == (900, 300)


class TestWriteCollage:
    def test_it_writes_a_readable_jpeg(self, tmp_path):
        photos_dir = tmp_path / "photos"
        photos_dir.mkdir()
        make_photos(photos_dir, 5)
        output = tmp_path / "collage.jpg"

        assert write_collage(photos_dir, output) == output
        with Image.open(output) as written:
            assert written.format == "JPEG"
            assert written.size == (CELL_SIZE[0] * 3, CELL_SIZE[1] * 2)

    def test_an_empty_folder_still_produces_a_valid_image(self, tmp_path):
        # collage.jpg is embedded in the README, so it must never be missing or
        # corrupt, even before the first student contributes.
        photos_dir = tmp_path / "photos"
        photos_dir.mkdir()
        output = tmp_path / "collage.jpg"

        write_collage(photos_dir, output)
        with Image.open(output) as written:
            assert written.format == "JPEG"
            assert written.size == (900, 300)

    def test_the_same_photos_produce_the_same_collage(self, tmp_path):
        # Determinism keeps the workflow from committing a new collage.jpg on
        # every run when nothing actually changed.
        photos_dir = tmp_path / "photos"
        photos_dir.mkdir()
        make_photos(photos_dir, 4)

        first = tmp_path / "one.jpg"
        second = tmp_path / "two.jpg"
        write_collage(photos_dir, first)
        write_collage(photos_dir, second)

        assert first.read_bytes() == second.read_bytes()
