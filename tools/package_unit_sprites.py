"""Package approved AI-drawn RGBA sheets; never modifies the drawn frames.

Run with one or more prompt manifests containing a ``sprites`` list. Atlas
rectangles and foot offsets are metadata so the original transparent artwork
stays intact. Pillow, numpy and scipy are needed only for this authoring command.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
from PIL import Image

ROOT=Path(__file__).resolve().parents[1]
DEST=ROOT/'files/army/animated'
STATES=(('idle',6,True),('walk',10,True),('attack',12,False),('hit',10,False),('death',9,False))


def package(item):
    target=(DEST/(item['id']+'.png')).resolve()
    if not target.is_relative_to(DEST.resolve()):raise ValueError('Sprite path escapes asset folder')
    source=Path(item['source'])
    with Image.open(source) as image:
        if image.mode!='RGBA':raise ValueError(f'{item["id"]}: a transparent RGBA sheet is required')
        width,height=image.size
        if width%6 or height%5 or width//6!=height//5:
            raise ValueError(f'{item["id"]}: expected six by five square cells, got {image.size}')
        cell=width//6;animations={}
        for row,(state,fps,loop) in enumerate(STATES):
            frames=[]
            for col in range(6):
                rect=(col*cell,row*cell,(col+1)*cell,(row+1)*cell)
                alpha=image.crop(rect).getchannel('A')
                bbox=alpha.point(lambda value:255 if value>48 else 0).getbbox()
                if bbox is None:raise ValueError(f'{item["id"]}: empty {state} frame {col}')
                frames.append(dict(rect=[col*cell,row*cell,cell,cell],
                    offset=[0,round(bbox[3]-cell*.9)]))
            animations[state]=dict(fps=fps,loop=loop,hold_last=not loop,frames=frames)
    target.parent.mkdir(parents=True,exist_ok=True)
    if source.resolve()!=target:shutil.copyfile(source,target)
    data=dict(version=1,image=target.name,character=item['id'],reference=item['reference'],
        facing='right',grid=[6,5],frame_size=[cell,cell],rect_origin='top-left',
        offset_origin='bottom-left',ground_anchor=[.5,.1],animations=animations,
        sha256=hashlib.sha256(target.read_bytes()).hexdigest())
    if __package__:
        from .stabilize_unit_idle import stabilize
    else:
        from stabilize_unit_idle import stabilize
    with Image.open(target) as image:
        stabilize(data,image)
    target.with_suffix('.json').write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    return item['id']


def index():
    characters={};references={}
    for path in sorted(DEST.rglob('*.json')):
        if path.name=='index.json':continue
        data=json.loads(path.read_text(encoding='utf-8'))
        characters[data['character']]=path.relative_to(DEST).as_posix()
        references[data['reference']]=data['character']
    (DEST/'index.json').write_text(json.dumps(dict(version=1,characters=characters,references=references),
        ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    return len(characters)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('manifests',nargs='+')
    args=parser.parse_args()
    for name in args.manifests:
        manifest=json.loads(Path(name).read_text(encoding='utf-8'))
        for item in manifest['sprites']:print('Packaged',package(item))
    print('Indexed',index(),'characters')
