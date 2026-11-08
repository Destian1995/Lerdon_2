"""Mix CC0 human voices into victory cheers and defeat groans.

Requires ffmpeg and the two original downloads in --sources; see SOURCES.json.
Outputs runtime PCM WAV only. No network or extra runtime dependencies.
"""
import argparse
from array import array
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import wave

RATE=22050
ROOT=Path(__file__).resolve().parents[1]
TARGET=ROOT/'files/sounds/effects'


def decode(path):
    raw=subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-i',str(path),
        '-ac','1','-ar',str(RATE),'-f','s16le','pipe:1'],capture_output=True,check=True).stdout
    samples=array('h');samples.frombytes(raw)
    if sys.byteorder!='little':samples.byteswap()
    return [v/32768 for v in samples]


def mix(layers,duration=3.8):
    result=[0.] * round(duration*RATE)
    for source,start,pitch,gain in layers:
        offset=round(start*RATE)
        for i in range(min(len(result)-offset,int((len(source)-1)/pitch))):
            index=i*pitch;left=int(index);fraction=index-left
            sample=source[left]*(1-fraction)+source[left+1]*fraction
            result[offset+i]+=sample*gain
    # A small room tail integrates the voices without a sharp cutoff.
    dry=result[:]
    for delay,gain in ((.071,.16),(.137,.10),(.213,.06)):
        offset=round(delay*RATE)
        for i in range(offset,len(result)):result[i]+=dry[i-offset]*gain
    peak=max(abs(v) for v in result) or 1
    output=array('h',(round(v/peak*.76*32767*min(1,i/(RATE*.01),(len(result)-1-i)/(RATE*.15)))
                      for i,v in enumerate(result)))
    if sys.byteorder!='little':output.byteswap()
    return output.tobytes()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sources',type=Path,required=True)
    args=parser.parse_args()
    metadata=json.loads((TARGET/'SOURCES.json').read_text(encoding='utf-8'))
    for record in metadata['recordings']:
        path=args.sources/record['local_file']
        if hashlib.sha256(path.read_bytes()).hexdigest()!=record['sha256']:
            raise ValueError('Source recording hash mismatch: '+str(path))
    cheers=decode(args.sources/'cheers.ogg')
    groans=decode(args.sources/'groans.wav')
    victory=[(cheers,(i%4)*.27+(i//4)*.07,.82+i*.034,.65) for i in range(12)]
    cuts=[groans[round(a*RATE):round(b*RATE)] for a,b in ((3.95,6.16),(10.08,12.22),(14.44,16.16))]
    defeat=[(clip,start,pitch,1) for clip,start,pitch in zip(cuts,(0,.65,1.35),(.92,1.04,.85))]
    for name,layers in (('victory',victory),('defeat',defeat)):
        with wave.open(str(TARGET/(name+'.wav')),'wb') as output:
            output.setnchannels(1);output.setsampwidth(2);output.setframerate(RATE)
            output.writeframes(mix(layers))
    print('Created victory crowd cheers and defeat groans (3.8 s, PCM WAV).')


if __name__=='__main__':main()
