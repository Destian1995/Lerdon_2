"""Author the reviewed Mirror Realm land/water mask; never alter its painting."""
import hashlib
import json
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from PIL import Image,ImageDraw
from map_terrain import LAND,WATER,FOREST,MOUNTAIN,VOID,TERRAIN_NAMES
from otherworld_content import BACKGROUND,CITY_POSITIONS

LAND_OUTLINE=((.03,0),(.98,0),(.99,.08),(.98,.17),(.99,.26),(.98,.37),(.99,.49),
    (.98,.60),(.95,.69),(.90,.75),(.86,.81),(.77,.86),(.72,.84),(.63,.90),
    (.58,.88),(.53,.90),(.45,.89),(.40,.92),(.35,.90),(.28,.96),(.20,.94),
    (.16,.88),(.13,.86),(.08,.79),(.07,.73),(.04,.67),(.035,.56),(.045,.47),
    (.03,.40),(.03,.30),(.05,.25),(.015,.20),(.02,.13),(.01,.06))
LAKE=((.095,.09),(.17,.07),(.23,.09),(.215,.16),(.22,.20),(.18,.22),
      (.14,.20),(.08,.18),(.115,.15))
MOUNTAINS=((.58,0),(1,0),(.96,.38),(.80,.35),(.68,.25),(.60,.18))


def build():
    source=Path(BACKGROUND)
    image=Image.open(source)
    grid=(300,200)
    annotation=Image.new('L',grid,WATER)
    draw=ImageDraw.Draw(annotation)
    polygon=lambda points,kind:draw.polygon([(round(x*grid[0]),round(y*grid[1])) for x,y in points],fill=kind)
    polygon(LAND_OUTLINE,LAND)
    polygon(MOUNTAINS,MOUNTAIN)
    polygon(((.25,.02),(.5,.02),(.47,.11),(.27,.15)),FOREST)
    polygon(((.76,.4),(.96,.4),(.94,.58),(.84,.6)),FOREST)
    polygon(LAKE,WATER)
    values=list(annotation.getdata())
    for y in range(grid[1]):
        for x in range(grid[0]):
            if x<3 or y<3 or x>=grid[0]-3 or y>=grid[1]-3:
                values[y*grid[0]+x]=VOID
    rows=[]
    for y in range(grid[1]):
        runs=[]
        for value in values[y*grid[0]:(y+1)*grid[0]]:
            if runs and runs[-1][0]==value:runs[-1][1]+=1
            else:runs.append([value,1])
        rows.append(runs)
    data=dict(version=1,image=source.name,image_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
              image_size=list(image.size),world_size=[1200,800],grid_size=list(grid),row_origin='top-left',
              classes=TERRAIN_NAMES,authoring=dict(land=LAND_OUTLINE,lake=LAKE,mountains=MOUNTAINS),rows=rows)
    target=Path('files/map/terrain/mirror_realm.json')
    target.write_text(json.dumps(data,separators=(',',':'))+'\n',encoding='utf-8')
    from map_terrain import load_terrain
    terrain=load_terrain(source)
    assert all(terrain.city_allowed(x-38.5,y-30) for x,y in CITY_POSITIONS)
    print('Mirror Realm: seven reviewed city footprints are on land')


if __name__=='__main__':build()
