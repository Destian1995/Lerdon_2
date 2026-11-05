import json
import random
import unittest
from strategy_ui_fixture import Window
from test_dialog_layout import settle
from test_otherworlds import fixture
from kivy.metrics import Metrics
from kivy.uix.popup import Popup
from otherworld_ui import OtherworldMap,ForeignCityPopup
from otherworld_themes import THEMES,CONFLICT_SIDES,image_path
from otherworld_effects import fog_front
import otherworlds as w
import otherworld_quests as q


class TownUITests(unittest.TestCase):
    def setUp(self):
        self.size=Window.size;self.density=max(1,Metrics.density)
        Metrics.density=1;Window.size=(640,360);settle()
        self.db=fixture();w.enter(self.db,'Север','Home')
        for i in range(1,6):w.recruit(self.db,'Север',i,10)
        self.owner=OtherworldMap(self.db,'Север');self.owner.open(animation=False);settle()
        self.city=ForeignCityPopup(self.owner,w.cities(self.db,'Север')[0]);self.city.open(animation=False);settle()

    def tearDown(self):
        for p in list(Window.children):
            if isinstance(p,Popup):p.dismiss(animation=False)
        settle();self.db.close();Metrics.density=self.density;Window.size=self.size;settle()

    def test_scrollable_garrison_and_three_services_fit_small_and_portrait_screens(self):
        self.assertEqual(len(self.city.army_box.rows.children),7)
        self.assertEqual({b.text for b in self.city.services.children},{'Рынок','Найм','Задания'})
        self.assertIsNone(self.city.market.parent)
        for size,density in (((640,360),1),((1280,576),2),((392,844),1)):
            Window.size=size;Metrics.density=density;settle();self.city.fit();settle()
            self.assertGreater(self.city.army_box.height,50)
            for b in self.city.services.children:
                self.assertGreaterEqual(b.height,44*density)
                self.assertGreaterEqual(b.width,44*density)
                self.assertGreaterEqual(b.x,self.city.root.x-1)
                self.assertLessEqual(b.right,self.city.root.right+1)
                self.assertGreaterEqual(b.y,self.city.root.y-1)
                self.assertLessEqual(b.top,self.city.root.top+1)

    def test_market_opens_separately_and_recruitment_has_no_tier_hints(self):
        self.city.market_button.dispatch('on_release');settle()
        self.assertIs(self.city.market.parent,self.city.market_popup.root)
        self.assertEqual(len(self.city.crystal_market.panels),2)
        self.city.market_popup.dismiss(animation=False);settle()
        self.city.recruit_button.dispatch('on_release');settle()
        session=self.city.recruitment
        self.assertEqual(session.notice.text,'')
        self.assertEqual(session.notice.height,0)
        self.assertTrue(all(not info['role_label'][0].isdigit() for _,info in session.units))

    def test_tavern_barmaid_opens_work_and_accepts_case_away_from_the_gate(self):
        self.city.dismiss(animation=False)
        self.db.execute("UPDATE portal_parties SET city_id=3 WHERE faction='Север'");self.db.commit()
        self.city=ForeignCityPopup(self.owner,w.cities(self.db,'Север')[2]);self.city.open(animation=False);settle()
        self.city.tavern_button.dispatch('on_release');settle()
        self.assertIsNotNone(self.city.bartender.texture)
        journal=self.city.journal
        self.assertEqual(journal.tavern_city,3)
        journal.cards.pages[0].buttons.children[0].dispatch('on_release');settle()
        self.assertIsNotNone(q.state(self.db,'Север'))

    def test_roster_row_opens_unit_statistics(self):
        row=self.city.army_box.rows.children[0]
        row.inspect();settle()
        self.assertIsNotNone(row.details_popup.parent)


class TownDataTests(unittest.TestCase):
    def test_faction_sides_and_portrait_routing(self):
        db=fixture();self.addCleanup(db.close)
        w.enter(db,'Север','Home')
        q.begin(db,'Север',random.Random(5))
        self.assertEqual(q.details(q.state(db,'Север'))['war']['sides'],list(CONFLICT_SIDES['Север']))
        for faction in THEMES:
            self.assertIn('/women/archer',image_path(faction,'units','archer'))
            self.assertIn('/women/boss',image_path(faction,'units','boss'))
            self.assertIn('/units/sentinel',image_path(faction,'units','sentinel'))
            self.assertIn('/units/rider',image_path(faction,'units','rider'))
            self.assertIn('/units/golem',image_path(faction,'units','golem'))

    def test_old_allegiance_and_routes_survive_renaming_without_rebalancing_units(self):
        db=fixture();self.addCleanup(db.close)
        w.enter(db,'Север','Home');w.recruit(db,'Север',2,17)
        q.begin(db,'Север',random.Random(8))
        run=q.state(db,'Север');data=q.details(run)
        data['war']['sides']=['Старая сторона','Другой двор']
        db.execute("UPDATE portal_quest_runs SET scenario=?,war=1,side='Другой двор'",(json.dumps(data),))
        db.execute("UPDATE units SET attack=999 WHERE unit_name LIKE 'Странник:%'")
        db.execute('UPDATE portal_presentation SET version=5')
        before=list(db.execute('SELECT city_name,unit_name,unit_count,experience FROM garrisons'))
        w.upgrade_world(db)
        updated=q.state(db,'Север')
        self.assertEqual(updated['side'],'Клан Грома')
        self.assertEqual(updated['war'],1)
        self.assertEqual(q.details(updated)['detective'],data['detective'])
        self.assertEqual(q.details(updated)['war']['supplies'],data['war']['supplies'])
        self.assertEqual(list(db.execute('SELECT city_name,unit_name,unit_count,experience FROM garrisons')),before)
        self.assertEqual(db.execute("SELECT attack FROM units WHERE unit_name LIKE 'Странник:%'").fetchone()[0],999)

    def test_fog_anchors_move_as_a_shared_front_and_fade_at_wrap(self):
        deltas=[]
        for anchor in ((300,650),(700,600),(1000,720)):
            first=fog_front(anchor,2);second=fog_front(anchor,5)
            deltas.append(second[0]-first[0])
            self.assertGreater(second[0],first[0])
        self.assertAlmostEqual(deltas[0],deltas[1]);self.assertAlmostEqual(deltas[1],deltas[2])
        self.assertAlmostEqual(fog_front((500,700),24*(1-.18))[2],0,places=6)
