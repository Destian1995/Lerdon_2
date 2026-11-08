"""Original, editable faction scores rendered offline with GeneralUser GS.

Requires numpy, scipy and tinysoundfont only on the authoring machine.
Usage: python tools/compose_faction_music.py --soundfont path/to/GeneralUser-GS.sf2
No reference recordings are sampled or bundled. The game plays finished WAVs.
"""
import argparse
import hashlib
import json
from pathlib import Path
import random
import struct
import wave

import numpy as np
from scipy import signal
import tinysoundfont

ROOT=Path(__file__).resolve().parents[1]
RATE=22050
# Programs are zero-based General MIDI. Each score has its own written motif.
PALETTES={
    'north':dict(faction='Север',title='Северные перевалы',battle_title='Сталь и метель',root=50,
        scale=[0,2,3,5,7,9,10],tempo=[76,124],lead=[73,60],arp=46,pad=48,bass=42,
        harmony=[0,5,3,4,0,2,3,4],motif=[0,2,4,3,2,0,1,2,4,5,4,2,3,1,0,-1],
        colors='Холодные флейты, арфа, валторны и низкие струнные.'),
    'elines':dict(faction='Элины',title='Караван у янтарных стен',battle_title='Песчаные знамёна',root=48,
        scale=[0,1,4,5,7,8,10],tempo=[84,132],lead=[68,68],arp=15,pad=48,bass=43,
        harmony=[0,3,0,5,3,1,4,0],motif=[4,3,2,1,0,2,3,4,5,4,3,2,1,2,1,0],
        colors='Гобой, цимбалы, восточный лад и ручная перкуссия.'),
    'elves':dict(faction='Эльфы',title='Свет под кронами',battle_title='Стрелы рассвета',root=55,
        scale=[0,2,4,6,7,9,11],tempo=[72,120],lead=[73,75],arp=46,pad=49,bass=42,
        harmony=[0,1,4,2,0,5,1,4],motif=[0,2,4,6,5,4,2,3,4,6,7,5,4,2,1,0],
        colors='Арфа, флейты и воздушные струнные в светлом лидийском ладу.'),
    'adepts':dict(faction='Адепты',title='Колокола рыжего леса',battle_title='Клятва аббатства',root=57,
        scale=[0,2,3,5,7,8,10],tempo=[70,116],lead=[68,60],arp=46,pad=52,bass=42,
        harmony=[0,3,5,4,0,2,3,4],motif=[0,1,2,4,3,2,1,0,2,3,4,5,4,2,1,0],
        colors='Сдержанный хор, гобой, колокольные акценты и хоральная гармония.'),
    'vampires':dict(faction='Вампиры',title='Полночь алого двора',battle_title='Вальс кровавой луны',root=48,
        scale=[0,2,3,5,7,8,11],tempo=[100,148],lead=[40,40],arp=6,pad=45,bass=43,
        harmony=[0,5,3,4,0,2,5,4],motif=[0,2,4,5,4,3,2,1,4,6,7,5,4,2,1,0],
        colors='Подвижная скрипка, пульсирующий клавесин, пиццикато и напряжённый гармонический минор.'),
    'undead':dict(faction='Нежить',title='Туман над некрополем',battle_title='Марш безымянных',root=42,
        scale=[0,1,3,5,7,8,10],tempo=[64,112],lead=[69,61],arp=8,pad=53,bass=43,
        harmony=[0,1,3,0,5,3,1,0],motif=[0,1,0,-1,2,1,0,-2,3,2,1,0,-1,1,0,-1],
        colors='Низкий хор, английский рожок, контрабасы и гулкие барабаны.'),
    'rebels':dict(faction='Мятежники',title='Огни вольного лагеря',battle_title='За свободные города',root=57,
        scale=[0,2,3,5,7,8,10],tempo=[88,140],lead=[71,56],arp=24,pad=45,bass=42,
        harmony=[0,5,2,6,0,3,5,4],motif=[0,2,3,4,2,1,0,2,4,5,4,3,2,1,2,0],
        colors='Кларнет, акустические струны, походные барабаны и медные духовые.'),
}


