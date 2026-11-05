"""Real purchases, retained windows and GPU particle lifecycle."""
import unittest
from strategy_ui_fixture import Window,city_fixture
from kivy.uix.popup import Popup
from test_dialog_layout import settle
from town_effects import construction_opacity,FLASH_DURATION


class TownEffectsTests(unittest.TestCase):
    def setUp(self):
        self.size=Window.size;Window.size=(900,600);settle()
        self.owner,self.db=city_fixture()
        self.db.executescript("CREATE TABLE resources(faction,resource_type,amount); INSERT INTO resources VALUES('Адепты','Кроны',500000);")
        self.db.execute('DELETE FROM buildings');self.db.commit()
        self.owner.load_buildings();self.owner.open(animation=False);settle()

    def tearDown(self):
        for widget in list(Window.children):
            if isinstance(widget,Popup):widget.dismiss(animation=False)
        settle();self.db.close();Window.size=self.size;settle()

    def test_actual_purchase_blinks_only_the_new_sprite_twice_then_settles(self):
        town=self.owner._open_build_menu();settle()
        effects=town.scene.effects
        effects.stop()
        town.choose('Кузница');town.purchase();effects.stop()
        self.assertEqual(set(effects.flashes),{'Кузница'})
        self.assertIn('Кузница',self.owner.city_preview.effects.flashes)
        before=effects.flashes['Кузница']
        town.choose('Рынок');effects.stop()
        self.assertEqual(effects.flashes['Кузница'],before)
        for _ in range(14):effects.update(.1)
        self.assertFalse(effects.flashes)
        self.assertEqual(town.scene.sprite_colors['Кузница'].a,1)
        values=[construction_opacity(i*FLASH_DURATION/120) for i in range(121)]
        minima=[i for i in range(1,120) if values[i]<values[i-1] and values[i]<values[i+1]]
        self.assertEqual(len(minima),2)
        self.assertEqual(values[0],1);self.assertEqual(values[-1],1)
        self.assertLess(min(values),.25)
        town.dismiss(animation=False);settle()
        reopened=self.owner._open_build_menu();settle()
        self.assertFalse(reopened.scene.effects.flashes)

    def test_failed_purchase_does_not_blink_or_add_chimney_smoke(self):
        self.db.execute('UPDATE resources SET amount=0');self.db.commit()
        town=self.owner._open_build_menu();settle()
        town.choose('Кузница');town.purchase()
        self.assertFalse(town.scene.effects.flashes)
        self.assertFalse(town.scene.effects.chimneys)
        self.assertFalse(any(color.a for color,_ in town.scene.effects.smoke))

    def test_smoke_only_comes_from_constructed_chimneys_and_tracks_resize(self):
        town=self.owner._open_build_menu();settle()
        town.choose('Фабрика');town.purchase();settle()
        self.assertFalse(town.scene.effects.chimneys)  # Abbey workshop has a bell tower.
        town.choose('Кузница');town.purchase();settle()
        effects=town.scene.effects;effects.stop();effects.flashes.clear();effects.update(0)
        self.assertEqual([source[0] for source in effects.chimneys],['Кузница'])
        self.assertTrue(any(color.a>0 for color,_ in effects.smoke))
        old=effects.chimneys[0][1:3]
        Window.size=(640,360);settle()
        self.assertNotEqual(effects.chimneys[0][1:3],old)
        for actual,expected in zip((*effects.mask.pos,*effects.mask.size),effects.bounds):
            self.assertAlmostEqual(actual,expected,places=4)

    def test_temporary_blink_stops_its_clock_in_an_otherwise_quiet_city(self):
        self.db.execute("UPDATE cities SET faction='Нейтрал'");self.db.commit()
        self.owner.load_buildings();settle()
        scene=self.owner.city_preview;effects=scene.effects
        self.assertIsNone(effects._event)
        self.db.execute("INSERT INTO buildings VALUES(?,?,?,1)",(scene.city,'Нейтрал','Стена'))
        self.db.commit();scene.refresh();effects._sync.cancel()
        self.assertIn('Стена',effects.flashes)
        self.assertIsNotNone(effects._event)
        for _ in range(14):effects.update(.1)
        self.assertIsNone(effects._event)

    def test_preview_clock_stops_on_tab_hide_and_restarts_on_show(self):
        Window.size=(640,360);settle()
        preview=self.owner.city_preview.effects
        self.owner.city_columns.select(1);settle()
        self.assertIsNotNone(preview._event)
        same=preview._event;preview.sync_visibility()
        self.assertIs(preview._event,same)
        self.owner.city_columns.select(0);settle()
        self.assertIsNone(preview._event)
        self.owner.city_columns.select(1);settle()
        self.assertIsNotNone(preview._event)
        self.owner.dismiss(animation=False);settle()
        self.assertIsNone(preview._event)
        self.owner.open(animation=False);settle()
        self.assertIsNotNone(preview._event)

    def test_construction_clock_stops_after_close_and_new_window_has_one_clock(self):
        town=self.owner._open_build_menu();settle();effects=town.scene.effects
        self.assertIsNotNone(effects._event)
        town.dismiss(animation=False);settle()
        self.assertIsNone(effects._event)
        age=effects.age;settle();self.assertEqual(effects.age,age)
        fresh=self.owner._open_build_menu();settle()
        self.assertIsNone(effects._event)
        self.assertIsNotNone(fresh.scene.effects._event)

    def test_faction_weather_reconfigures_without_widget_overlays_or_particle_growth(self):
        town=self.owner._open_build_menu();settle();scene=town.scene
        for faction,key in [('Север','north'),('Эльфы','elves'),('Вампиры','vampires'),('Адепты','adepts')]:
            self.db.execute('UPDATE cities SET faction=?',(faction,));self.db.commit()
            scene.refresh();settle();effects=scene.effects;effects.stop()
            self.assertEqual(effects.key,key)
            self.assertFalse(scene.children)
            objects=len(effects.weather_layer.children)
            for _ in range(12):effects.update(.1)
            self.assertEqual(len(effects.weather_layer.children),objects)
            if key=='adepts':self.assertTrue(effects.rain)
            else:self.assertTrue(effects.particles)
            if key=='elves':
                effects.age=4.32;effects.update(0)
                self.assertGreater(effects.glow.a,0)
                self.assertGreater(max(c.a for c,_ in effects.bolt.layers),0)
