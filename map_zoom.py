"""GPU camera, HUD controls and map-only wheel/drag/pinch gestures."""
import math

from kivy.clock import Clock
from kivy.core.window import Window
from kivy.graphics import Canvas, InstructionGroup, PushMatrix, PopMatrix, Translate, Scale
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.modalview import ModalView

from map_camera import MapCamera
from strategy_ui import StrategyButton, surface


class CanvasCamera:
    """Enclose just one canvas, leaving sibling HUD/popup canvases untouched."""
    def __init__(self, canvas):
        self.canvas = canvas
        self.scoped = isinstance(canvas,Canvas)
        self.begin,self.end = InstructionGroup(),InstructionGroup()
        self.begin.add(PushMatrix())
        self.translate = Translate()
        self.scale = Scale(1,1,1)
        self.begin.add(self.translate)
        self.begin.add(self.scale)
        self.end.add(PopMatrix())

    def update(self, camera):
        self.translate.x,self.translate.y = camera.translation
        self.scale.x = self.scale.y = camera.zoom
        before = self.canvas.before if self.scoped else self.canvas
        after = self.canvas.after if self.scoped else self.canvas
        if (before.children and after.children and before.children[0] is self.begin
                and after.children[-1] is self.end):
            return
        self.remove()
        before.insert(0,self.begin)
        after.insert(len(after.children),self.end)

    def remove(self):
        for canvas,group in ((self.canvas.before if self.scoped else self.canvas,self.begin),
                             (self.canvas.after if self.scoped else self.canvas,self.end)):
            if group in canvas.children:
                canvas.remove(group)