def pitch(palette,degree,octave=0):
    return palette['root']+palette['scale'][degree%7]+12*(degree//7+octave)


def compose(key,scene):
    p=PALETTES[key];battle=scene=='battle';bpm=p['tempo'][battle]
    bars=48 if battle else 32
    rng=random.Random('lerdon-score-v1:'+key+':'+scene)
    # lead, arpeggio, ensemble, cello/bass, response, extra colour, percussion
    programs=[p['lead'][battle],p['arp'],48 if battle else p['pad'],p['bass'],
              60 if key not in ('elines','elves','undead') else 68 if key=='elines' else 73 if key=='elves' else 19,
              19 if key in ('adepts','vampires','undead') else 46,0]
    notes=[]
    def note(channel,beat,duration,key_note,velocity):
        # Human timing stays inside the bar; phrase rests are written explicitly.
        offset=rng.uniform(-.012,.012) if channel!=9 else rng.uniform(-.005,.005)
        start=max(0,beat+offset)
        end=min(bars*4-.01,start+duration)
        if end>start:
            notes.append(dict(channel=channel,beat=round(start,4),duration=round(end-start,4),
                note=int(max(0,min(127,key_note))),velocity=int(max(1,min(120,velocity+rng.randint(-4,4))))))
    previous=[pitch(p,0),pitch(p,2),pitch(p,4)]
    for bar in range(bars):
        phrase=bar//8;local=bar%8
        # A / A' / B / A'' for exploration; two larger battle developments.
        section=(phrase//2)%3 if battle else (1 if phrase==2 else 0)
        harmony=p['harmony'][(local+(2 if section else 0))%8]
        if bar==bars-1:harmony=4 if key!='undead' else 0
        root=pitch(p,harmony)
        chord=[pitch(p,harmony+i) for i in (0,2,4)]
        # Nearest inversion keeps inner parts singable instead of jumping octaves.
        voicing=[]
        for i,n in enumerate(chord):
            options=[n-12,n,n+12]
            voicing.append(min(options,key=lambda v:abs(v-previous[i])))
        previous=voicing
        base=bar*4
        swell=1 if local<4 else 1.08
        if battle or key=='vampires':
            for beat in (np.arange(0,4,.5) if not battle else (0,1,2,3)):
                for n in voicing:note(2,base+float(beat),.26,n,round((54 if beat%2 else 66)*swell)*(1 if battle else .7))
                note(3,base+beat,.65,root-12,70 if beat%2==0 else 57)
            if phrase in (0,2,4):
                for n in voicing:note(5,base,3.6,n-12,36)
        else:
            for n in voicing:note(2,base,3.8,n,38 if key!='undead' else 44)
            note(3,base,3.6,root-12,46)
        arp_pattern=[0,1,2,1,0,2,1,2] if key!='elines' else [0,2,1,2,0,1,2,1]
        subdivision=.25 if key=='vampires' else .5 if battle or key in ('elves','elines') else 1
        for step in range(int(4/subdivision)):
            if not battle and phrase==0 and local<2 and step%2:continue
            n=chord[arp_pattern[step%8]]+12
            note(1,base+step*subdivision,subdivision*.72,n,48 if not battle else 51)
        # The first two bars leave space to establish the faction's instruments.
        if bar>=2:
            motif=p['motif']
            first=motif[(local*2)%16]
            second=motif[(local*2+1)%16]
            if section:
                first+=2;second+=2
            octave=1 if battle and p['lead'][1] in (56,60,61) else 2
            if key=='undead':octave=2
            if not battle:
                if key=='vampires':
                    for offset,length,degree in ((0,.65,first),(1,.5,first+1),(1.75,.7,second),(3,.8,first-1)):
                        note(0,base+offset,length,pitch(p,degree,octave),64)
                else:
                    note(0,base+.25,1.5,pitch(p,first,octave),64)
                    if local not in (3,7):note(0,base+2.25,1.25,pitch(p,second,octave),59)
            else:
                pattern=[(0,.7,first),(.75,.45,first+1),(1.5,.9,second),(2.75,.45,second-1),(3.25,.6,first)]
                if local in (3,7):pattern=[(0,1.4,second),(2,1.5,0 if local==7 else first)]
                for offset,length,degree in pattern:note(0,base+offset,length,pitch(p,degree,octave),78)
            if local in (3,7) and phrase>0:
                note(4,base+2,1.65,pitch(p,harmony+4,1),56 if battle else 40)
        if key in ('adepts','vampires') and local==0:
            note(5,base,3.75,pitch(p,0,-1),34)
        # Percussion is sparse under exploration, with distinct battle patterns.
        if battle:
            for beat in (0,2):note(9,base+beat,.15,36 if key!='elines' else 64,80)
            for beat in (1,3):note(9,base+beat,.15,38 if key in ('north','rebels') else 41,64)
            for beat in np.arange(0,4,.5):note(9,base+float(beat),.08,42 if key=='rebels' else 54 if key=='elines' else 51,30)
            if local==7:
                for step in range(4):note(9,base+3+step*.25,.12,45-step%3,50+step*6)
            if local==0:note(9,base,.5,49,52)
        elif key in ('elines','rebels'):
            for beat in (0,2.5):note(9,base+beat,.12,64 if key=='elines' else 41,30)
        elif key in ('north','undead') and local%2==0:note(9,base,.3,41,32)
    return dict(id=key+'_'+scene,faction=p['faction'],scene=scene,
        title=p['battle_title'] if battle else p['title'],bpm=bpm,bars=bars,
        seconds=bars*4*60/bpm,programs=programs,notes=notes,description=p['colors'])


def midi_bytes(score):
    def varlen(value):
        out=[value&127];value>>=7
        while value:out.insert(0,128|(value&127));value>>=7
        return bytes(out)
    events=[(0,b'\xff\x51\x03'+int(60e6/score['bpm']).to_bytes(3,'big'))]
    for channel,program in enumerate(score['programs'][:-1]):events.append((0,bytes([0xC0+channel,program])))
    events.append((0,bytes([0xC9,0])))
    for n in score['notes']:
        events.append((round(n['beat']*480),bytes([0x90+n['channel'],n['note'],n['velocity']])))
        events.append((round((n['beat']+n['duration'])*480),bytes([0x80+n['channel'],n['note'],0])))
    data=bytearray();last=0
    for tick,msg in sorted(events,key=lambda e:(e[0],e[1][0]>>4!=8)):
        data.extend(varlen(tick-last));data.extend(msg);last=tick
    data.extend(b'\x00\xff\x2f\x00')
    return b'MThd'+struct.pack('>IHHH',6,0,1,480)+b'MTrk'+struct.pack('>I',len(data))+data


def render(score,font):
    synth=tinysoundfont.Synth(gain=-14,samplerate=RATE)
    sfid=synth.sfload(str(font),max_voices=384)
    for channel,program in enumerate(score['programs'][:-1]):synth.program_select(channel,sfid,0,program)
    synth.program_select(9,sfid,128,0,is_drums=True)
    # Two complete performances: the first supplies release tails at loop start.
    length=round(score['seconds']*RATE);audio=np.zeros((length*2+RATE*2,2),np.float32)
    events=[]
    for cycle in (0,1):
        for n in score['notes']:
            start=round(n['beat']*60/score['bpm']*RATE)+cycle*length
            end=round((n['beat']+n['duration'])*60/score['bpm']*RATE)+cycle*length
            events.extend([(start,1,n),(end,0,n)])
    cursor=0
    for position,on,n in sorted(events,key=lambda e:(e[0],e[1])):
        if position>cursor:
            audio[cursor:position]=np.frombuffer(synth.generate_simple(position-cursor),np.float32).reshape(-1,2)
            cursor=position
        synth.noteon(n['channel'],n['note'],n['velocity']) if on else synth.noteoff(n['channel'],n['note'])
    audio[cursor:]=np.frombuffer(synth.generate_simple(len(audio)-cursor),np.float32).reshape(-1,2)
    synth.sfunload(sfid)
    # Soft hall reflections; filter the wet signal to keep the lead legible.
    wet=np.zeros_like(audio)
    for delay,gain in ((.043,.12),(.079,.10),(.131,.075),(.211,.055),(.337,.035),(.521,.022)):
        offset=round(delay*RATE)
        wet[offset:]+=audio[:-offset]*gain
    wet=signal.sosfilt(signal.butter(2,4500,fs=RATE,output='sos'),wet,axis=0).astype(np.float32)
    audio=(audio+wet)[length:2*length].mean(axis=1)
    audio=signal.sosfilt(signal.butter(2,45,fs=RATE,btype='highpass',output='sos'),audio).astype(np.float32)
    rms=float(np.sqrt(np.mean(audio**2)))
    target=.065 if score['scene']=='menu' else .105 if score['scene']=='battle' else .085
    audio*=target/max(rms,1e-8)
    audio=np.tanh(audio*1.1)/1.1
    peak=float(np.max(np.abs(audio)))
    if peak>.84:audio*=.84/peak
    # Rounded PCM edges complement the player's overlapping musical loop tails.
    edge=round(RATE*.04)
    audio[:edge]*=np.linspace(0,1,edge);audio[-edge:]*=np.linspace(1,0,edge)
    return np.round(audio*32767).astype('<i2')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--soundfont',type=Path,required=True)
    parser.add_argument('--faction',choices=list(PALETTES))
    args=parser.parse_args()
    target=ROOT/'files/music';target.mkdir(exist_ok=True)
    scores=ROOT/'assets/music/scores';scores.mkdir(parents=True,exist_ok=True)
    catalog=[]
    if args.faction and (target/'catalog.json').is_file():
        catalog=[t for t in json.loads((target/'catalog.json').read_text(encoding='utf-8'))['tracks']
                 if not t['id'].startswith(args.faction+'_')]
    for key in ([args.faction] if args.faction else PALETTES):
        for scene in ('background','battle'):
            score=compose(key,scene)
            (scores/(score['id']+'.json')).write_text(json.dumps(score,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
            (scores/(score['id']+'.mid')).write_bytes(midi_bytes(score))
            samples=render(score,args.soundfont)
            path=target/(score['id']+'.wav')
            with wave.open(str(path),'wb') as output:
                output.setnchannels(1);output.setsampwidth(2);output.setframerate(RATE);output.writeframes(samples.tobytes())
            entry={k:v for k,v in score.items() if k not in ('notes','programs')}
            entry.update(file=path.name,sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                rms=round(float(np.sqrt(np.mean((samples.astype(float)/32768)**2))),5),peak=round(float(np.max(np.abs(samples.astype(float)))/32768),5))
            catalog.append(entry)
            print(entry['id'],round(entry['seconds'],1),'seconds',len(score['notes']),'notes',flush=True)
    order=[key+'_'+scene for key in PALETTES for scene in ('background','battle')]
    catalog.sort(key=lambda entry:order.index(entry['id']))
    (target/'catalog.json').write_text(json.dumps(dict(version=1,sample_rate=RATE,tracks=catalog),ensure_ascii=False,indent=2)+'\n',encoding='utf-8')


if __name__=='__main__':main()
