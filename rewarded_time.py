"""Durable active-play minutes. No campaign database or wall-clock deadlines."""
import json
import math
import os
import time
from pathlib import Path

REWARD_SECONDS = 15 * 60
AD_UNIT_ID = 'R-M-20420203-1'


class PlayTime:
    def __init__(self, path, clock=time.monotonic):
        self.path = Path(path)
        self.clock = clock
        self.remaining = 0.0
        self.issued = []
        self.claimed = []
        self.running = False
        self.last = clock()
        try:
            data = json.loads(self.path.read_text(encoding='utf-8'))
            seconds = float(data['remaining'])
            if math.isfinite(seconds) and seconds >= 0:
                self.remaining = seconds
            self.issued = [s for s in data.get('issued', []) if isinstance(s, str)][-128:]
            self.claimed = [s for s in data.get('claimed', []) if isinstance(s, str)][-128:]
        except (OSError, ValueError, KeyError, TypeError):
            pass

    def save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix('.tmp')
        with temporary.open('w', encoding='utf-8') as stream:
            json.dump(dict(remaining=self.remaining, issued=self.issued, claimed=self.claimed), stream)
            stream.flush()
            os.fsync(stream.fileno())
        temporary.replace(self.path)

    def tick(self, running):
        now = self.clock()
        before = self.remaining
        if self.running:
            self.remaining = max(0.0, before - max(0.0, now - self.last))
        self.last = now
        self.running = bool(running)
        return before > 0 and self.remaining == 0

    def issue(self, session):
        if session not in self.issued:
            self.issued = (self.issued + [session])[-128:]
            self.save()

    def grant(self, session):
        if session not in self.issued or session in self.claimed:
            return False
        old = self.remaining, self.claimed[:]
        self.remaining += REWARD_SECONDS
        self.claimed = (self.claimed + [session])[-128:]
        try:
            self.save()
        except OSError:
            self.remaining, self.claimed = old
            raise
        return True

    @property
    def caption(self):
        seconds = math.ceil(self.remaining)
        return f'{seconds // 60:02d}:{seconds % 60:02d}'
