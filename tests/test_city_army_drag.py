import unittest
from types import SimpleNamespace
from unittest.mock import patch
from strategy_ui_fixture import Window, Widget
from test_dialog_layout import settle
from test_map_zoom import Touch
from test_otherworlds import fixture
from test_allied_movement import city_methods
import test_allied_movement as allied
from city_army_drag import CityArmyDrag
from otherworld_ui import OtherworldMap, ForeignCityPopup
from mirror_army_transfer import send_from_map
import otherworlds as w


class GestureTests(unittest.TestCase):
    def setUp(self):
        self.drops=[]
        self.gesture=CityArmyDrag(Widget(),lambda p:1 if p[0]<100 else 2,
                                  lambda city:city==1,lambda *v:self.drops.append(v))
        self.addCleanup(self.gesture.cancel)

    def test_hold_drag_sends_once_and_consumes_release(self):
        t=Touch(50,100);self.gesture.down(t);self.gesture.activate()
        t.pos=(150,100)
        self.assertTrue(self.gesture.move(t));self.assertTrue(self.gesture.up(t))
        self.assertFalse(self.gesture.up(t));self.assertEqual(self.drops,[(1,2)])
        self.assertFalse(self.gesture.layer.children)

    def test_pan_before_hold_and_cancel_never_send(self):
        t=Touch(50,100);self.gesture.down(t);t.pos=(80,100)
        self.assertFalse(self.gesture.move(t));self.gesture.activate()
        t.pos=(150,100);self.assertFalse(self.gesture.up(t));self.assertEqual(self.drops,[])
        self.gesture.down(Touch(50,100));self.gesture.cancel()
        self.assertIsNone(self.gesture.event)

    def test_small_jitter_keeps_hold_but_leaving_city_gesture_cancels_it(self):
        t=Touch(50,100);self.gesture.down(t);t.pos=(64,105)
        self.assertTrue(self.gesture.move(t));self.assertIsNotNone(self.gesture.event)
        self.gesture.activate();t.pos=(150,100)
        self.assertTrue(self.gesture.up(t));self.assertEqual(self.drops,[(1,2)])

    def test_army_removed_during_hold_does_not_activate(self):
        t=Touch(50,100);self.gesture.down(t)
        self.gesture.eligible=lambda _:False
        self.gesture.activate()
        self.assertFalse(self.gesture.active);self.assertIsNone(self.gesture.touch)

    def test_drag_uses_current_player_emblem_and_clears_it_after_release(self):
        from map_city_effects import faction_emblem
        from kivy.graphics import Rectangle
        for faction in ('Север','Эльфы','Вампиры','Адепты','Элины'):
            self.gesture.faction=lambda:faction
            touch=Touch(50,100);self.gesture.down(touch);self.gesture.activate()
            self.assertIs(self.gesture.emblem_texture,faction_emblem(faction))
            images=[i for i in self.gesture.layer.children if type(i) is Rectangle]
            self.assertEqual(len(images),1)
            self.assertIs(images[0].texture,faction_emblem(faction))
            touch.pos=(150,100);self.gesture.move(touch)
            self.assertEqual(len([i for i in self.gesture.layer.children if type(i) is Rectangle]),1)
            self.gesture.up(touch)
            self.assertIsNone(self.gesture.emblem_texture)


class MirrorTransferTests(unittest.TestCase):
    def setUp(self):
        self.db=fixture();w.enter(self.db,'Север','Home');self.addCleanup(self.db.close)
        self.target=self.db.execute('SELECT city2 FROM portal_roads WHERE city1=1 LIMIT 1').fetchone()[0]

    def test_selected_stack_moves_rest_stays_and_can_be_sent_separately(self):
        before=self.db.execute('SELECT SUM(unit_count) FROM garrisons').fetchone()[0]
        w.begin_beam(self.db,'Север',self.target,['troop1'])
        self.assertEqual([r[0] for r in w._camp_units(self.db,w.city_camp(self.db,'Север',1))],['Hero'])
        w.finish_beam(self.db,'Север')
        self.assertEqual(w._camp_units(self.db,w.party(self.db,'Север')['camp'])[0][1],1000)
        w.begin_beam(self.db,'Север',self.target,['Hero'],source=1)
        w.finish_beam(self.db,'Север')
        self.assertEqual({r[0] for r in w._camp_units(self.db,w.party(self.db,'Север')['camp'])},{'troop1','Hero'})
        self.assertEqual(self.db.execute('SELECT SUM(unit_count) FROM garrisons').fetchone()[0],before)
        self.assertEqual(self.db.execute("SELECT experience FROM garrisons WHERE unit_name='troop1'").fetchone()[0],3)

    def test_invalid_selection_and_no_moves_roll_back_every_change(self):
        before=list(self.db.execute('SELECT * FROM garrisons'))
        for names in ([],['missing']):
            with self.assertRaises(ValueError):w.begin_beam(self.db,'Север',self.target,names)
        self.db.execute('UPDATE turn_check_move SET moves_left=0')
        with self.assertRaises(ValueError):w.begin_beam(self.db,'Север',self.target,['troop1'])
        self.assertEqual(list(self.db.execute('SELECT * FROM garrisons')),before)
        self.assertIsNone(w.beam(self.db,'Север'))
        self.assertEqual(w.party(self.db,'Север')['city_id'],1)

    def test_stationary_source_switch_rolls_back_when_road_is_invalid(self):
        w.begin_beam(self.db,'Север',self.target,['troop1']);w.finish_beam(self.db,'Север')
        before=list(self.db.execute('SELECT * FROM garrisons'));party=w.party(self.db,'Север')
        with self.assertRaises(ValueError):w.begin_beam(self.db,'Север',1,['Hero'],source=1)
        self.assertEqual(list(self.db.execute('SELECT * FROM garrisons')),before)
        self.assertEqual(w.party(self.db,'Север'),party)


