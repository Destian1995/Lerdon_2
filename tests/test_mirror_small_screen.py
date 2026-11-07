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
        self.size=Window.size;self.metrics=(max(1,Metrics.density),Metrics.fontscale)
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
        city.open_market();settle()
        for size,density in [((640,360),1),((1280,576),2),((390,844),1)]:
            Window.size=size;Metrics.density=density;settle();city.fit();settle()
            for mode in ('artifacts','resources'):
                with self.subTest(size=size,density=density,mode=mode):
                    city.show_market(mode);settle()
                    self.assertEqual(len(city.offers.pages),0)
                    self.assertEqual(len(city.army_box.rows.children),7)
                    if mode=='resources':
                        self.assertEqual(len(city.crystal_market.panels),2)
                        for panel in city.crystal_market.panels:
                            self.inside(panel.button,panel)
                            self.assertGreaterEqual(panel.button.height,48*density)
                            self.assertGreaterEqual(panel.price.height,panel.price.texture_size[1])
                        self.assertEqual(city.crystal_market.cards.cols,1 if size[0]==390 else 2)
                    else:self.assertEqual(len(city.artifact_shop.rows.children),5)
                    row=city.army_box.rows.children[0]
                    city.army_box.scroll_to(row,animate=False);settle()
                    self.inside(city.guard_label,city.city_titles)
                    self.inside(city.action_bar,city.root)
                    self.readable(row)

    def test_accusation_choices_and_quests_can_be_paged(self):
        q.begin(self.db,'Север',random.Random(54))
        d=q.details(q.state(self.db,'Север'))['detective']
        for place,kind in zip(d['cities'],('witness','ledger')):
            self.db.execute('UPDATE portal_parties SET city_id=?',(place,));self.db.commit()
            q.action(self.db,'Север',kind,d['search_sites'][d['search_answer']] if kind=='ledger' else None)
        journal=QuestJournal(self.owner);journal.open(animation=False);settle()
        self.assertEqual(len(journal.cards.pages),3)
        for index,card in enumerate(journal.cards.pages):
            journal.cards.select(index);settle()
            self.assertIs(card.parent,journal.cards.detail_host)
            for button in card.buttons.children:
                self.assertIs(button.parent,card.buttons)
                self.assertGreaterEqual(button.height,44)
            self.assertGreaterEqual(card.scroll.height,40)
            self.readable(card)
        # A repeat run can still have the previous cap buff plus an unclaimed
        # war reward while the detective case is at its accusation stage.
        war=q.details(q.state(self.db,'Север'))['war']
        self.db.execute("UPDATE portal_quest_runs SET war=3,side=? WHERE faction='Север'",(war['sides'][0],))
        self.db.execute("INSERT INTO portal_quest_rewards VALUES('Север',1,102,NULL)")
        self.db.execute("INSERT INTO portal_quest_buffs VALUES('Север',25)");self.db.commit()
        journal.refresh();settle()
        self.assertEqual(len(journal.cards.pages),5)
        for index,card in enumerate(journal.cards.pages):
            journal.cards.select(index);settle();self.readable(card)

    def test_map_fills_window_and_keeps_fixed_view_while_city_taps_work(self):
        m=self.owner.map
        self.assertGreater(m.height,self.owner.height*.90)
        self.assertGreater(m.width,self.owner.width*.95)
        self.assertFalse(hasattr(self.owner,'zoom_controls'))
        m.set_zoom(1.5);m.camera.move(35,20);m.redraw_camera();settle()
        self.assertEqual(m.camera.zoom,1);self.assertEqual(m.camera.pan,(0,0))
        wheel=SimpleNamespace(pos=m.center,x=m.center_x,y=m.center_y,
                              is_mouse_scrolling=True,button='scrollup')
        m.on_touch_down(wheel)
        self.assertEqual(m.camera.zoom,1)
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
        self.assertEqual(m.camera.pan,before)
        fingers=[SimpleNamespace(uid=str(i),pos=(m.center_x+i*30,m.center_y),
                                 x=m.center_x+i*30,y=m.center_y,grab=Mock(),ungrab=Mock()) for i in (1,2)]
        for finger in fingers:m.on_touch_down(finger)
        fingers[0].pos=(m.center_x-60,m.center_y)
        m.on_touch_move(fingers[0])
        with patch('otherworld_ui.ForeignCityPopup') as popup:
            for finger in fingers:m.on_touch_up(finger)
            popup.assert_not_called()
        self.assertEqual(m.camera.zoom,1);self.assertEqual(m.camera.pan,(0,0))
        for widget in (self.owner.header,self.owner.action_bar):self.inside(widget,self.owner.stage)

    def test_recruitment_mixer_and_portraits_fit_phone_density_and_portrait(self):
        city=ForeignCityPopup(self.owner,w.cities(self.db,'Север')[0]);city.open(animation=False);settle()
        city.open_recruitment();session=city.recruitment;settle()
        for size,density in [((640,360),1),((1280,576),2),((392,844),1)]:
            Window.size=size;Metrics.density=density;session.fit();settle()
            card=session.cards[0]
            self.assertIsNotNone(card.portrait.texture)
            self.assertTrue(card.portrait._portrait_frame.visible)
            self.inside(card.controls,card)
            self.inside(card.mirror_scroll,card)
            self.assertGreaterEqual(card.quantity_slider.height,48*density)
            self.assertGreaterEqual(card.controls.height,48*density)


if __name__=='__main__':unittest.main()
