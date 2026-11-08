"""Prepare the user's coin recording for the game's SDL2 mixer.

Requires ffmpeg only when preparing assets; no additional runtime dependency.
The original recording is preserved alongside the runtime coins.wav.
"""
from array import array
import sys
import wave

from prepare_result_audio import decode, RATE, TARGET


def main():
    samples=decode(TARGET/'coins-pour-out-2.wav')
    peak=max(abs(sample) for sample in samples) or 1
    frames=array('h',(round(sample/peak*.58*32767*min(
        1,index/(RATE*.005),(len(samples)-1-index)/(RATE*.012)))
        for index,sample in enumerate(samples)))
    if sys.byteorder!='little':frames.byteswap()
    with wave.open(str(TARGET/'coins.wav'),'wb') as clip:
        clip.setnchannels(1);clip.setsampwidth(2);clip.setframerate(RATE)
        clip.writeframes(frames.tobytes())
    print('Prepared coins.wav from coins-pour-out-2.wav (mono, PCM16, 22050 Hz).')


if __name__=='__main__':main()
