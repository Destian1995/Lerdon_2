import unittest

from map_camera import MapCamera


class CameraTests(unittest.TestCase):
    def test_overview_is_identical_and_zoom_is_limited_to_one_and_a_half(self):
        camera=MapCamera((1200,800),(60,40,1080,720))
        self.assertEqual(camera.project(300,200),(300,200))
        camera.set_zoom(100)
        self.assertEqual(camera.zoom,1.5)
        camera.set_zoom(-100)
        self.assertEqual(camera.zoom,1)
        self.assertEqual(camera.pan,(0,0))
        self.assertFalse(camera.set_zoom(float('nan')))

    def test_zoom_keeps_the_point_under_cursor_when_edges_allow_it(self):
        camera=MapCamera((1200,800),(0,0,1200,800))
        anchor=(750,450)
        camera.set_zoom(1.5,anchor)
        self.assertEqual(camera.unproject(*anchor),anchor)
        for point in ((0,0),(600,400),(1100,750)):
            projected=camera.project(*point)
            original=camera.unproject(*projected)
            self.assertAlmostEqual(point[0],original[0])
            self.assertAlmostEqual(point[1],original[1])

    def test_pan_cannot_move_beyond_map_edges_and_reset_restores_center(self):
        camera=MapCamera((1200,800),(0,0,1200,800))
        camera.set_zoom(1.5)
        camera.move(10000,-10000)
        self.assertEqual(camera.pan,(300,-200))
        camera.reset()
        self.assertEqual(camera.translation,(0,0))

    def test_axes_that_still_fit_cannot_be_dragged_into_empty_space(self):
        camera=MapCamera((1280,576),(251.2,28.8,777.6,518.4))
        camera.set_zoom(1.5)
        camera.move(10000,10000)
        self.assertEqual(camera.pan[0],0)
        self.assertAlmostEqual(camera.pan[1],100.8)

    def test_resize_keeps_zoom_and_clamps_pan(self):
        camera=MapCamera((1200,800),(60,40,1080,720))
        camera.set_zoom(1.5)
        camera.move(100,100)
        camera.configure((640,360),(77,18,486,324))
        self.assertEqual(camera.zoom,1.5)
        self.assertLessEqual(abs(camera.pan[0]),44.5)
        self.assertLessEqual(abs(camera.pan[1]),63)


from strategy_ui_fixture import *
from test_responsive_windows import settle
from map_atmosphere import MapAtmosphere
from map_zoom import MapZoom, sync_map_zoom
from kivy.graphics import Fbo, ClearColor, ClearBuffers


class Touch:
    counter=0
    def __init__(self,x,y,button='left'):
        Touch.counter+=1
        self.uid=Touch.counter
        self.pos=(x,y)
        self.button=button
        self.ud={}
        self.stack=[]
        self.grabbed=set()
    @property
    def x(self):
        return self.pos[0]
    @property
    def y(self):
        return self.pos[1]
    def grab(self,widget):
        self.grabbed.add(widget)
    def ungrab(self,widget):
        self.grabbed.discard(widget)
    def push(self):
        self.stack.append(self.pos)
    def pop(self):
        self.pos=self.stack.pop()
    def apply_transform_2d(self,transform):
        self.pos=transform(*self.pos)


