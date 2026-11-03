"""Write native Kivy texture-region metadata; generated paintings stay intact."""
import json
from pathlib import Path
from PIL import Image

GROUPS={'cities':(3,3,['city_'+str(i) for i in range(1,8)]),
        'units':(3,2,['sentinel','archer','rider','weaver','golem','boss']),
        'artifacts':(3,2,['blade','crown','boots','armor','ring','relic'])}


def build():
    root=Path('files/otherworld/themes')
    for faction in ('north','elves','vampires','adepts','elines'):
        for group,(cols,rows,keys) in GROUPS.items():
            source=root/faction/(group+'.png')
            with Image.open(source) as im:width,height=im.size
            entries={}
            for i,key in enumerate(keys):
                col,row=i%cols,i//cols
                left=round(col*width/cols)+2;right=round((col+1)*width/cols)-2
                top=round(row*height/rows)+2;bottom=round((row+1)*height/rows)-2
                entries[key]=[left,height-bottom,right-left,bottom-top]
            source.with_suffix('.atlas').write_text(json.dumps({source.name:entries},indent=2),encoding='utf-8')
    print('15 Kivy atlases created; source PNGs unchanged')


if __name__=='__main__':build()
