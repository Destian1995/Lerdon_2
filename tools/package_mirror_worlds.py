"""Package approved faction landscapes and retain their generation provenance."""
import hashlib
import json
from pathlib import Path
import sys

from PIL import Image

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from otherworld_themes import THEMES,CITY_LAYOUTS

LANDSCAPES={
    'north':'Separate snowy Nordic islands, broad sea channels, fjords and harbours',
    'elves':'Ancient emerald forest, turquoise lakes, river deltas and waterfalls',
    'vampires':'Basalt gorges, misty marshes, blackwater lakes and burgundy woodland',
    'adepts':'Rust-orange autumn woodland, rocky rivers and crusader abbey ruins',
    'elines':'Golden dunes, sandstone mesas, slot canyons and scattered oases',
}


def package(records):
    known={theme['key'] for theme in THEMES.values()}
    assert len({(r['key'],r.get('kind','map')) for r in records})==len(records),'Duplicate faction asset'
    previous=ROOT/'assets/city-redesign-prompts.json'
    city_art=json.loads(previous.read_text(encoding='utf-8'))
    prompts={}
    for record in records:
        key=record['key']
        if key not in known:raise ValueError(key)
        kind=record.get('kind','map')
        if kind not in ('map','cities'):raise ValueError(kind)
        folder=ROOT/'files/otherworld/themes'/key
        target=folder/(kind+'.png')
        with Image.open(record['path']) as image:
            if kind=='map':
                if image.width<=image.height:raise ValueError('Map must be landscape')
                image=image.convert('RGB');image.thumbnail((1536,1024),Image.Resampling.LANCZOS)
            else:
                image=image.convert('RGBA')
                if image.getchannel('A').getextrema()[0]!=0:raise ValueError('Cities require transparency')
                image.thumbnail((1536,1536),Image.Resampling.LANCZOS)
                entries={}
                for i in range(7):
                    left=round(i%3*image.width/3)+2;right=round((i%3+1)*image.width/3)-2
                    top=round(i//3*image.height/3)+2;bottom=round((i//3+1)*image.height/3)-2
                    entries[f'city_{i+1}']=[left,image.height-bottom,right-left,bottom-top]
                (folder/'cities.atlas').write_text(json.dumps({'cities.png':entries},indent=2),encoding='utf-8')
            staged=target.with_name(target.stem+'.new.png')
            image.save(staged,optimize=True)
            staged.replace(target)
        prompts[key,kind]=record['prompt']
        entry=key+'_mirror_'+kind
        city_art[entry]=dict(generator='built-in image_gen',prompt=record['prompt'],
                            files=[target.relative_to(ROOT).as_posix()])
    previous.write_text(json.dumps(city_art,ensure_ascii=False,indent=2),encoding='utf-8')
    worlds=[]
    for faction,theme in THEMES.items():
        key=theme['key'];target=ROOT/'files/otherworld/themes'/key/'map.png'
        prompt=prompts.get((key,'map'),city_art.get(key+'_mirror_map',{}).get('prompt',''))
        with Image.open(target) as image:size=list(image.size)
        worlds.append(dict(faction=faction,key=key,landscape=LANDSCAPES[key],
            file=target.relative_to(ROOT).as_posix(),size=size,
            sha256=hashlib.sha256(target.read_bytes()).hexdigest(),prompt=prompt,
            city_atlas=(target.parent/'cities.atlas').relative_to(ROOT).as_posix(),
            architecture_prompt=city_art.get(key+'_mirror_cities',{}).get('prompt',''),
            city_positions=list(CITY_LAYOUTS[key]),
            replaced=(key,'map') in prompts))
    manifest=dict(generator='built-in image_gen',
        style_reference='User-approved autumn forest map with rivers, clearings and small ruins',
        worlds=worlds)
    (ROOT/'assets/mirror-geography-prompts.json').write_text(
        json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    print('Packaged',len(records),'map/city assets; documented all',len(worlds),'faction worlds')


if __name__=='__main__':
    package(json.loads(Path(sys.argv[1]).read_text(encoding='utf-8')))
