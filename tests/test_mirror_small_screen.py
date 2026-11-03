import random
import unittest
from types import SimpleNamespace
from unittest.mock import Mock,patch
from kivy.core.text import Label as CoreLabel
from kivy.metrics import Metrics
from kivy.uix.popup import Popup
from kivy.uix.scrollview import ScrollView
from strategy_ui_fixture import Window
from test_dialog_layout import settle
from test_otherworlds import fixture
from window_theme import install_window_theme
from otherworld_ui import OtherworldMap,ForeignCityPopup
from otherworld_quest_ui import QuestJournal
from mirror_layout import FitLabel,FitButton
import otherworlds as w
import otherworld_quests as q


class MirrorSmallScreenTests(unittest.TestCase):
    def setUp(self):
        self.size=Window.size;self.metrics=(Metrics.density,Metrics.fontscale)
        self.db=fixture();self.addCleanup(self.db.close)
        w.enter(self.db,'Север','Home')
        for i in range(1,6):w.recruit(self.db,'Север',i)
        install_window_theme();Metrics.density=1
        Window.size=(640,360);settle()
        self.owner=OtherworldMap(self.db,'Север');self.owner.open(animation=False);settle()

    def tearDown(self):
        for popup in list(Window.children):
            if isinstance(popup,Popup):popup.dismiss(animation=False)
        settle();Metrics.density,Metrics.fontscale=self.metrics
        Window.size=self.size;settle()

    def inside(self,widget,parent):
        self.assertGreaterEqual(widget.x,parent.x-1)
        self.assertGreaterEqual(widget.y,parent.y-1)
        self.assertLessEqual(widget.right,parent.right+1)
        self.assertLessEqual(widget.top,parent.top+1)

    def readable(self,root):
        for label in root.walk():
            if not isinstance(label,(FitLabel,FitButton)) or not label.text or not label.height:continue
            inset=12 if isinstance(label,FitButton) else 0
            text=CoreLabel(text=label.text,font_name=label.font_name,font_size=label.font_size,
                           bold=label.bold,text_size=(max(1,label.width-inset),None))
            text.refresh()
            self.assertLessEqual(text.texture.height,label.height-(6 if isinstance(label,FitButton) else 1)+.01,
                                 (label.text,label.size,label.font_size,text.texture.height))

    def test_goods_and_army_are_readable_one_card_at_a_time(self):
        city=ForeignCityPopup(self.owner,w.cities(self.db,'Север')[0]);city.open(animation=False);settle()
        for size,density in [((640,360),1),((1280,576),2),((390,844),1)]:
            Window.size=size;Metrics.density=density;settle();city.fit();settle()
            for mode in ('units','artifacts','resources'):
                with self.subTest(size=size,density=density,mode=mode):
                    city.show_market(mode);settle()
                    self.assertEqual(len(city.offers.pages),2 if mode=='resources' else 5)
                    self.assertEqual(len(city.army_box.pages),7)
                    for index,card in enumerate(city.offers.pages):
                        city.offers.select(index);settle()
                        self.assertIs(city.offers.carousel.current_slide,card)
                        self.inside(card.button,card)
                        self.assertGreaterEqual(card.button.height,36)
                        self.assertGreaterEqual(card.title_label.font_size,12)
                        self.readable(card)
                    self.assertEqual(city.offers.counter.text,f'{len(city.offers.pages)} / {len(city.offers.pages)}')
                    city.army_box.select(6);settle()
                    self.assertIs(city.army_box.carousel.current_slide,city.army_box.pages[6])
                    self.inside(city.guard_label,city.army_panel)
                    self.inside(city.action_bar,city.root)
                    self.readable(city.army_box.carousel.current_slide)

    def test_accusation_choices_and_quests_can_be_paged(self):
        q.begin(self.db,'Север',random.Random(54))
        d=q.details(q.state(self.db,'Север'))['detective']
        for place,kind in zip(d['cities'],('witness','ledger')):
            self.db.execute('UPDATE portal_parties SET city_id=?',(place,));self.db.commit()
            q.action(self.db,'Север',kind)
        journal=QuestJournal(self.owner);journal.open(animation=False);settle()
        self.assertEqual(len(journal.cards.pages),2)
        for index,card in enumerate(journal.cards.pages):
            journal.cards.select(index);settle()
            self.assertIs(journal.cards.carousel.current_slide,card)
            for button in card.buttons.children:self.inside(button,card)
            self.readable(card)
        # A repeat run can still have the previous cap buff plus an unclaimed
        # war reward while the detective case is at its accusation stage.
        war=q.details(q.state(self.db,'Север'))['war']
        self.db.execute("UPDATE portal_quest_runs SET war=3,side=? WHERE faction='Север'",(war['sides'][0],))
        self.db.execute("INSERT INTO portal_quest_rewards VALUES('Север',1,102,NULL)")
        self.db.execute("INSERT INTO portal_quest_buffs VALUES('Север',25)");self.db.commit()
        journal.refresh();settle()
        self.assertEqual(len(journal.cards.pages),4)
        for index,card in enumerate(journal.cards.pages):
            journal.cards.select(index);settle();self.readable(card)

    def test_map_fills_window_and_zoomed_tap_drag_and_reset_keep_correct_city(self):
        m=self.owner.map
        self.assertGreater(m.height,self.owner.height*.90)
        self.assertGreater(m.width,self.owner.width*.95)
        self.owner.zoom_plus.dispatch('on_release');settle()
        m.set_zoom(1.5);m.camera.move(35,20);m.redraw_camera();settle()
        for x,y,_,city in m.hits:
            self.assertEqual((x,y),m.point(city['x'],city['y']))
        x,y,_,city=m.hits[5]
        touch=SimpleNamespace(uid='tap',pos=(x,y),x=x,y=y,grab=Mock(),ungrab=Mock())
        with patch('otherworld_ui.ForeignCityPopup') as popup:
            m.on_touch_down(touch);m.on_touch_up(touch)
            popup.assert_called_once_with(self.owner,city)
            popup.return_value.open.assert_called_once()
        before=m.camera.pan
        touch=SimpleNamespace(uid='drag',pos=(m.center_x,m.center_y),x=m.center_x,y=m.center_y,grab=Mock(),ungrab=Mock(),dx=25,dy=18)
        with patch('otherworld_ui.ForeignCityPopup') as popup:
            m.on_touch_down(touch)
            touch.pos=(touch.x+25,touch.y+18)
            m.on_touch_move(touch);m.on_touch_up(touch)
            popup.assert_not_called()
        self.assertNotEqual(m.camera.pan[0],before[0]);self.assertNotEqual(m.camera.pan[1],before[1])
        self.owner.zoom_label.dispatch('on_release')
        self.assertEqual(m.camera.zoom,1);self.assertEqual(m.camera.pan,(0,0))
        for widget in (self.owner.header,self.owner.action_bar):self.inside(widget,self.owner.stage)


if __name__=='__main__':unittest.main()
