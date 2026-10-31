"""Render the tutorial over the real HUD without opening the player's DB."""
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from strategy_ui_fixture import Window, hud_fixture, cleanup_hud
from kivy.base import EventLoop
from tutorial import TutorialProgress
from tutorial_ui import TutorialPanel


def settle():
    for _ in range(8):
        time.sleep(.025)
        EventLoop.idle()


host = hud_fixture()
Window.add_widget(host)
progress = TutorialProgress('Борьба')
progress.next()
progress.next()
panel = TutorialPanel(progress, lambda: None, lambda: None, lambda: None, lambda: None)
host.root_overlay.add_widget(panel)
for size, suffix in (((1280, 720), 'desktop'), ((640, 360), 'phone'), ((360, 640), 'portrait')):
    Window.size = size
    settle()
    target = ROOT / 'assets' / f'tutorial-guide-{suffix}.png'
    saved = Path(Window.screenshot(name=str(target)))
    if saved != target:
        saved.replace(target)
cleanup_hud(host)
Window.remove_widget(host)
print('Rendered tutorial previews')
