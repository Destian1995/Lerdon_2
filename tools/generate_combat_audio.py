"""Reproducible original synthesized effects; PCM WAV, no external dependencies.

Run from the project root: python tools/generate_combat_audio.py
No samples from third-party recordings are used by this synthesizer.
Recorded victory/defeat voices are maintained by prepare_result_audio.py.
"""
import math
from pathlib import Path
import random
import struct
import wave

RATE = 22050
DURATIONS = dict(click=.08, step=.18, rifle=.48, bow=.30, sword=.38, hit=.22,
                 throw=.48, explosion=1.35, magic=.85, frost=.95, heal=.85,
                 monster=.85, build=.85)


def synth(name, duration):
    rng = random.Random('lerdon-audio-v1:'+name)
    result = []
    low = 0.
    for i in range(round(RATE*duration)):
        t=i/RATE; u=t/duration
        noise=rng.uniform(-1,1); low+=.08*(noise-low)
        sine=lambda frequency: math.sin(math.tau*frequency*t)
        decay=lambda speed: math.exp(-speed*t)
        if name=='click': value=(sine(950)*.25+noise*.25)*decay(65)
        elif name=='step': value=(low*3+sine(95)*.3)*decay(27)
        elif name=='rifle':
            value=noise*decay(75)*1.6+low*4*decay(11)+sine(72)*.4*decay(17)
            if .075<t<.13:value+=noise*.13*math.exp(-45*(t-.075))
        elif name=='bow': value=noise*.25*decay(12)+sine(220-120*u)*.5*decay(18)
        elif name=='sword': value=noise*.4*math.sin(math.pi*u)**2+sine(1850)*.2*decay(13)+sine(2470)*.12*decay(17)
        elif name=='hit': value=low*5*decay(25)+noise*.25*decay(65)+sine(130)*.4*decay(25)
        elif name=='throw': value=noise*.28*math.sin(math.pi*u)**2+sine(500-270*u)*.08
        elif name=='explosion': value=low*6*decay(3.4)+noise*.7*decay(14)+sine(48)*.6*decay(5)
        elif name=='magic': value=(sine(360+550*u)+sine(540+750*u))*.25*math.sin(math.pi*u)+noise*.08
        elif name=='frost': value=noise*.3*math.sin(math.pi*u)+sum(sine(f)*.06 for f in (1320,1970,2420))*decay(3)
        elif name=='heal': value=sum(sine(f)*.17 for f in (523.25,659.25,783.99))*math.sin(math.pi*u)**2
        elif name=='monster': value=(sine(68+9*math.sin(t*13))*.5+low*2)*math.sin(math.pi*u)**.5
        elif name=='build':
            value=0
            for start in (0,.21,.43):
                age=t-start
                if age>=0:
                    value+=(noise*.55*math.exp(-65*age)+low*3*math.exp(-24*age)
                            +math.sin(math.tau*780*age)*.18*math.exp(-17*age))
        # Smooth both ends to prevent discontinuity clicks, retain headroom.
        value*=min(1,t/.003,(duration-t)/.025)
        result.append(value)
    peak=max(abs(v) for v in result) or 1
    return b''.join(struct.pack('<h',round(v/peak*.78*32767)) for v in result)


def main():
    target=Path(__file__).resolve().parents[1]/'files/sounds/effects'
    target.mkdir(parents=True,exist_ok=True)
    for name,duration in DURATIONS.items():
        with wave.open(str(target/f'{name}.wav'),'wb') as wav:
            wav.setnchannels(1);wav.setsampwidth(2);wav.setframerate(RATE)
            wav.writeframes(synth(name,duration))
    print(f'Created {len(DURATIONS)} original PCM sound effects.')


if __name__=='__main__':main()
