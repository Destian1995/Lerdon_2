import random
import unittest
from strategy_ui_fixture import Window
from test_dialog_layout import settle
from test_otherworlds import fixture
from kivy.metrics import Metrics,dp,sp
from kivy.uix.popup import Popup
from otherworld_ui import OtherworldMap,ForeignCityPopup
from otherworld_quest_ui import QuestJournal
from mirror_readable_ui import ReadableText
from utils.garrison_stats import garrison_profiles
import otherworlds as w
import otherworld_quests as q


class ArchitectureTests(unittest.TestCase):
    def setUp(self):
        self.size=Window.size;self.metrics=Metrics.density,Metrics.fontscale
        Metrics.density=Metrics.fontscale=1;Window.size=(640,360);settle()
        self.db=fixture();w.enter(self.db,'Север','Home')
        w.recruit(self.db,'Север',1,10)
        self.owner=OtherworldMap(self.db,'Север');self.owner.open(animation=False);settle()

    def tearDown(self):
        for widget in list(Window.children):
            if isinstance(widget,Popup):widget.dismiss(animation=False)
        settle();self.db.close();Metrics.density,Metrics.fontscale=self.metrics
        Window.size=self.size;settle()

    def inside(self,a,b):
        self.assertGreaterEqual(a.x,b.x-1);self.assertGreaterEqual(a.y,b.y-1)
        self.assertLessEqual(a.right,b.right+1);self.assertLessEqual(a.top,b.top+1)

    def test_city_uses_schema_and_fixed_readable_fonts_at_android_metrics(self):
        city=ForeignCityPopup(self.owner,w.cities(self.db,'Север')[0]);city.open(animation=False);settle()
        for size,density,scale in (((640,360),1,1),((1280,576),2,1),((1280,576),2.5,1.2),((392,844),1,1)):
            Window.size=size;Metrics.density=density;Metrics.fontscale=scale;settle();city.fit();settle()
            self.inside(city.army_panel,city.root);self.inside(city.service_panel,city.root)
            self.assertEqual([b.text for b in reversed(city.services.children)],['Задания','Рынок','Найм'])
            self.assertTrue(city.bartender.texture)
            for button in city.services.children:
                self.inside(button,city.service_panel)
                self.assertGreaterEqual(button.height,dp(44)-1)
                self.assertGreaterEqual(button.font_size,sp(15)-.1)
            self.assertGreater(city.army_box.height,dp(48))
            first=list(reversed(city.army_box.rows.children))[0]
            self.assertEqual(first.name,'Hero')
            for row in city.army_box.rows.children:
                self.assertGreaterEqual(row.title.font_size,sp(15)-.1)
                self.assertGreaterEqual(row.stats.font_size,sp(14)-.1)
            self.inside(city.battle_button,city.army_panel)
            self.assertGreaterEqual(city.battle_button.font_size,sp(15)-.1)

    def test_journal_selects_tasks_from_left_and_actions_work_on_right(self):
        q.begin(self.db,'Север',random.Random(54))
        journal=QuestJournal(self.owner,tavern_city=1);journal.open(animation=False);settle()
        self.assertEqual(len(journal.cards.selectors),3)
        for size,density,scale in (((640,360),1,1),((1280,576),2,1),((1280,576),2.5,1.2),((392,844),1,1)):
            Window.size=size;Metrics.density=density;Metrics.fontscale=scale;settle();journal.fit();settle()
            self.inside(journal.cards.sidebar,journal.root);self.inside(journal.cards.detail_host,journal.root)
            self.inside(journal.close_button,journal.cards.sidebar)
            for i,button in enumerate(journal.cards.selectors):
                button.dispatch('on_release');settle()
                card=journal.cards.pages[i]
                self.assertIs(card.parent,journal.cards.detail_host)
                self.assertGreater(card.scroll.height,dp(35))
                self.assertGreaterEqual(card.heading.font_size,sp(17)-.1)
                for label in card.sections:self.assertGreaterEqual(label.font_size,sp(15)-.1)
        run=q.state(self.db,'Север');war=q.details(run)['war']
        self.db.execute("UPDATE portal_parties SET city_id=? WHERE faction='Север'",(war['embassy'],))
        journal.refresh();journal.cards.select(1);settle()
        card=journal.cards.pages[1]
        button=card.buttons.children[0];side=button.text.removeprefix('Поддержать: ')
        self.assertFalse(button.disabled);button.dispatch('on_release');settle()
        self.assertEqual(q.state(self.db,'Север')['side'],side)

    def test_map_buttons_are_compact_and_use_sp_fonts_on_android(self):
        Window.size=(1280,576);Metrics.density=2;settle();self.owner.fit();settle()
        self.assertLessEqual(self.owner.action_bar.height,dp(44)+1)
        for button in self.owner.action_bar.children:self.assertGreaterEqual(button.font_size,sp(15)-.1)
        self.assertFalse(hasattr(self.owner,'zoom_controls'))


class GuardRewardTests(unittest.TestCase):
    def test_every_regular_city_has_45_million_garrison_defense(self):
        db=fixture();self.addCleanup(db.close);w.enter(db,'Север','Home')
        for city in w.cities(db,'Север'):
            guard,target=w.guard_profile(db,'Север',city)
            self.assertIsNone(target)
            self.assertGreaterEqual(guard['defense']*guard['unit_count'],45_000_000)
            self.assertLess(guard['defense']*guard['unit_count'],45_000_000+guard['unit_count'])

    def test_victory_grants_three_percent_damage_for_nine_turns_and_expires(self):
        db=fixture();self.addCleanup(db.close);party=w.enter(db,'Север','Home')
        def win(attacker,guard,*args,**kwargs):guard['unit_count']=0
        result=w.fight_guards(db,'Север',skirmish=win)
        self.assertTrue(result['won']);self.assertEqual(w.guard_bonus_left(db,'Север'),9)
        plain=garrison_profiles(db,party['camp'],faction='Север')
        boosted=w.expedition_profiles(db,'Север',party['camp'])
        for name in plain:self.assertAlmostEqual(boosted[name]['attack'],plain[name]['attack']*1.03)
        db.execute('UPDATE turn SET turn_count=turn_count+9')
        self.assertEqual(w.guard_bonus_left(db,'Север'),0)
        self.assertEqual(w.expedition_profiles(db,'Север',party['camp']),garrison_profiles(db,party['camp'],faction='Север'))
