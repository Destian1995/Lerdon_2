"""Main-thread music envelopes and overlapping loops, with at most two voices."""
import math


class MusicPlayback:
    FADE=.7
    LOOP_FADE=.8

    def __init__(self,load,stop,schedule,now,reserve,on_current=None):
        self.load,self.stop,self.schedule,self.now,self.reserve=load,stop,schedule,now,reserve
        self.on_current=on_current or (lambda sound:None)
        self.voices=[]
        self.current=None
        self.desired=None
        self.volume=0
        self.event=None

    @property
    def playing_count(self):
        return sum(v['sound'].state=='play' for v in self.voices)

    def _fade(self,voice,target,duration):
        if voice['target']==target:return
        voice.update(start_gain=voice['gain'],target=target,elapsed=0.,duration=duration)

    def _remove(self,voice):
        self.stop(voice['sound'],unload=True)
        self.voices.remove(voice)

    def _start(self,path,duration):
        sound=self.load('music:'+path.stem,path)
        if sound is None:return None
        # Rapid A -> B -> C changes retire the oldest tail before opening C.
        while len(self.voices)>=2:
            oldest=next((v for v in self.voices if v is not self.current),self.voices[0])
            self._remove(oldest)
        self.reserve(self.playing_count+1)
        try:
            sound.volume=0
            sound.loop=False  # Loop ourselves before EOF, avoiding Kivy's polling gap.
            sound.play()
            if sound.state!='play':
                self.stop(sound,unload=True)
                return None
        except Exception:
            self.stop(sound,unload=True)
            return None
        voice=dict(sound=sound,path=path,gain=0.,start_gain=0.,target=1.,elapsed=0.,
                   duration=duration,started=self.now())
        self.voices.append(voice)
        self.current=voice
        self.on_current(sound)
        return voice

    def request(self,path,volume,immediate=False):
        self.volume=volume
        self.desired=path
        if immediate:
            self.close()
            return
        if path is None:
            self.current=None;self.on_current(None)
            for voice in self.voices:self._fade(voice,0.,self.FADE)
        elif self.current is None or self.current['path']!=path:
            matching=next((v for v in self.voices if v['path']==path),None)
            new=matching or self._start(path,self.FADE)
            if new:
                self.current=new;self.on_current(new['sound'])
                for voice in self.voices:self._fade(voice,1. if voice is new else 0.,self.FADE)
        for voice in self.voices:voice['sound'].volume=self.volume*voice['gain']
        if self.voices and self.event is None:self.event=self.schedule(self.tick,1/30)

    def tick(self,dt):
        for voice in list(self.voices):
            voice['elapsed']+=max(0,min(dt,.1))
            t=min(1,voice['elapsed']/voice['duration'])
            # Equal-power envelopes avoid a dip halfway between two passages.
            progress=math.sin(t*math.pi/2) if voice['target']>voice['start_gain'] else 1-math.cos(t*math.pi/2)
            voice['gain']=voice['start_gain']+(voice['target']-voice['start_gain'])*progress
            voice['sound'].volume=self.volume*voice['gain']
            if t>=1 and voice['target']==0:self._remove(voice)
        current=self.current
        if current and self.desired==current['path']:
            length=float(getattr(current['sound'],'length',0) or 0)
            remaining=length-(self.now()-current['started'])
            if length>self.LOOP_FADE*2 and remaining<=self.LOOP_FADE:
                new=self._start(current['path'],self.LOOP_FADE)
                if new:
                    self._fade(current,0.,self.LOOP_FADE)
                else:
                    current['sound'].loop=True  # Safe fallback if a loop voice cannot load.
                    current['started']=self.now()
        if not self.voices:
            if self.event:self.event.cancel()
            self.event=None
            return False
        return True

    def close(self):
        if self.event:self.event.cancel()
        self.event=None
        for voice in list(self.voices):self._remove(voice)
        self.current=None;self.on_current(None)
