"""Sample the campaign's reviewed terrain mask around the actual battle city."""
import ast
from pathlib import Path
import sqlite3
from collections import Counter

BIOMES={'Север':'snow','Элины':'desert','Эльфы':'forest','Адепты':'forest','Вампиры':'corruption','Нежить':'corruption'}


def remember_map(conn,path):
    conn.execute('CREATE TABLE IF NOT EXISTS campaign_map_context(id INTEGER PRIMARY KEY,image_path TEXT NOT NULL)')
    conn.execute('INSERT OR REPLACE INTO campaign_map_context VALUES(1,?)',(str(path).replace('\\','/'),))


def local_field(terrain,x,y):
    from map_terrain import FOREST,MOUNTAIN,SNOW,SWAMP,WATER,DESERT,CORRUPTION
    kinds={FOREST:'forest',MOUNTAIN:'hill',SNOW:'snow',SWAMP:'swamp',WATER:'water',DESERT:'sand',CORRUPTION:'blight'}
    field={};counts=Counter()
    for ix in range(10):
        for iy in range(10):
            kind=terrain.kind_at(x+(ix-4.5)*12,y+(iy-4.5)*12)
            counts[kind]+=1
            tile=kinds.get(kind,'plain')
            if kind==MOUNTAIN and (ix*7+iy*3)%5==0:tile='rock'
            field[ix,iy]=tile
    for iy in (3,6):
        for ix in range(10):field[ix,iy]='bridge' if field[ix,iy]=='water' else 'road'
    for ix in (0,1,8,9):
        for iy in range(10):field[ix,iy]='snow' if field[ix,iy]=='snow' else 'sand' if field[ix,iy]=='sand' else 'plain'
    biome='plains'
    options={FOREST:'forest',MOUNTAIN:'highland',SNOW:'snow',SWAMP:'swamp',DESERT:'desert',CORRUPTION:'corruption'}
    dominant=max(options,key=lambda k:counts[k])
    if counts[dominant]>=18:biome=options[dominant]
    elif counts[WATER]>=8:biome='coast'
    return biome,field


def context(conn,city,faction):
    from utils.city_terrain import city_terrain
    relief=city_terrain(conn,city)
    fallback='highland' if relief.landform=='highland' else 'coast' if relief.waterside else BIOMES.get(faction,'plains')
    try:
        row=conn.execute('SELECT image_path FROM campaign_map_context WHERE id=1').fetchone()
        town=conn.execute('SELECT coordinates FROM cities WHERE name=?',(city,)).fetchone()
        if row and town:
            from map_terrain import load_terrain
            path=Path(row[0])
            if not path.is_absolute():path=Path(__file__).resolve().parent/path
            terrain=load_terrain(path)
            if terrain:
                x,y=ast.literal_eval(town[0])
                biome,field=local_field(terrain,x+38.5,y+24)
                return dict(biome=biome,terrain=field)
    except (sqlite3.OperationalError,OSError,ValueError,TypeError,SyntaxError):pass
    return dict(biome=fallback)
