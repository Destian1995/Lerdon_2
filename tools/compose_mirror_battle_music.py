"""An original battle score inspired by the supplied recordings' broad palette.

No reference audio, melody, stems or sampled passages are loaded by this script.
Only the existing licensed GeneralUser instrument bank renders the written notes.
Authoring: numpy, scipy, tinysoundfont. Runtime: finished mono PCM WAV only.
"""
import argparse
import hashlib
import json
from pathlib import Path
import random
import wave

import numpy as np
from tools.compose_faction_music import ROOT,RATE,render,midi_bytes


def compose():
    rng=random.Random('lerdon-mirror-overture-original-v1')
    bpm=126;bars=72;root=50;scale=(0,2,3,5,7,8,10)
    def pitch(degree,octave=0):return root+scale[degree%7]+12*(degree//7+octave)
    # Two independently written eight-bar sentences, including deliberate rests.
    melody=[
        [(0,.75,4),(1,.5,3),(2,1.5,0)],[(.5,.5,2),(1.25,.5,4),(2.25,1.25,5)],
        [(0,.75,4),(1,.5,2),(2,1.25,1)],[(.25,1.5,0),(2.5,.75,-1)],
        [(0,.5,2),(.75,.5,3),(1.5,.75,4),(2.75,.75,6)],
        [(0,1.25,5),(1.75,.5,4),(2.5,1,2)],[(.5,.75,1),(1.5,.5,2),(2.5,1,0)],[(0,2.5,-1)],
        [(0,1.25,7),(1.75,.5,5),(2.5,1,4)],[(.5,.75,6),(1.5,1.75,5)],
        [(0,.5,4),(.75,.5,5),(1.5,.5,3),(2.5,1,2)],[(.25,2,3),(2.75,.5,1)],
        [(0,.75,4),(1,.75,6),(2,1.5,7)],[(.5,.5,5),(1.25,.5,4),(2,1.5,3)],
        [(0,1,2),(1.5,.5,1),(2.5,1,0)],[(.25,2.5,4)],
    ]
    chords=((50,53,57,60),(46,50,53,57),(53,57,60,64),(48,52,55,60),
            (43,46,50,57),(45,50,52,57),(46,50,53,60),(45,49,52,57))
    progression=(0,1,2,3,4,1,6,7)
    notes=[]
    def note(channel,beat,duration,key,velocity):
        start=max(0,beat+rng.uniform(-.012,.012))
        length=min(duration,bars*4-.01-start)
        if length>0:notes.append(dict(channel=channel,beat=round(start,4),duration=round(length,4),
            note=int(key),velocity=max(1,min(100,round(velocity+rng.uniform(-3,3))))))
    for bar in range(bars):
        base=bar*4;section=0 if bar<8 else 1 if bar<24 else 2 if bar<40 else 3 if bar<48 else 4 if bar<64 else 5
        energy=(.60,.78,.89,.62,1,.67)[section]
        chord=chords[progression[bar%8]]
        if section in (0,5):chord=chords[0 if bar%4<2 else 5]
        for key in chord:note(2,base,3.95,key+12,37*energy)
        note(3,base,3.7,chord[0]-12,53*energy)
        pattern=(0,2,1,3,2,1,3,1)
        for index,degree in enumerate(pattern):
            if section==3 and index%2:continue
            note(1,base+index*.5,.62,chord[degree]+12,49*energy)
        if section in (1,2,4):
            phrase=bar%8+(8 if section==2 else 0)
            for offset,length,degree in melody[phrase]:
                note(0,base+offset,length+.10,pitch(degree,1),67*energy)
                if section==4 and bar%8 in (0,2,4,6):
                    note(4,base+offset+.035,length,pitch(degree,1),34)
        elif section in (0,5) and bar%2==0:
            note(0,base+.5,2.9,pitch((0,4,2,1)[bar//2%4],1),38)
        else:
            for offset,degree in ((.5,4),(2.25,2)):note(5,base+offset,1.3,pitch(degree,1),41)
        if section in (1,2,4):
            for beat,drum,velocity in ((0,41,55),(1.5,43,36),(2,36,48),(3.25,45,32)):
                note(9,base+beat,.15,drum,velocity*energy)
            if bar%8==7:
                for beat,drum in ((3,45),(3.5,43),(3.75,41)):note(9,base+beat,.14,drum,42*energy)
        if section==4 and bar%4==0:
            for i,key in enumerate(chord):note(5,base+i*.12,1.9,key+24,32)
    return dict(id='battle_mirror_overture',title='Знамёна за зеркалом',scene='battle',faction=None,
        bpm=bpm,bars=bars,seconds=bars*4*60/bpm,programs=[41,107,48,42,110,46,0],notes=notes,
        description='Собственная тема: альт и струнные, перебор кото, мягкие низкие барабаны; две мелодические темы и плавная драматургия.',
        original_composition=True,uses_reference_audio=False,
        inspiration='Broad rhythmic energy and plucked-string/orchestral palette of the two user-supplied ChiFang references; no copied notes or audio.')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--soundfont',type=Path,required=True)
    args=parser.parse_args();score=compose();samples=render(score,args.soundfont)
    path=ROOT/'files/music/battle_mirror_overture.wav'
    with wave.open(str(path),'wb') as clip:
        clip.setnchannels(1);clip.setsampwidth(2);clip.setframerate(RATE);clip.writeframes(samples.tobytes())
    folder=ROOT/'assets/music/scores';folder.mkdir(parents=True,exist_ok=True)
    (folder/(score['id']+'.json')).write_text(json.dumps(score,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    (folder/(score['id']+'.mid')).write_bytes(midi_bytes(score))
    metadata={key:value for key,value in score.items() if key not in ('notes','programs')}
    metadata.update(file=path.name,sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
        rms=float(np.sqrt(np.mean((samples.astype(float)/32768)**2))),
        peak=float(np.max(np.abs(samples.astype(float)))/32768),sample_rate=RATE,channels=1)
    path.with_suffix('.json').write_text(json.dumps(metadata,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('Rendered original battle overture:',round(score['seconds'],2),'seconds,',len(score['notes']),'written notes.')


if __name__=='__main__':main()
