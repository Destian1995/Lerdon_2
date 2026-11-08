"""Register idle drawings without changing pixels in approved sprite sheets.

Authoring dependencies: Pillow, numpy, scipy. Runtime uses only JSON offsets.
Correlating silhouettes with frame zero detects whole-figure translation while
retaining the artist's changes to pose, clothing and breathing.
"""
import json
from pathlib import Path

import numpy as np
from PIL import Image
from scipy.ndimage import gaussian_filter
from scipy.signal import fftconvolve

ROOT=Path(__file__).resolve().parents[1]/'files/army/animated'


def translations(image, frames):
    silhouettes=[]
    for frame in frames:
        x,y,w,h=frame['rect']
        alpha=np.asarray(image.crop((x,y,x+w,y+h)).getchannel('A'),dtype=float)/255
        silhouettes.append(gaussian_filter(alpha,1))
    reference=silhouettes[0]
    height,width=reference.shape
    limit=min(width,height)//4
    shifts=[]
    for silhouette in silhouettes:
        correlation=fftconvolve(silhouette,reference[::-1,::-1],mode='full')
        search=correlation[height-1-limit:height+limit,width-1-limit:width+limit]
        y,x=np.unravel_index(np.argmax(search),search.shape)
        shifts.append((int(x-limit),int(y-limit)))
    return shifts


def stabilize(data, image):
    frames=data['animations']['idle']['frames']
    shifts=translations(image,frames)
    base=frames[0]['offset'][:]
    for frame,(dx,dy) in zip(frames,shifts):
        frame['offset']=[base[0]+dx,base[1]+dy]
    data['idle_registration']=dict(version=1,reference_frame=0,
        method='silhouette translation relative to first idle frame',shifts=shifts)
    return shifts


def main():
    registry=json.loads((ROOT/'index.json').read_text(encoding='utf-8'))
    records=[]
    for key,relative in registry['characters'].items():
        path=ROOT/relative
        data=json.loads(path.read_text(encoding='utf-8'))
        with Image.open(path.parent/data['image']) as image:
            shifts=stabilize(data,image)
        path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        records.append((max(abs(x) for x,y in shifts),max(abs(y) for x,y in shifts),key))
    print('Registered idle frames for',len(records),'characters; largest source shifts:')
    for x,y,key in sorted(records,reverse=True)[:12]:print(key,x,y)


if __name__=='__main__':main()
