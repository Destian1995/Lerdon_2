"""Prepare generated icons for runtime: alpha-aware trim, resample, PNG encoding.

This performs no painting or semantic image edits. Original generated images
remain in Codex's image output directory; only compact runtime PNGs are shipped.
"""
import argparse
import hashlib
import json
from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]


def prepare(require_complete=False):
    path = ROOT / 'assets/pict-redraw-manifest.json'
    data = json.loads(path.read_text(encoding='utf-8'))
    for entry in data['entries']:
        if not entry['source']:
            if require_complete:
                raise RuntimeError('Missing generated icon: ' + entry['output'])
            continue
        with Image.open(entry['source']) as image:
            image = image.convert('RGBA')
            alpha = image.getchannel('A')
            if alpha.getextrema()[0] == 255:
                raise ValueError('Generated image is not transparent: ' + entry['key'])
            bbox = alpha.point(lambda value: 255 if value > 12 else 0).getbbox()
            if bbox is None:
                raise ValueError('Empty generated icon: ' + entry['key'])
            image = image.crop(bbox)
            size = entry['size']
            image.thumbnail((round(size * .88), round(size * .88)), Image.Resampling.LANCZOS)
            output = Image.new('RGBA', (size, size))
            output.alpha_composite(image, ((size - image.width) // 2, (size - image.height) // 2))
            destination = ROOT / entry['output']
            output.save(destination, optimize=True)
            entry['sha256'] = hashlib.sha256(destination.read_bytes()).hexdigest()
            entry['bytes'] = destination.stat().st_size
            entry['alpha_bbox'] = output.getchannel('A').getbbox()
            print(entry['output'], output.size, entry['bytes'])
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--require-complete', action='store_true')
    prepare(parser.parse_args().require_complete)
