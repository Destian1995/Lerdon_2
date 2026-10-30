"""Inspect generated UI icons at large size and at their actual 22px use size."""
import io
import json
from pathlib import Path
import subprocess
from PIL import Image, ImageDraw, ImageOps

ROOT = Path(__file__).resolve().parents[1]


def render():
    data = json.loads((ROOT / 'assets/pict-redraw-manifest.json').read_text(encoding='utf-8'))
    entries = data['entries']
    sheet = Image.new('RGB', (1200, 4 * 235 + 30), '#131c29')
    draw = ImageDraw.Draw(sheet)
    draw.text((12, 8), 'FILES/PICT | OLD / NEW | Bottom samples: actual 22px on dark and light backgrounds', fill='white')
    before_bytes = after_bytes = 0
    for index, entry in enumerate(entries):
        x, y = index % 5 * 240, index // 5 * 235 + 30
        draw.rounded_rectangle((x + 3, y + 3, x + 237, y + 230), radius=8, fill='#222f40')
        draw.text((x + 10, y + 10), entry['key'], fill='#d8e6f5')
        old = Image.open(io.BytesIO(subprocess.check_output(['git', 'show', 'HEAD:' + entry['output']], cwd=ROOT))).convert('RGBA')
        new = Image.open(ROOT / entry['output']).convert('RGBA')
        before_bytes += old.width * old.height * 4
        after_bytes += new.width * new.height * 4
        old = ImageOps.contain(old, (68, 110), Image.Resampling.LANCZOS)
        big = ImageOps.contain(new, (122, 122), Image.Resampling.LANCZOS)
        sheet.paste(old, (x + 7 + (68 - old.width) // 2, y + 43 + (110 - old.height) // 2), old)
        sheet.paste(big, (x + 99 + (122 - big.width) // 2, y + 35 + (122 - big.height) // 2), big)
        draw.text((x + 17, y + 161), 'OLD', fill='#8394a8')
        draw.text((x + 139, y + 161), 'NEW', fill='#d8e6f5')
        small = new.resize((22, 22), Image.Resampling.LANCZOS)
        draw.rectangle((x + 10, y + 183, x + 111, y + 220), fill='#101722')
        draw.rectangle((x + 124, y + 183, x + 225, y + 220), fill='#e9dfc3')
        sheet.paste(small, (x + 50, y + 190), small)
        sheet.paste(small, (x + 164, y + 190), small)
    sheet.save(ROOT / 'assets/pict-icons-redrawn.jpg', quality=95)
    print('Original decoded RGBA MiB:', round(before_bytes / 1048576, 2))
    print('New decoded RGBA MiB:', round(after_bytes / 1048576, 2))
    print('Runtime PNG KiB:', round(sum((ROOT / e['output']).stat().st_size for e in entries) / 1024, 1))


if __name__ == '__main__':
    render()
