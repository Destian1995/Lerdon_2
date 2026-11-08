"""Blend the two user-supplied ChiFang recordings into a looping battle track.

Usage: python tools/prepare_chifang_battle_mix.py --sources path/to/recordings
Authoring only: ffmpeg and numpy. Original recordings are never modified.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import wave

import numpy as np

ROOT=Path(__file__).resolve().parents[1]
RATE=22050
SOURCES=('3_1_ChiFang_Town_Medium.Ogg.oga',
         '3_2_ChiFang_Chan_Palace_Medium.Ogg.oga')


def decode(path):
    raw=subprocess.run(['ffmpeg','-v','error','-i',str(path),'-ac','1','-ar',str(RATE),
        '-f','s16le','pipe:1'],capture_output=True,check=True).stdout
    samples=np.frombuffer(raw,dtype='<i2').astype(np.float64)/32768
    samples-=samples.mean()
    rms=np.sqrt(np.mean(samples**2))
    return samples*(.105/max(float(rms),1e-8))


def crossfade(left,right,length):
    phase=np.linspace(0,np.pi/2,length)
    return left*np.cos(phase)+right*np.sin(phase)


def mix(first,second,overlap):
    passage=crossfade(first[-overlap:],second[:overlap],overlap)
    linear=np.concatenate((first[:-overlap],passage,second[overlap:]))
    # Fold the final transition into the first passage, maintaining a cyclic order.
    seam=crossfade(linear[-overlap:],linear[:overlap],overlap)
    loop=np.concatenate((linear[overlap:-overlap],seam))
    loop*=min(.105/max(float(np.sqrt(np.mean(loop**2))),1e-8),
              .82/max(float(np.max(np.abs(loop))),1e-8))
    edge=round(RATE*.012)
    loop[:edge]*=np.linspace(0,1,edge)
    loop[-edge:]*=np.linspace(1,0,edge)
    return np.round(loop*32767).astype('<i2')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sources',type=Path,required=True)
    args=parser.parse_args()
    paths=[args.sources/name for name in SOURCES]
    overlap=6
    samples=mix(*(decode(path) for path in paths),round(RATE*overlap))
    target=ROOT/'files/music/battle_chifang_mix.wav'
    with wave.open(str(target),'wb') as clip:
        clip.setnchannels(1);clip.setsampwidth(2);clip.setframerate(RATE)
        clip.writeframes(samples.tobytes())
    metadata=dict(version=1,title='ChiFang — боевая смесь',file=target.name,
        scene='battle',seconds=len(samples)/RATE,transition_seconds=overlap,
        sample_rate=RATE,channels=1,
        rms=round(float(np.sqrt(np.mean((samples.astype(float)/32768)**2))),5),
        peak=round(float(np.max(np.abs(samples.astype(float)))/32768),5),
        sha256=hashlib.sha256(target.read_bytes()).hexdigest(),
        sources=[dict(file=path.name,sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                      provenance='User supplied recording; license not specified') for path in paths])
    target.with_suffix('.json').write_text(json.dumps(metadata,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(f'Prepared {target.name}: {metadata["seconds"]:.2f} seconds; peak {metadata["peak"]}.')


if __name__=='__main__':main()
