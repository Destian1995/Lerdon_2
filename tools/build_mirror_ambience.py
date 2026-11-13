"""Offline placement metadata only: inspect paintings, never modify images."""
import hashlib
import json
import math
from pathlib import Path
from PIL import Image

ROOT=Path(__file__).resolve().parents[1]/'files/otherworld/themes'
WINDOWS={
    'north':((.01,.23,.99,.97),),
    'elves':((.02,.22,.98,.98),),
    'adepts':((.38,.09,.91,.99),),
    'elines':((.01,.31,.13,.40),(.45,.19,.55,.26),(.84,.70,.94,.78)),
    'vampires':((.02,.57,.60,.96),),
}
FLOW={'north':(.95,-.22),'elves':(.10,-1),'adepts':(.35,-1),
      'elines':(.8,-.1),'vampires':(.65,-.3)}
LEAVES={
    'elves':((60,730),(260,755),(435,700),(650,755),(950,735),(1120,650),
             (90,520),(1050,510),(550,540),(400,400),(1130,350),(180,210),
             (590,180),(1100,150),(380,70),(760,80)),
    'adepts':((40,740),(240,740),(450,730),(800,700),(1100,740),(60,570),
              (350,620),(1060,520),(130,430),(650,420),(1100,340),(280,260),
              (800,240),(80,100),(540,80),(1070,70)),
}


def water_pixel(key,rgb):
    r,g,b=rgb
    if key=='elines':return g>r*1.10 and b>r*.75 and b>g*.62
    if key=='vampires':return b>r*1.10 and g>=r*.91 and 35<max(rgb)<145
    if key=='north':return b>r*1.22 and g>r*1.05 and b>g*.85 and 40<max(rgb)<225
    if key=='elves':return g>r*1.25 and b>r*1.25 and b>g*.68 and g>80
    return b>r*1.08 and g>r*1.05 and max(rgb)<235


def build(key):
    path=ROOT/key/'map.png'
    with Image.open(path) as source:
        image=source.convert('RGB')
    def wet(x,y):
        u,v=x/1200,1-y/800
        if not any(x0<u<x1 and y0<v<y1 for x0,y0,x1,y1 in WINDOWS[key]):return False
        return water_pixel(key,image.getpixel((min(image.width-1,int(u*image.width)),
                                               min(image.height-1,int(v*image.height)))))
    dx,dy=FLOW[key];length=math.hypot(dx,dy);dx=round(dx/length,4);dy=round(dy/length,4)
    travel=6 if key=='elines' else (10 if key in ('adepts','vampires') else 18)
    half_width=2 if key=='elines' else 3
    candidates=[]
    steps=math.ceil(travel*3)
    for y in range(24,780,6):
        for x in range(24,1180,6):
            if wet(x,y) and all(wet(x+dx*along-dy*across,y+dy*along+dx*across)
                   for along in ((k/steps-.5)*travel for k in range(steps+1))
                   for across in (-half_width,0,half_width)):
                candidates.append((x,y))
    # Spread glints over real water instead of clustering at the first river.
    chosen=[]
    while candidates and len(chosen)<28:
        point=max(candidates,key=lambda p:min((p[0]-q[0])**2+(p[1]-q[1])**2 for q in chosen)) if chosen else candidates[len(candidates)//2]
        chosen.append(point);candidates.remove(point)
    data=dict(version=1,image_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
              world_size=[1200,800],water=[dict(x=x,y=y,dx=round(dx,4),dy=round(dy,4),travel=travel,half_width=half_width)
                                          for x,y in chosen],leaves=LEAVES.get(key,()))
    (ROOT/key/'ambience.json').write_text(json.dumps(data,indent=2)+'\n',encoding='utf-8')
    print(key,len(chosen),'water patches;',len(data['leaves']),'tree anchors')


if __name__=='__main__':
    for key in WINDOWS:build(key)