class MapUITests(unittest.TestCase):
    def setUp(self):
        self.old_size=Window.size;Window.size=(640,360);settle()
        self.db=fixture();self.db.execute("INSERT INTO resources VALUES('Север','Рабочие',1234)")
        w.enter(self.db,'Север','Home')
        self.owner=OtherworldMap(self.db,'Север');self.owner.open(animation=False);settle()
        self.target=self.db.execute('SELECT city2 FROM portal_roads WHERE city1=1 LIMIT 1').fetchone()[0]

    def tearDown(self):
        for child in list(Window.children):
            if hasattr(child,'dismiss'):child.dismiss(animation=False)
        settle();self.db.close();Window.size=self.old_size;settle()

    def test_workers_selection_stationary_roster_and_single_stack_autosend(self):
        self.assertIn('1.2',self.owner.resource_labels['Рабочие'].text)
        with patch.object(self.owner,'play_beam') as animate:
            popup=send_from_map(self.owner,1,self.target);settle()
            self.assertEqual(len(popup.unit_buttons),2)
            self.assertTrue(popup.send.disabled)
            popup.unit_buttons['troop1'].dispatch('on_release')
            popup.send.dispatch('on_release');settle()
            animate.assert_called_once_with(1,self.target)
            w.finish_beam(self.db,'Север')
            city=ForeignCityPopup(self.owner,w.cities(self.db,'Север')[0])
            self.assertEqual(len(city.army_box.rows.children),1)
            self.assertEqual(city.army_box.rows.children[0].name,'Hero')
            send_from_map(self.owner,1,self.target)
            self.assertEqual(animate.call_count,2)

    def test_all_faction_effects_change_and_keep_one_clock(self):
        effects=self.owner.map.effects
        for faction in ('north','elves','vampires','adepts','elines'):
            effects.weather=faction
            effects.update(.1);points=list(effects.flair[0].layers[0][1].pos)
            effects.update(.1)
            self.assertNotEqual(points,list(effects.flair[0].layers[0][1].pos))
        event=effects._event;effects.start();self.assertIs(event,effects._event)

    def test_real_window_hold_with_jitter_drags_mirror_garrison(self):
        from kivy.tests.common import UnitTestTouch
        Window.size=(1200,800);settle();self.owner.fit();settle()
        source=self.owner.map.nodes[0]
        destination=next(c for c in self.owner.map.nodes if c['id']==self.target)
        start=self.owner.map.point(source['x'],source['y'])
        touch=UnitTestTouch(*start);touch.touch_down()
        touch.touch_move(start[0]+12,start[1]+2)
        self.assertIsNotNone(self.owner.map.army_drag.event)
        for _ in range(4):settle()
        self.assertTrue(self.owner.map.army_drag.active)
        with patch('mirror_army_transfer.send_from_map') as send:
            touch.touch_move(*self.owner.map.point(destination['x'],destination['y']))
            touch.touch_up()
            send.assert_called_once_with(self.owner,source['id'],self.target)

    def test_mirror_pick_includes_top_of_rendered_city(self):
        for x,y,width,height,cid in self.owner.map.city_bounds:
            self.assertEqual(self.owner.map.city_at((x+width/2,y+height-2)),cid)


class MainMapPickerTests(unittest.TestCase):
    def test_drop_filters_source_and_autosends_only_single_stack(self):
        fixture_case=allied.AlliedMovementTests();fixture_case.setUp();db=fixture_case.db
        self.addCleanup(db.close)
        errors=[];selections=[];sent=[]
        load=city_methods('load_troops_by_type',_show_dark_error_popup=lambda *a:errors.append(a))['load_troops_by_type']
        owner=SimpleNamespace(conn=db,city_name='Наш дальний',player_fraction='Север',
            is_ally=lambda *_:False,_drag_source='Наш ближний',
            show_troops_selection=lambda rows:selections.append(rows),
            move_selected_group_to_city=lambda:sent.append(owner.selected_group))
        load(owner,'Всех',None)
        self.assertEqual(len(selections[0]),3)
        self.assertTrue(all(row[0]=='Наш ближний' for row in selections[0]))
        db.execute("DELETE FROM garrisons WHERE city_name='Наш ближний' AND unit_name!='Мечник'")
        load(owner,'Всех',None)
        self.assertEqual(len(sent),1);self.assertEqual(sent[0][0]['unit_count'],10)
        owner._drag_source='Остров';load(owner,'Всех',None)
        self.assertTrue(errors);self.assertEqual(len(sent),1)
