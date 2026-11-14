"""Poll Android callbacks on Kivy's thread; Java owns the ad lifecycle."""
import json


class AndroidRewarded:
    def __init__(self):
        from jnius import autoclass
        self.bridge = autoclass('com.lerdonlegends.ads.RewardedBridge')
        self.activity = autoclass('org.kivy.android.PythonActivity').mActivity

    def show(self, session, unit):
        self.bridge.show(self.activity, session, unit)

    def poll(self):
        for _ in range(16):
            event = self.bridge.poll(self.activity)
            if not event:
                break
            yield json.loads(event)

    def acknowledge(self, session):
        self.bridge.acknowledge(self.activity, session)

    def cancel(self, session):
        self.bridge.cancel(self.activity, session)