class ZoomUITests(unittest.TestCase):
    def setUp(self):
        self.original_size=Window.size
        Window.size=(1200,800)
        settle()
        self.root=FloatLayout(size_hint=(None,None),size=Window.size)
        tree=ast.parse((ROOT/'main.py').read_text(encoding='utf-8'))
        source=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='MapWidget')
        methods=[n for n in source.body if isinstance(n,ast.FunctionDef) and n.name in
                 ('on_touch_down','on_touch_move','on_touch_up')]
        cls=ast.ClassDef(name='TouchMap',bases=[ast.Name(id='Widget',ctx=ast.Load())],
                         keywords=[],body=methods,decorator_list=[])
        ns=dict(Widget=Widget)
        exec(compile(ast.fix_missing_locations(ast.Module(body=[cls],type_ignores=[])),
                     'main.py','exec'),ns)
        self.owner=ns['TouchMap'](size_hint=(None,None),size=Window.size)
        self.owner.map_pos,self.owner.map_scale=(0,0),1
        self.owner.base_map_width,self.owner.base_map_height=1200,800
        self.owner._road_geometry=object()
        self.clicks=[]
        self.owner.check_fortress_click=lambda touch:self.clicks.append(touch.pos)
        self.redraws=[]
        self.owner.update_cities=lambda *args:self.redraws.append(True)
        self.layer=MapAtmosphere()
        self.layer.configure((0,0),1)
        self.owner._map_atmosphere=self.layer
        self.screen=FloatLayout()
        self.screen.root_overlay=FloatLayout()
        self.screen.game_area=FloatLayout()
        self.screen.root_overlay.add_widget(self.screen.game_area)
        self.screen.add_widget(self.screen.root_overlay)
        self.root.add_widget(self.owner)
        self.root.add_widget(self.screen)
        self.layer.city_effects.attach_standards(self.screen.game_area)
        self.zoom=self.owner._map_zoom=MapZoom(self.owner)
        Window.add_widget(self.root)
        self.zoom.start()
        settle()

    def tearDown(self):
        self.zoom.stop()
        self.layer.city_effects.attach_standards(None)
        self.layer.stop()
        Window.remove_widget(self.root)
        Window.size=self.original_size
        settle()

    def test_buttons_limits_and_reset_do_not_rebuild_routes_or_change_hud_size(self):
        geometry=self.owner._road_geometry
        size=self.zoom.controls.size
        for _ in range(20):
            self.zoom.plus.dispatch('on_release')
        self.assertEqual(self.zoom.camera.zoom,1.5)
        self.assertTrue(self.zoom.plus.disabled)
        self.assertEqual(self.zoom.indicator.text,'×1.5')
        self.assertIs(self.owner._road_geometry,geometry)
        self.assertEqual(self.redraws,[])
        self.assertEqual(self.zoom.controls.size,size)
        self.zoom.indicator.dispatch('on_release')
        self.assertEqual(self.zoom.camera.zoom,1)
        self.assertTrue(self.zoom.minus.disabled)

    def test_zoomed_city_tap_uses_original_hit_coordinates(self):
        self.zoom.change(.5)
        touch=Touch(*self.zoom.camera.project(700,350))
        screen_point=touch.pos
        self.assertTrue(self.zoom.down(touch))
        self.assertTrue(self.zoom.up(touch))
        self.assertEqual(self.clicks,[(700,350)])
        self.assertEqual(touch.pos,screen_point)

    def test_real_window_dispatch_keeps_buttons_and_city_taps_separate(self):
        from kivy.tests.common import UnitTestTouch
        plus=UnitTestTouch(*self.zoom.plus.center)
        plus.touch_down()
        plus.touch_up()
        settle()
        self.assertAlmostEqual(self.zoom.camera.zoom,1.1)
        self.assertEqual(self.clicks,[])
        self.zoom.change(.4)
        touch=UnitTestTouch(*self.zoom.camera.project(700,350))
        touch.touch_down()
        touch.touch_up()
        self.assertEqual(len(self.clicks),1)
        self.assertAlmostEqual(self.clicks[0][0],700)
        self.assertAlmostEqual(self.clicks[0][1],350)

    def test_stop_releases_gestures_controls_and_overlay_matrices(self):
        touch=Touch(600,400)
        self.zoom.down(touch)
        self.zoom.stop()
        self.assertEqual(self.zoom.touches,{})
        self.assertNotIn(self.owner,touch.grabbed)
        self.assertIsNone(self.zoom.controls.parent)
        self.assertEqual(self.zoom.overlays,[])

    def test_wheel_and_drag_never_open_a_city(self):
        wheel=Touch(700,400,'scrollup')
        self.assertTrue(self.zoom.down(wheel))
        self.zoom.up(wheel)
        self.assertAlmostEqual(self.zoom.camera.zoom,1.1)
        touch=Touch(600,400)
        self.zoom.down(touch)
        touch.pos=(650,430)
        self.zoom.move(touch)
        self.zoom.up(touch)
        self.assertNotEqual(self.zoom.camera.pan,(0,0))
        self.assertEqual(self.clicks,[])

    def test_pinch_is_bounded_and_releases_do_not_trigger_city_clicks(self):
        first,second=Touch(550,400),Touch(650,400)
        self.zoom.down(first)
        self.zoom.down(second)
        second.pos=(850,400)
        self.zoom.move(second)
        self.assertEqual(self.zoom.camera.zoom,1.5)
        self.zoom.up(first)
        self.zoom.up(second)
        self.assertEqual(self.clicks,[])
        self.assertEqual(self.zoom.touches,{})

    def test_open_game_panel_blocks_camera_and_hides_controls(self):
        panel=Widget()
        self.screen.game_area.add_widget(panel)
        self.assertEqual(self.zoom.controls.opacity,0)
        self.zoom.plus.dispatch('on_release')
        self.assertEqual(self.zoom.camera.zoom,1)
        self.assertFalse(self.zoom.down(Touch(600,400,'scrollup')))
        self.screen.game_area.remove_widget(panel)
        self.assertEqual(self.zoom.controls.opacity,1)

    def test_loading_or_city_modal_does_not_leave_zoom_controls_hidden(self):
        popup=Popup(title='Город',content=Label(text='Информация'))
        try:
            popup.open(animation=False)
            settle()
            self.assertEqual(self.zoom.controls.opacity,0)
            self.assertFalse(self.zoom.down(Touch(600,400,'scrollup')))
            popup.dismiss(animation=False)
            settle()
            self.assertEqual(self.zoom.controls.opacity,1)
        finally:
            popup.dismiss(animation=False)

    def test_gpu_map_badges_and_flags_share_transform_but_hud_does_not(self):
        with self.owner.canvas:
            Color(1,0,0,1)
            Rectangle(pos=(700,300),size=(20,20))
        with self.screen.game_area.canvas.before:
            Color(0,0,1,1)
            Rectangle(pos=(700,350),size=(20,20))
        self.layer.city_effects.flag_group.add(Color(1,1,0,1))
        self.layer.city_effects.flag_group.add(Rectangle(pos=(700,400),size=(20,20)))
        with self.screen.root_overlay.canvas.after:
            Color(0,1,0,1)
            Rectangle(pos=(20,20),size=(20,20))
        self.zoom.change(.5)
        self.zoom.restore()
        fbo=Fbo(size=Window.size,with_stencilbuffer=True)
        with fbo:
            ClearColor(0,0,0,1)
            ClearBuffers()
        fbo.add(self.root.canvas)
        try:
            fbo.draw()
            pixels=fbo.pixels
            def rgb(x,y):
                index=(int(y)*1200+int(x))*4
                return tuple(pixels[index:index+3])
            for y,color in ((310,(255,0,0)),(360,(0,0,255)),(410,(255,255,0))):
                self.assertEqual(rgb(*self.zoom.camera.project(710,y)),color)
            self.assertEqual(rgb(30,30),(0,255,0))
            # New terrain/camp instructions added between full redraws remain
            # inside the camera, without rebuilding the world or its roads.
            with self.owner.canvas:
                Color(1,0,1,1)
                Rectangle(pos=(800,300),size=(20,20))
            fbo.draw()
            extra_pixels=fbo.pixels
            x,y=self.zoom.camera.project(810,310)
            index=(int(y)*1200+int(x))*4
            self.assertEqual(tuple(extra_pixels[index:index+3]),(255,0,255))
            self.owner.canvas.clear()
            with self.owner.canvas:
                Color(1,0,0,1)
                Rectangle(pos=(700,300),size=(20,20))
            self.screen.game_area.canvas.before.clear()
            with self.screen.game_area.canvas.before:
                Color(0,0,1,1)
                Rectangle(pos=(700,350),size=(20,20))
            self.zoom.restore()
            sync_map_zoom(self.screen)
            fbo.draw()
            self.assertEqual(fbo.pixels,pixels)
        finally:
            fbo.remove(self.root.canvas)


if __name__ == '__main__':
    unittest.main()
