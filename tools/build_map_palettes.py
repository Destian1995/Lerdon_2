"""Author compact local foliage palettes; Pillow is never needed at runtime."""
import colorsys
import json
from pathlib import Path
from PIL import Image

from map_terrain import TerrainMap, WATER, VOID, FOREST


def build(path):
    data=json.loads(path.read_text(encoding='utf-8'))
    terrain=TerrainMap(data)
    image=Image.open(Path('files/map/generate')/data['image']).convert('RGB')
    image=image.resize((terrain.width,terrain.height),Image.Resampling.BOX)
    pixels=list(image.getdata())
    width,height=60,40
    cells=[]
    for gy in range(height):
        for gx in range(width):
            cx,cy=int((gx+.5)*terrain.width/width),int((gy+.5)*terrain.height/height)
            leaves,ground=[],[]
            green,warm=0,0
            for y in range(max(0,cy-9),min(terrain.height,cy+10)):
                for x in range(max(0,cx-9),min(terrain.width,cx+10)):
                    index=y*terrain.width+x
                    if terrain.grid[index] in (WATER,VOID):
                        continue
                    rgb=pixels[index]
                    ground.append(rgb)
                    h,s,v=colorsys.rgb_to_hsv(*(c/255 for c in rgb))
                    # Ignore yellow grass and pale snow. Count actual leafy
                    # greens and orange/copper vegetation in nearby groves.
                    is_green=.16<=h<=.46 and s>.25 and .10<v<.80
                    is_warm=.015<=h<=.115 and s>.38 and .18<v<.85
                    if terrain.grid[index]==FOREST and (is_green or is_warm):
                        leaves.append(rgb)
                        green+=is_green
                        warm+=is_warm
            samples=leaves or ground or [(110,120,70)]
            rgb=[round(sum(p[i] for p in samples)/len(samples)) for i in range(3)]
            cells.append(rgb+[int(warm>green and warm>=4)])
    data['foliage_palette']={'version':1,'grid_size':[width,height],
                             'row_origin':'top-left','cells':cells}
    path.write_text(json.dumps(data,ensure_ascii=False,separators=(',',':'))+'\n',encoding='utf-8')
    print(path.stem,'warm cells',sum(c[3] for c in cells))


if __name__=='__main__':
    for path in sorted(Path('files/map/terrain').glob('map_*.json')):
        build(path)
