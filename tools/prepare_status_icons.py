"""Pack generated status art for the 24–60 dp UI without baking frames into PNGs."""
import json
import shutil
from pathlib import Path
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
manifest_path = ROOT / 'assets/status-redraw-manifest.json'
manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
for asset in manifest['assets']:
    image = Image.open(asset['source']).convert('RGBA')
    assert image.getchannel('A').getextrema()[0] == 0, asset['path']
    image = image.resize((128, 128), Image.Resampling.LANCZOS)
    target = ROOT / asset['path']
    target.parent.mkdir(parents=True, exist_ok=True)
    image.save(target, optimize=True)
for target, source in manifest['aliases'].items():
    shutil.copy2(ROOT / source, ROOT / target)
sheet = Image.new('RGB', (880, ((len(manifest['assets']) + 5) // 6) * 150), (10, 17, 27))
draw = ImageDraw.Draw(sheet)
for index, asset in enumerate(manifest['assets']):
    image = Image.open(ROOT / asset['path'])
    image.thumbnail((88, 88))
    x, y = (index % 6) * 146, (index // 6) * 150
    sheet.paste(image, (x + 28, y + 6), image)
    small = image.resize((28, 28), Image.Resampling.LANCZOS)
    sheet.paste(small, (x + 58, y + 96), small)
    draw.text((x + 6, y + 128), Path(asset['path']).name, fill=(218, 207, 178))
sheet.save(ROOT / 'assets/status-icons-redrawn.jpg', quality=92)
print(f"Packed {len(manifest['assets'])} generated icons and {len(manifest['aliases'])} aliases")
