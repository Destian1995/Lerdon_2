import unittest

from strategy_ui_fixture import Window,Widget
from map_atmosphere import MapAtmosphere


def site(cid=1,ready=0):
    return dict(id=cid,tier=7,variant=3,x=400,y=300,ready_turn=ready)


class SignalTests(unittest.TestCase):
    def setUp(self):
        self.layer=MapAtmosphere()
        self.layer.configure((30,20),.8)
        self.addCleanup(self.layer.stop)

    def test_lightning_and_flash_reuse_instructions_on_shared_clock(self):
        signals=self.layer.monster_signals
        signals.sync([site()],0)
        signal=signals.signals[1]
        pool=tuple(signal.group.children)
        seen=False
        for frame in range(600):
            self.layer.update(1/30)
            seen=seen or signal.core_color.a>.1
        self.assertTrue(seen)
        self.assertEqual(tuple(signal.group.children),pool)
        self.assertIsNone(self.layer._event)
        self.layer.start()
        event=self.layer._event
        self.layer.start()
        self.assertIs(self.layer._event,event)
        self.layer.stop()
        self.assertIsNone(self.layer._event)

    def test_respawning_lair_has_no_flash_and_can_flash_after_respawn(self):
        signals=self.layer.monster_signals
        signals.sync([site(ready=5)],4)
        signal=signals.signals[1]
        signal.wait=0
        signals.update(.1)
        self.assertEqual(signal.core_color.a,0)
        self.assertEqual(signal.halo_color.a,0)
        signals.sync([site(ready=5)],5)
        self.assertGreater(signal.core_color.a,.1)

    def test_resize_reprojects_lightning_without_allocating_new_signals(self):
        signals=self.layer.monster_signals
        signals.sync([site()],0)
        signal=signals.signals[1];signal.wait=0;signals.update(.01)
        points=list(signal.core.points)
        self.layer.configure((100,50),1.2)
        signals.sync([site()],0)
        self.assertIs(signals.signals[1],signal)
        expected=[]
        for x,y in zip(points[::2],points[1::2]):expected.extend((100+(x-30)*1.5,50+(y-20)*1.5))
        for actual,wanted in zip(signal.core.points,expected):self.assertAlmostEqual(actual,wanted,places=3)
        signals.sync([],0)
        self.assertEqual(signals.signals,{})
        self.assertEqual(len(signals.group.children),0)


if __name__=='__main__':unittest.main()
