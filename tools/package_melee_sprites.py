"""Attach approved six-frame melee sheets without altering their pixels.

Each source is a 3x2 sheet of square cells. The existing idle silhouette sets
the physical scale and ground position, preventing an attack from resizing or
teleporting a unit. Pillow is required only when preparing game assets.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil

from PIL import Image

ROOT=Path(__file__).resolve().parents[1]
ASSETS=ROOT/'files/army/animated'


def bounds(image,rect):
    x,y,w,h=rect
    alpha=image.crop((x,y,x+w,y+h)).getchannel('A')
    box=alpha.point(lambda value:255 if value>48 else 0).getbbox()
    if box is None:raise ValueError('Empty animation frame')
    # The lower silhouette defines a root; weapons and extended arms don't move it.
    left,top,right,bottom=box
    band=alpha.crop((0,max(top,bottom-max(3,round((bottom-top)*.14))),w,bottom))
    masses=list(band.resize((w,1),Image.Resampling.BOX).tobytes())
    total=sum(masses)
    center=sum(i*value for i,value in enumerate(masses))/max(1,total)
    return box,center


def attach(data,path,weapon):
    extra=path.with_name(path.stem+'-melee.png')
    with Image.open(path.parent/data['image']) as image:
        idle=data['animations']['idle']['frames'][0]
        box,root=bounds(image,idle['rect'])
        base_w,base_h=data['frame_size']
        target_height=(box[3]-box[1])/base_h
        target_x=root/base_w-data['ground_anchor'][0]-idle['offset'][0]/base_w
        target_y=-data['ground_anchor'][1]-box[3]/base_h+1+idle['offset'][1]/base_h
    with Image.open(extra) as image:
        if image.mode!='RGBA' or image.width%3 or image.height%2 or image.width//3!=image.height//2:
            raise ValueError(f'{extra}: expected transparent 3x2 square cells')
        cell=image.width//3
        first,_=bounds(image,(0,0,cell,cell))
        scale=target_height/((first[3]-first[1])/cell)
        frames=[]
        for index in range(6):
            rect=[index%3*cell,index//3*cell,cell,cell]
            box,root=bounds(image,rect)
            frames.append(dict(rect=rect,offset=[round(root-cell*.5-target_x*cell/scale,3),
                round(box[3]-cell*.9+target_y*cell/scale,3)]))
    data['animations']['melee']=dict(image=extra.name,sha256=hashlib.sha256(extra.read_bytes()).hexdigest(),
        frame_size=[cell,cell],ground_anchor=[.5,.1],scale=round(scale,6),
        weapon=weapon,fps=12,loop=False,hold_last=True,frames=frames)


def package(item):
    registry=json.loads((ASSETS/'index.json').read_text(encoding='utf-8'))
    path=ASSETS/registry['characters'][item['id']]
    target=path.with_name(path.stem+'-melee.png')
    if Path(item['source']).resolve()!=target.resolve():shutil.copyfile(item['source'],target)
    data=json.loads(path.read_text(encoding='utf-8'))
    attach(data,path,item['weapon'])
    path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('Packaged melee:',item['id'])


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('manifest',type=Path)
    args=parser.parse_args()
    for item in json.loads(args.manifest.read_text(encoding='utf-8'))['sprites']:package(item)