class MapZoom:
    def __init__(self, owner):
        self.owner = owner
        self.camera = MapCamera(Window.size,self.rect())
        self.map_canvas = CanvasCamera(owner.canvas)
        self.overlays = []
        self.screen = None
        self.touches = {}
        self.running = False
        self.attach_event = None
        self.resize_event = Clock.create_trigger(self.resize,0)
        self.controls = surface(BoxLayout(size_hint=(None,None),size=(dp(184),dp(52)),
                                pos_hint={'center_x':.5},y=dp(8),padding=dp(4),spacing=dp(4)))
        self.minus = StrategyButton(text='−',size_hint_x=None,width=dp(48))
        self.indicator = StrategyButton(text='×1.0')
        self.plus = StrategyButton(text='+',size_hint_x=None,width=dp(48))
        for button in (self.minus,self.indicator,self.plus):
            self.controls.add_widget(button)
        self.minus.bind(on_release=lambda *_: self.change(-.1))
        self.plus.bind(on_release=lambda *_: self.change(.1))
        self.indicator.bind(on_release=lambda *_: self.reset())
        self.restore()

    def rect(self):
        return (*self.owner.map_pos,self.owner.base_map_width*self.owner.map_scale,
                self.owner.base_map_height*self.owner.map_scale)

    def start(self):
        if self.running:
            return
        self.running = True
        Window.bind(on_resize=self.resize_event)
        Window.bind(children=self.visibility)
        self.attach_event = Clock.schedule_once(self.attach,0)

    def stop(self):
        self.running = False
        Window.unbind(on_resize=self.resize_event)
        Window.unbind(children=self.visibility)
        self.resize_event.cancel()
        if self.attach_event:
            self.attach_event.cancel()
        for item in list(self.touches.values()):
            item['touch'].ungrab(self.owner)
        self.touches.clear()
        if self.controls.parent:
            self.controls.parent.remove_widget(self.controls)
        if self.screen:
            self.screen.game_area.unbind(children=self.visibility)
            self.screen.root_overlay.unbind(children=self.visibility)
        for wrapper in self.overlays:
            wrapper.remove()
        self.overlays.clear()
        self.screen = None

    def attach(self, dt=0):
        self.attach_event = None
        if not self.owner.parent:
            return
        screen = next((w for w in self.owner.parent.children
                       if hasattr(w,'game_area') and hasattr(w,'root_overlay')),None)
        if screen is None:
            return
        if self.screen is not screen:
            self.screen = screen
            screen.game_area.bind(children=self.visibility)
            screen.root_overlay.bind(children=self.visibility)
        if self.controls.parent is not screen.root_overlay:
            screen.root_overlay.add_widget(self.controls)
        self.restore_overlays()
        self.visibility()

    def blocked(self):
        return (any(isinstance(w,ModalView) for w in Window.children) or
                bool(self.screen and (self.screen.game_area.children or
                                      getattr(self.screen,'_turn_overlay',None))))

    def visibility(self, *args):
        blocked = self.blocked()
        self.controls.opacity = 0 if blocked else 1
        self.controls.disabled = blocked

    def restore_overlays(self):
        if self.screen is None:
            return
        canvases = [self.screen.game_area.canvas.before]
        layer = getattr(self.owner,'_map_atmosphere',None)
        effects = getattr(layer,'city_effects',None)
        if effects and effects._standard_host is self.screen.game_area and effects._standard_canvas is not None:
            canvases.append(effects._standard_canvas)
        for canvas in canvases:
            wrapper = next((w for w in self.overlays if w.canvas is canvas),None)
            if wrapper is None:
                wrapper = CanvasCamera(canvas)
                self.overlays.append(wrapper)
            wrapper.update(self.camera)

    def restore(self):
        self.camera.configure(Window.size,self.rect())
        self.map_canvas.update(self.camera)
        self.restore_overlays()
        self.indicator.text = f'×{self.camera.zoom:.1f}'
        self.minus.disabled = self.camera.zoom <= 1.0+1e-9
        self.plus.disabled = self.camera.zoom >= 1.5-1e-9

    def resize(self, dt=0):
        # Refit the overview once, then keep the user's zoom and bounded pan.
        if not self.running or not self.owner.parent:
            return
        self.owner.update_cities()
        self.restore()

    def change(self, step):
        if self.blocked():
            return
        self.camera.set_zoom(round(self.camera.zoom+step,2))
        self.restore()

    def reset(self):
        if not self.blocked():
            self.camera.reset()
            self.restore()

    def down(self, touch):
        if self.blocked() or not self.camera.contains(*touch.pos):
            return False
        button = getattr(touch,'button',None) or ''
        if button in ('scrollup','scrolldown'):
            self.camera.set_zoom(self.camera.zoom+(.1 if button=='scrollup' else -.1),touch.pos)
            touch.ud['map_zoom_wheel'] = True
            self.restore()
            return True
        if button not in ('','left'):
            return False
        self.touches[touch.uid] = dict(touch=touch,pos=tuple(touch.pos),origin=tuple(touch.pos),moved=False)
        touch.grab(self.owner)
        if len(self.touches)>1:
            for item in self.touches.values():
                item['moved'] = True
        return True

    def move(self, touch):
        item = self.touches.get(touch.uid)
        if item is None:
            return False
        if self.blocked():
            item['moved'] = True
            return True
        before = [v['pos'] for v in list(self.touches.values())[:2]]
        previous = item['pos']
        item['pos'] = tuple(touch.pos)
        if math.dist(item['origin'],touch.pos) > dp(8):
            item['moved'] = True
        if len(self.touches)>1:
            after = [v['pos'] for v in list(self.touches.values())[:2]]
            old_center = tuple((a+b)/2 for a,b in zip(*before))
            new_center = tuple((a+b)/2 for a,b in zip(*after))
            old_distance = math.dist(*before)
            if old_distance>1:
                self.camera.set_zoom(self.camera.zoom*math.dist(*after)/old_distance,old_center)
                self.camera.move(new_center[0]-old_center[0],new_center[1]-old_center[1])
        elif item['moved'] and self.camera.zoom>1:
            self.camera.move(touch.x-previous[0],touch.y-previous[1])
        self.restore()
        return True

    def up(self, touch):
        if touch.ud.pop('map_zoom_wheel',False):
            return True
        item = self.touches.pop(touch.uid,None)
        if item is None:
            return False
        touch.ungrab(self.owner)
        if (not item['moved'] and math.dist(item['origin'],touch.pos)<=dp(8)
                and not self.blocked() and self.camera.contains(*touch.pos)):
            touch.push()
            try:
                touch.apply_transform_2d(self.camera.unproject)
                self.owner.check_fortress_click(touch)
            finally:
                touch.pop()
        return True


def sync_map_zoom(screen):
    """Military badge redraws clear their canvas; reapply its camera wrapper."""
    parent = getattr(screen,'parent',None)
    if parent:
        for widget in parent.children:
            camera = getattr(widget,'_map_zoom',None)
            if camera and camera.screen is screen:
                camera.restore_overlays()
