"""Package the generated city atlases without changing their painted content."""
import json
from pathlib import Path
from PIL import Image

ROOT=Path(__file__).resolve().parents[1]
PROMPTS={
    'elines_town':'Three separate wide desert castle town panoramas matching the northern city reference: detailed weathered sandstone fortresses, terraced construction grounds, stone steps and cobbled paths, oasis water and palms, painterly fantasy strategy architecture. No UI, labels or text.',
    'adepts_town':'Three separate wide crusader abbey town panoramas in rust-orange autumn forest, matching the northern city reference: fortified limestone monasteries, Romanesque cloisters, chapels, slate and timber roofs, crenellated towers, terraced construction grounds, stone steps and cobbled paths. No Victorian or industrial architecture, labels or text.',
    'citadel_atlas':'Transparent 4x2 atlas of eight substantial multi-towered citadels, complete isolated silhouettes, elevated painterly strategy camera. Order: snowy northern stone, elven living wood, vampire gothic, adept Victorian redbrick; Eline desert sandstone, undead bone and spectral green, rebel patched stone and red cloth, neutral medieval limestone. No text, no ground tiles, no narrow watchtowers.',
    'adepts_mirror_cities':'Transparent 3x3 atlas of nine distinct fortified crusader abbey cities with limestone chapels, Romanesque cloisters, crenellated towers, slate roofs, arched gates and rust-orange autumn trees. Detailed painterly medieval architecture matching the northern city reference; no Victorian buildings, equal cells, no overlaps or text.',
    'elines_mirror_cities':'Transparent 3x3 atlas of nine distinct desert castle cities, warm sandstone fortress-palaces and crenellated citadels, terraced adobe, copper domes, dusty dunes and oasis palms. Miniature elevated painterly game cities; equal cells, no overlaps, text or Greek acropolis.',
    'adepts_mirror_map':'Wide painterly overhead fantasy strategy terrain: rust-orange copper amber autumn forests, rocky gorge, rivers, stone bridges, cobbled paths and small abandoned medieval crusader abbey ruins. Clear empty ground for separate town icons. No Victorian or industrial structures, text, labels, UI, grids or large cities.',
    'elines_mirror_map':'Wide painterly overhead fantasy strategy terrain: vast warm ochre desert dunes, sandstone plateaus and canyons, dry wadis, turquoise oases with sparse palms and caravan roads. Clear sandy plots for separate city icons. No Greek countryside, forests, labels, UI or grids.',
    'adepts_buildings':'Transparent 3x2 atlas of six complete medieval crusader abbey strategy sprites matching the northern city reference: limestone, Romanesque arches, slate and timber roofs. Top row monastic infirmary, abbey crystal workshop, crenellated wall and gate; bottom row monastery market, medieval forge, fortified abbey citadel. Equal cells, no Victorian industry, labels or ground tiles.',
    'elines_buildings':'Transparent 3x2 atlas of six complete detailed sandstone desert strategy sprites matching the northern city reference: weathered masonry, timber awnings, crenellated fortifications, terracotta. Top row healer infirmary, crystal workshop, wall and arched gate; bottom row bazaar, medieval forge, sandstone citadel. Equal cells, no cartoon props, labels or ground tiles.',
}


def cell(image,col,row,cols,rows):
    return image.crop((round(col*image.width/cols),round(row*image.height/rows),
                       round((col+1)*image.width/cols),round((row+1)*image.height/rows)))


def sprite(image,path):
    image=image.convert('RGBA')
    assert image.getchannel('A').getextrema()[0]==0,path
    bounds=image.getchannel('A').getbbox()
    assert bounds,path
    image=image.crop(bounds)
    image.thumbnail((640,640),Image.Resampling.LANCZOS)
    result=Image.new('RGBA',(image.width+8,image.height+8))
    result.paste(image,(4,4))
    result.save(path,optimize=True)


def package(sources):
    outputs={key:[] for key in sources}
    def record(key,path):outputs[key].append(path.relative_to(ROOT).as_posix())
    for faction in ('adepts','elines'):
        folder=ROOT/'files/city/interiors'/faction
        for row,path in enumerate(sources[faction+'_town']):
            with Image.open(path) as image:
                target=folder/f'city-{row+1}.jpg'
                image.thumbnail((1536,1024),Image.Resampling.LANCZOS)
                image.convert('RGB').save(target,quality=93,optimize=True)
                record(faction+'_town',target)
        names=('hospital','factory','wall','market','forge','citadel')
        with Image.open(sources[faction+'_buildings']) as image:
            for i,name in enumerate(names):
                target=folder/(name+'.png');sprite(cell(image,i%3,i//3,3,2),target)
                record(faction+'_buildings',target)
        mirror=ROOT/'files/otherworld/themes'/faction
        for group in ('cities','map'):
            key=faction+'_mirror_'+group;target=mirror/(group+'.png')
            with Image.open(sources[key]) as image:image.save(target,optimize=True)
            record(key,target)
        with Image.open(mirror/'cities.png') as image:
            entries={}
            for i in range(7):
                left=round((i%3)*image.width/3)+2
                bottom=round((i//3+1)*image.height/3)-2
                right=round((i%3+1)*image.width/3)-2
                top=round((i//3)*image.height/3)+2
                entries[f'city_{i+1}']=[left,image.height-bottom,right-left,bottom-top]
        (mirror/'cities.atlas').write_text(json.dumps({'cities.png':entries},indent=2),encoding='utf-8')
    factions=('north','elves','vampires','adepts','elines','undead','rebels','neutral')
    with Image.open(sources['citadel_atlas']) as image:
        for i,faction in enumerate(factions):
            # Use the matching architecture from the six-building sheets for these factions.
            if faction not in ('adepts','elines'):
                target=ROOT/'files/city/interiors'/faction/'citadel.png'
                sprite(cell(image,i%4,i//4,4,2),target);record('citadel_atlas',target)
    for faction,filename in (('adepts','adepts'),('elines','poly')):
        target=ROOT/'files/buildings'/(filename+'.png')
        with Image.open(ROOT/'files/city/interiors'/faction/'citadel.png') as image:
            image.save(target,optimize=True)
    manifest={key:dict(generator='built-in image_gen',prompt=PROMPTS[key],files=paths)
              for key,paths in outputs.items()}
    prompts=ROOT/'.release/city-redesign-final-prompts.json'
    if prompts.is_file():
        for key,prompt in json.loads(prompts.read_text(encoding='utf-8')):
            if key in manifest:manifest[key]['prompt']=prompt
            else:
                group=key.rsplit('_',1)[0]
                if group in manifest:manifest[group].setdefault('variant_prompts',[]).append(prompt)
    manifest['style_reference']=dict(file='files/city/interiors/north/city-1.jpg',
        role='Painterly architectural detail, camera and terraced construction-ground composition')
    (ROOT/'assets/city-redesign-prompts.json').write_text(
        json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    print('Packaged',sum(map(len,outputs.values())),'city images and two city atlases')


if __name__=='__main__':
    import sys
    package(json.loads(Path(sys.argv[1]).read_text(encoding='utf-8')))
