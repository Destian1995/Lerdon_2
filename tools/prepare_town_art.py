"""Package generated town art; preserve alpha, trim empty sprite margins and size for mobile."""
import argparse
import hashlib
import json
from pathlib import Path
from PIL import Image

ROOT=Path(__file__).resolve().parents[1]


def prepare(records):
    result=[]
    for entry in records:
        faction=entry['key']
        if not faction.isascii() or not faction.replace('_','').isalnum():raise ValueError(faction)
        folder=ROOT/'files/city/interiors'/faction;folder.mkdir(parents=True,exist_ok=True)
        with Image.open(entry['path']) as original:
            if 'building' in entry:
                name=entry['building']
                if name not in ('hospital','factory','wall','market','forge','citadel'):raise ValueError(name)
                art=original.convert('RGBA')
                if art.getchannel('A').getextrema()[0]!=0:raise ValueError(f'No transparency: {entry["path"]}')
                bounds=art.getchannel('A').getbbox()
                if not bounds:raise ValueError('Empty building sprite')
                art=art.crop(bounds);art.thumbnail((640,640),Image.Resampling.LANCZOS)
                final=Image.new('RGBA',(art.width+8,art.height+8));final.paste(art,(4,4))
                target=folder/(name+'.png');final.save(target,optimize=True)
                size=final.size
            else:
                art=original.convert('RGB');art.thumbnail((1536,1024),Image.Resampling.LANCZOS)
                target=folder/f'city-{entry["variant"]}.jpg';art.save(target,quality=91,optimize=True)
                size=art.size
        result.append(dict(file=target.relative_to(ROOT).as_posix(),size=size,
                           sha256=hashlib.sha256(target.read_bytes()).hexdigest(),prompt=entry['prompt'],
                           reference=f'files/city/interiors/{faction}/city-1.jpg' if 'building' in entry or entry.get('variant')!=1 else None))
    manifest=ROOT/'assets/town-art-prompts.json'
    manifest.write_text(json.dumps(dict(generator='built-in image_gen',assets=result),ensure_ascii=False,indent=2),encoding='utf-8')
    print(f'Packaged {len(result)} town assets; prompts: {manifest}')


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('sources')
    args=parser.parse_args()
    prepare(json.loads(Path(args.sources).read_text(encoding='utf-8')))
