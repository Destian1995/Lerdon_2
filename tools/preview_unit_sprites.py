"""Build an offline sprite-review page and a small animated contact sheet."""
import json
from pathlib import Path
from PIL import Image,ImageDraw

ROOT=Path(__file__).resolve().parents[1]
ASSETS=ROOT/'files/army/animated'
OUTPUT=ROOT/'assets/animated-units'


def build():
    OUTPUT.mkdir(parents=True,exist_ok=True)
    registry=json.loads((ASSETS/'index.json').read_text(encoding='utf-8'))
    clips={}
    for key,relative in registry['characters'].items():
        data=json.loads((ASSETS/relative).read_text(encoding='utf-8'))
        data['url']='../../files/army/animated/'+str(Path(relative).with_suffix('.png')).replace('\\','/')
        clips[key]=data
    page='''<!doctype html><html lang="ru"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Просмотр анимаций отрядов</title><style>
body{margin:0;padding:20px;background:#101923;color:#eedfbf;font:16px system-ui}main{max-width:1000px;margin:auto}
select,button{min-height:44px;font:inherit;padding:8px;background:#202f3d;color:inherit;border:1px solid #8e7545;border-radius:6px}
.controls{display:flex;gap:8px;flex-wrap:wrap;margin:12px 0}canvas{width:100%;height:auto;background:#182632;border:1px solid #8e7545;border-radius:8px}
p{color:#aabac6}#status{min-height:24px}</style><main><h1>Анимации отрядов</h1>
<p>Ожидание, движение, атака, получение урона и гибель. Это просмотр ассетов, боевые характеристики не рассчитываются.</p>
<div class="controls"><select id="unit" aria-label="Персонаж"></select><select id="action" aria-label="Действие">
<option value="idle">Ожидание</option><option value="walk">Движение</option><option value="attack">Атака</option><option value="hit">Получение урона</option><option value="death">Гибель</option></select>
<button id="restart">Повторить</button><button id="flip">Развернуть</button><button id="back">Сменить фон</button></div>
<canvas id="view" width="900" height="650"></canvas><p id="status"></p></main><script>
const clips=SPRITE_DATA,unit=document.getElementById('unit'),action=document.getElementById('action'),
canvas=document.getElementById('view'),ctx=canvas.getContext('2d'),status=document.getElementById('status');
for(const key of Object.keys(clips)){const o=document.createElement('option');o.value=key;o.textContent=key;unit.append(o)}
unit.value=clips['north-hunter']?'north-hunter':Object.keys(clips)[0];let image=new Image(),start=performance.now(),facing=1,light=false;
function load(){status.textContent='Загрузка…';image=new Image();image.onload=()=>{start=performance.now()};image.onerror=()=>{status.textContent='Не удалось загрузить '+image.src};image.src=clips[unit.value].url}
unit.onchange=load;action.onchange=()=>start=performance.now();document.getElementById('restart').onclick=()=>start=performance.now();
document.getElementById('flip').onclick=()=>facing=-facing;document.getElementById('back').onclick=()=>light=!light;
function draw(now){ctx.fillStyle=light?'#d4c4a5':'#182632';ctx.fillRect(0,0,900,650);ctx.strokeStyle='#8e7545';ctx.beginPath();ctx.moveTo(50,550);ctx.lineTo(850,550);ctx.stroke();
const data=clips[unit.value],clip=data.animations[action.value],phase=Math.floor((now-start)/1000*clip.fps),index=clip.loop?phase%clip.frames.length:Math.min(phase,clip.frames.length-1),f=clip.frames[Math.max(0,index)],r=f.rect,scale=2;
if(image.complete&&image.naturalWidth){ctx.save();ctx.translate(450,550);ctx.scale(facing,1);ctx.drawImage(image,r[0],r[1],r[2],r[3],-r[2]*data.ground_anchor[0]*scale+f.offset[0]*scale,-r[3]*(1-data.ground_anchor[1])*scale-f.offset[1]*scale,r[2]*scale,r[3]*scale);ctx.restore();status.textContent=unit.value+' · '+action.options[action.selectedIndex].text+' · '+(index+1)+'/'+clip.frames.length+' · '+clip.fps+' кадр/с'}requestAnimationFrame(draw)}load();requestAnimationFrame(draw);
</script></html>'''
    (OUTPUT/'preview.html').write_text(page.replace('SPRITE_DATA',json.dumps(clips,ensure_ascii=False).replace('<','\\u003c')),encoding='utf-8')
    keys=['north-hunter','adepts/paladin','elines/blood-mage','elves/archer','vampires/death-herald','undead/banshee','monsters/monster_3','monsters/monster_6_5']
    images={key:Image.open((ASSETS/registry['characters'][key]).with_suffix('.png')).convert('RGBA') for key in keys}
    frames=[];durations=[]
    for state in ('idle','walk','attack','hit','death'):
        for step in range(12):
            frame=Image.new('RGB',(960,530),'#14202c');draw=ImageDraw.Draw(frame)
            for i,key in enumerate(keys):
                meta=clips[key];clip=meta['animations'][state];idx=step%6 if clip['loop'] else min(step,5)
                data=clip['frames'][idx];l,t,w,h=data['rect'];sprite=images[key].crop((l,t,l+w,t+h))
                factor=220/w;sprite=sprite.resize((220,round(h*factor)),Image.Resampling.LANCZOS)
                x=i%4*240;y=i//4*265;baseline=y+225
                top=round(baseline-h*(1-meta['ground_anchor'][1])*factor-data['offset'][1]*factor)
                frame.paste(sprite,(x+10,top),sprite);draw.line((x+10,baseline,x+230,baseline),fill='#6e623e')
                draw.text((x+10,y+235),key,fill='#ecdcad')
            draw.text((10,510),state.upper(),fill='#ecdcad');frames.append(frame);durations.append(120 if step<11 else 550)
    frames[0].save(OUTPUT/'sprite-collection-preview.gif',save_all=True,append_images=frames[1:],duration=durations,loop=0,disposal=2,optimize=False)
    print('Previewed',len(clips),'characters')


if __name__=='__main__':build()
