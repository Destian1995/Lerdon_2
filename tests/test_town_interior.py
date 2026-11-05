import sqlite3
import unittest
from pathlib import Path
from strategy_ui_fixture import Window,city_fixture
from test_dialog_layout import settle
from test_map_zoom import Touch
from kivy.metrics import Metrics,dp,sp
from kivy.uix.popup import Popup
from city_construction import CATALOG,buy_building,building_counts
from town_art import THEMES,city_variant,panorama_path,building_path


class TownTests(unittest.TestCase):
    def setUp(self):
        self.size=Window.size;self.metrics=Metrics.density,Metrics.fontscale
        Metrics.density=Metrics.fontscale=1;Window.size=(640,360);settle()
        self.owner,self.db=city_fixture()
        self.db.executescript("CREATE TABLE resources(faction,resource_type,amount); INSERT INTO resources VALUES('Адепты','Кроны',500000);")
        self.db.execute('DELETE FROM buildings');self.db.commit()
        self.owner.load_buildings()
        self.owner.open(animation=False);settle()

    def tearDown(self):
        for widget in list(Window.children):
            if isinstance(widget,Popup):widget.dismiss(animation=False)
        if hasattr(self.owner,'town_popup'):self.owner.town_popup.chooser.dismiss()
        self.owner.dismiss(animation=False);settle();self.db.close()
        Metrics.density,Metrics.fontscale=self.metrics;Window.size=self.size;settle()

    def money(self):return self.db.execute('SELECT amount FROM resources').fetchone()[0]

    def test_purchased_building_appears_in_both_scenes_and_survives_reopening(self):
        town=self.owner._open_build_menu();settle()
        town.choose('Рынок');town.build.dispatch('on_release');settle()
        self.assertEqual(self.money(),470000)
        self.assertEqual(town.scene.counts['Рынок'],1)
        self.assertEqual(self.owner.city_preview.counts['Рынок'],1)
        self.assertIn('Рынок',town.scene.sprites)
        self.assertIn('Рынок',self.owner.city_preview.sprites)
        town.dismiss(animation=False);settle()
        again=self.owner._open_build_menu();settle()
        self.assertEqual(again.scene.counts['Рынок'],1)
        self.assertIn('Рынок',again.scene.sprites)
        self.assertEqual(again.scene.city,town.scene.city)

    def test_preview_tap_opens_city_and_plot_tap_selects_building(self):
        self.owner.open(animation=False);settle();self.owner.city_columns.select(1);settle()
        scene=self.owner.city_preview
        touch=Touch(*scene.center);scene.on_touch_down(touch);scene.on_touch_up(touch);settle()
        town=self.owner.town_popup
        from town_art import LOTS
        name='Кузница';u,v,_=LOTS[name];x,y,w,h=town.scene.scene_bounds
        touch=Touch(x+u*w,y+v*h);town.scene.on_touch_down(touch);town.scene.on_touch_up(touch)
        self.assertEqual(town.selected,name)

    def test_live_owner_balance_and_unique_buildings_are_enforced(self):
        self.assertTrue(self.owner._build_building('Стена',0))
        self.assertEqual(self.money(),460000)
        self.db.execute('UPDATE buildings SET count=3');self.db.commit()
        before=self.money()
        with self.assertRaises(ValueError):buy_building(self.db,self.owner.city_name,'Адепты','Стена')
        self.assertEqual(self.money(),before)
        self.db.execute('DELETE FROM buildings')
        self.db.executemany('INSERT INTO buildings VALUES(?,?,?,?)',[(self.owner.city_name,'Адепты',n,c) for n,c in [('Больница',12),('Фабрика',12),('Стена',1)]])
        self.db.commit()
        with self.db:buy_building(self.db,self.owner.city_name,'Адепты','Рынок')
        self.assertEqual(building_counts(self.db,self.owner.city_name,'Адепты')['Рынок'],1)
        self.db.execute('DELETE FROM buildings');self.db.execute('UPDATE resources SET amount=0');self.db.commit()
        with self.assertRaises(ValueError):buy_building(self.db,self.owner.city_name,'Адепты','Больница')
        self.assertFalse(building_counts(self.db,self.owner.city_name,'Адепты'))
        self.db.execute("UPDATE cities SET faction='Север'");self.db.execute('UPDATE resources SET amount=500000');self.db.commit()
        self.assertFalse(self.owner._build_building('Рынок',0));self.assertEqual(self.money(),500000)

    def test_failed_insert_rolls_back_payment(self):
        self.db.execute("CREATE TRIGGER fail_build BEFORE INSERT ON buildings BEGIN SELECT RAISE(ABORT,'test failure'); END")
        before=self.money()
        with self.assertRaises(sqlite3.IntegrityError):buy_building(self.db,self.owner.city_name,'Адепты','Рынок')
        self.assertEqual(self.money(),before)
        self.assertFalse(building_counts(self.db,self.owner.city_name,'Адепты'))

    def test_council_auto_buildings_are_real_visible_layers_on_panorama(self):
        from city_development import auto_develop
        self.db.executescript("CREATE TABLE nobles(loyalty,status); INSERT INTO nobles VALUES(81,'active');")
        town=self.owner._open_build_menu();settle()
        self.assertEqual(auto_develop(self.db,'Адепты'),[(self.owner.city_name,n) for n in CATALOG])
        town.choose('Кузница');settle()
        self.assertEqual(set(town.scene.sprites),set(CATALOG))
        self.assertEqual(town.scene.counts,dict.fromkeys(CATALOG,1))

    def test_plot_highlight_is_replaced_by_building_contour_and_effect_on_tap(self):
        from town_scene import building_shape,shape_contains
        town=self.owner._open_build_menu();settle()
        name='Рынок';town.choose(name)
        self.assertIn(name,town.scene.plots)
        self.assertNotIn(name,town.scene.outlines)
        town.purchase();settle()
        self.assertNotIn(name,town.scene.plots)
        self.assertIn(name,town.scene.outlines)
        self.assertIn(CATALOG[name]['desc'],town.detail.text)
        self.assertNotIn('Цена:',town.detail.text)
        self.assertTrue(town.build.disabled)
        sprite=town.scene.sprites[name]
        path=building_path(town.faction,name);mask,contours=building_shape(path)
        self.assertTrue(contours)
        self.assertFalse(shape_contains(path,0,0))
        # Tap the opaque upper half, away from the ground touch target.
        candidates=[(x,y) for y in range(len(mask)//2,len(mask))
                    for x in range(len(mask[0])) if mask[y][x]]
        x,y=candidates[len(candidates)//2]
        point=(sprite.pos[0]+(x+.5)/len(mask[0])*sprite.size[0],
               sprite.pos[1]+(y+.5)/len(mask)*sprite.size[1])
        town.choose('Больница')
        touch=Touch(*point);town.scene.on_touch_down(touch);town.scene.on_touch_up(touch)
        self.assertEqual(town.selected,name)
        self.assertIn('Построено',town.detail.text)
        self.assertIn(CATALOG[name]['desc'],town.detail.text)
        # Finished buildings have neither plot overlays nor contour unless selected.
        town.choose('Больница')
        self.assertNotIn(name,town.scene.outlines)
        self.assertNotIn(name,town.scene.plots)

    def test_panorama_and_controls_fit_small_android_and_portrait(self):
        town=self.owner._open_build_menu();settle()
        for size,density,scale in (((640,360),1,1),((1280,576),2.5,1.2),((392,844),1,1)):
            Window.size=size;Metrics.density=density;Metrics.fontscale=scale;settle();town.fit();settle()
            for widget in (town.scene,town.controls,town.selector,town.build):
                self.assertGreaterEqual(widget.x,town.root.x-1);self.assertGreaterEqual(widget.y,town.root.y-1)
                self.assertLessEqual(widget.right,town.root.right+1);self.assertLessEqual(widget.top,town.root.top+1)
            self.assertGreaterEqual(town.build.height,dp(44)-1)
            self.assertGreaterEqual(town.selector.height,dp(44)-1)
            self.assertGreaterEqual(town.detail.font_size,sp(14)-.1)
            self.assertGreater(town.detail_scroll.height,dp(14))
            self.assertGreater(town.scene.width,dp(150))
            from town_art import LOTS
            for name,(u,v,_) in town.scene.lots.items():
                x,y,w,h=town.scene.scene_bounds
                touch=Touch(x+u*w,y+v*h);town.scene.on_touch_down(touch);town.scene.on_touch_up(touch)
                self.assertEqual(town.selected,name)
            town.export_to_png(f'.release/town-layout-{size[0]}x{size[1]}.png')


class TownArtTests(unittest.TestCase):
    def test_citadel_entrance_anchors_are_on_the_visible_gate(self):
        from PIL import Image
        from town_art import CITADEL_DOORS
        for faction,key in THEMES.items():
            with self.subTest(faction=faction), Image.open(building_path(faction,'Цитадель')) as art:
                u,v=CITADEL_DOORS[key]
                # A point just above the ground contact must be on the doorway,
                # not on the transparent margin below or beside the fortress.
                x=round(u*(art.width-1));y=round((1-v-.025)*(art.height-1))
                self.assertGreaterEqual(art.getpixel((x,y))[3],180)

    def test_every_faction_has_three_unique_panorama_files_and_six_transparent_buildings(self):
        from PIL import Image
        for faction,key in THEMES.items():
            images=[Path(f'files/city/interiors/{key}/city-{n}.jpg') for n in (1,2,3)]
            self.assertEqual(len({p.read_bytes() for p in images}),3)
            for path in images:
                with Image.open(path) as art:self.assertGreater(art.width,art.height)
            for name in CATALOG:
                with Image.open(building_path(faction,name)) as art:
                    self.assertEqual(art.mode,'RGBA')
                    low,high=art.getchannel('A').getextrema()
                    self.assertEqual(low,0);self.assertGreaterEqual(high,250)
                    self.assertLessEqual(max(art.size),768)

    def test_variant_is_stable_and_all_three_can_be_assigned(self):
        variants={city_variant('Город '+str(i)) for i in range(30)}
        self.assertEqual(variants,{1,2,3})
        self.assertEqual(panorama_path('Север','Виндгар'),panorama_path('Север','Виндгар'))
