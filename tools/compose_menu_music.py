"""Render the independent, quiet main-menu score; no faction motifs are used."""
import argparse
import hashlib
import json
from pathlib import Path
import wave
import numpy as np
from tools.compose_faction_music import ROOT,RATE,render,midi_bytes


def compose():
    root=53;scale=[0,2,4,5,7,9,11]
    def pitch(degree,octave=0):return root+scale[degree%7]+12*(degree//7+octave)
    notes=[]
    def note(channel,beat,duration,key,velocity):
        notes.append(dict(channel=channel,beat=beat,duration=duration,note=key,velocity=velocity))
    # An independently written 16-bar piano sentence, with breathing spaces.
    melody=[[(.5,2.5,2)],[(1,1.5,1)],[(0,1.6,4),(2.5,1.,2)],[],
            [(1,2.,5)],[(0,1.5,4),(2,1.5,2)],[(.5,2.5,1)],[(1,2.,0)],
            [(0,2.,3)],[(1,1.5,2)],[(0,1.5,1),(2.5,1.,-1)],[],
            [(.5,2.5,2)],[(1,1.5,4)],[(0,2.5,1)],[(1,2.,0)]]
    harmony=[0,5,3,4,0,2,1,4,3,0,5,1,3,0,1,4]
    for bar in range(32):
        base=bar*4;degree=harmony[bar%16]
        chord=[pitch(degree+i) for i in (0,2,4,6)]
        for key in chord:note(2,base,3.9,key,29 if bar<16 else 32)
        note(3,base,3.65,pitch(degree,-1),34)
        # Slow, irregular harp spacing keeps the menu free of a marching pulse.
        for offset,index in ((.15,0),(1.35,2),(2.8,1)):
            if bar%4==3 and offset>1:continue
            note(1,base+offset,.95,chord[index]+12,34)
        for offset,length,degree_note in melody[bar%16]:
            note(0,base+offset,length,pitch(degree_note,1),43 if bar<16 else 47)
        if bar in (13,29):note(4,base+1,2.3,pitch(4,1),28)
    return dict(id='menu',faction=None,scene='menu',title='Тихие страницы Лэрдона',
                bpm=62,bars=32,seconds=32*4*60/62,
                programs=[0,46,89,42,73,8,0],notes=notes,
                description='Спокойное фортепиано, редкие ноты арфы и тёплый тихий фон. Без ударных.')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--soundfont',type=Path,required=True)
    args=parser.parse_args();score=compose();samples=render(score,args.soundfont)
    path=ROOT/'files/music/menu.wav'
    with wave.open(str(path),'wb') as clip:
        clip.setnchannels(1);clip.setsampwidth(2);clip.setframerate(RATE);clip.writeframes(samples.tobytes())
    scores=ROOT/'assets/music/scores'
    (scores/'menu.json').write_text(json.dumps(score,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    (scores/'menu.mid').write_bytes(midi_bytes(score))
    metadata={key:value for key,value in score.items() if key not in ('notes','programs')}
    metadata.update(file='menu.wav',sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                    rms=float(np.sqrt(np.mean((samples.astype(float)/32768)**2))),
                    peak=float(np.max(np.abs(samples.astype(float)))/32768))
    (ROOT/'files/music/menu.json').write_text(json.dumps(metadata,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('Created standalone calm menu theme:',round(score['seconds'],1),'seconds')


if __name__=='__main__':main()
