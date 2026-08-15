"""Regenerate the image fixtures: `python -m tests.fixtures.make_image_fixtures`.

Generated rather than committed as photographs, for the same reason the PDF fixtures are:
each one stands for a specific failure mode, and building them in code makes the mode explicit
instead of leaving it as a property of some binary nobody can diff.
"""

import io
from pathlib import Path

from PIL import Image, ImageDraw

HERE = Path(__file__).parent

LABEL_TEXT = """\
ROLLED OATS

Nutrition Information
Servings per pack: 10
Serving size: 40 g

                Per 100 g
Energy           379 kcal
Protein           13.2 g
Carbohydrate      67.7 g
Fat                6.5 g
Fibre             10.1 g
Sugars             1.1 g
Sodium               6 mg
"""


def _label_image(size: tuple[int, int] = (560, 420)) -> Image.Image:
    image = Image.new("RGB", size, "white")
    ImageDraw.Draw(image).multiline_text((24, 24), LABEL_TEXT, fill="black", spacing=4)
    return image


def write_label(path: Path) -> None:
    _label_image().save(path, "JPEG", quality=90)


def write_rotated_label(path: Path) -> None:
    """The same label stored sideways with an EXIF orientation tag.

    This is what a phone produces: the pixels are rotated and a tag says how to put them
    back. Code that ignores the tag reads a sideways label and quietly does badly.
    """
    image = _label_image().rotate(-90, expand=True)

    # EXIF orientation 6 = "rotate 90° clockwise to display correctly".
    exif = Image.Exif()
    exif[0x0112] = 6
    image.save(path, "JPEG", quality=90, exif=exif)


def write_plate(path: Path) -> None:
    """Stands in for a meal photo. Content is irrelevant — the stub cannot see it anyway."""
    image = Image.new("RGB", (640, 480), (222, 210, 190))
    draw = ImageDraw.Draw(image)
    draw.ellipse((80, 60, 560, 420), fill="white", outline=(180, 180, 180), width=3)
    draw.ellipse((150, 130, 330, 280), fill=(190, 140, 90))
    draw.ellipse((320, 180, 470, 330), fill=(240, 235, 220))
    draw.ellipse((220, 280, 350, 380), fill=(110, 150, 80))
    image.save(path, "JPEG", quality=85)


def write_huge(path: Path) -> None:
    """Large in pixels, tiny on disk — a decompression bomb passes any byte-size check."""
    buffer = io.BytesIO()
    Image.new("RGB", (9000, 9000), "white").save(buffer, "PNG", optimize=True)
    path.write_bytes(buffer.getvalue())


def main() -> None:
    write_label(HERE / "label.jpg")
    write_rotated_label(HERE / "label_rotated.jpg")
    write_plate(HERE / "plate.jpg")
    write_huge(HERE / "huge.png")
    print(f"Wrote image fixtures to {HERE}")


if __name__ == "__main__":
    main()
