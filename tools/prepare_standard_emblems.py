"""Make small, high-contrast banner glyphs from the existing faction symbols."""
from pathlib import Path
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
SOURCES = ('people', 'elfs', 'vampires', 'adepts', 'poly', 'castle_death', 'keig', 'default')


def make_skull(output):
    """Bone-white heraldic skull; transparent sockets show the dark cloth."""
    scale = 4
    mask = Image.new('L', (96 * scale, 96 * scale))
    draw = ImageDraw.Draw(mask)
    def box(values):
        return tuple(value * scale for value in values)
    draw.ellipse(box((20, 10, 76, 68)), fill=255)
    draw.polygon([(x * scale, y * scale) for x, y in
                  ((19, 43), (77, 43), (74, 62), (64, 67), (62, 83),
                   (34, 83), (32, 67), (22, 62))], fill=255)
    draw.rounded_rectangle(box((30, 59, 66, 87)), radius=6 * scale, fill=255)
    for eye in ((27, 35, 44, 51), (52, 35, 69, 51)):
        draw.ellipse(box(eye), fill=0)
    draw.polygon([(48 * scale, 51 * scale), (42 * scale, 62 * scale),
                  (54 * scale, 62 * scale)], fill=0)
    draw.rectangle(box((34, 69, 62, 71)), fill=0)
    for x in (39, 47, 55):
        draw.rectangle(box((x, 74, x + 2, 88)), fill=0)
    glyph = Image.new('RGBA', (96, 96), (237, 236, 222, 0))
    glyph.putalpha(mask.resize((96, 96), Image.Resampling.LANCZOS))
    glyph.save(output / 'skull.png', optimize=True)


def main():
    output = ROOT / 'files/status/army_in_city/standards'
    output.mkdir(exist_ok=True)
    for source in SOURCES:
        with Image.open(ROOT / f'files/buildings/{source}.png') as image:
            alpha = image.convert('RGBA').getchannel('A')
            alpha = alpha.crop(alpha.getbbox())
            alpha.thumbnail((88, 88), Image.Resampling.LANCZOS)
            glyph = Image.new('RGBA', alpha.size, (255, 230, 166, 0))
            glyph.putalpha(alpha)
            canvas = Image.new('RGBA', (96, 96))
            canvas.paste(glyph, ((96 - glyph.width) // 2, (96 - glyph.height) // 2))
            canvas.save(output / f'{source}.png', optimize=True)
    make_skull(output)


if __name__ == '__main__':
    main()
