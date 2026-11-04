"""Register generated portrait cells without modifying any source painting."""
import json
from pathlib import Path
from PIL import Image


def build():
    for faction in ('north','elves','vampires','adepts','elines'):
        source=Path('files/otherworld/themes')/faction/'women.png'
        with Image.open(source) as im:width,height=im.size
        roles={'bartender':(0,0),'archer':(1,0),'boss':(2,1)}
        if faction in ('north','elves','elines'):roles['weaver']=(0,1)
        entries={}
        for key,(col,row) in roles.items():
            left=round(col*width/3)+2;right=round((col+1)*width/3)-2
            top=round(row*height/2)+2;bottom=round((row+1)*height/2)-2
            entries[key]=[left,height-bottom,right-left,bottom-top]
        source.with_suffix('.atlas').write_text(json.dumps({source.name:entries},indent=2),encoding='utf-8')


if __name__=='__main__':build()
