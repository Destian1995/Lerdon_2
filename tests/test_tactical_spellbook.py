"""Real touch layouts, cooldowns and ability selection under the global theme."""
from pathlib import Path
import unittest

import test_tactical_battle_ui as ui_fixture
from kivy.metrics import Metrics
from test_tactical_combat import unit
from tactical_battle_ui import TacticalBattlePopup
from tactical_combat import TacticalBattle
from tactical_spellbook_ui import AbilityBook,ICONS,INK,ROOT
from tactical_abilities import ABILITIES
from window_theme import theme_tree


class SpellbookTests(unittest.TestCase):
    def setUp(self):
        ui_fixture.TacticalUITests.setUp(self)
        self.metrics=Metrics.density,Metrics.fontscale

    def tearDown(self):
        ui_fixture.TacticalUITests.tearDown(self)
        Metrics.density,Metrics.fontscale=self.metrics

    def book(self,name='Владислав'):
        model=TacticalBattle([unit(name,1,cls=3,initiative=100),unit('Солдаты',1000)],
                             [unit('Враг',1000)],biome='forest')
        view=TacticalBattlePopup(model,'attacker',lambda _:None)
        self.views.append(view);view.deploying=False;view.open(animation=False);ui_fixture.settle()
        view.clock_event.cancel();view.clock_event=None
        book=view.show_skills();self.views.append(book);ui_fixture.settle()
        return view,book

    def test_two_pages_controls_and_ink_fit_small_screens_and_large_ui_scale(self):
        for size,density in (((640,360),1),((568,320),1),((360,640),1),((800,480),1.5)):
            Metrics.density=density;ui_fixture.Window.size=size;ui_fixture.settle()
            view,book=self.book()
            self.assertEqual(set(book.tiles),{'snipe','burst','grenade'})
            for button in (book.cast,book.cancel):
                self.assertGreaterEqual(button.height,44*density)
                self.assertGreaterEqual(button.x,0)
                self.assertLessEqual(button.right,ui_fixture.Window.width+1)
                self.assertGreaterEqual(button.y,0)
                self.assertLessEqual(button.top,ui_fixture.Window.height+1)
            for tile in book.tiles.values():self.assertGreaterEqual(tile.height,62*density)
            theme_tree(book.content);theme_tree(book.content)
            self.assertEqual(tuple(book.description.color),INK)
            self.assertEqual(tuple(book.tiles['grenade'].name.color),INK)
            book.select_skill('grenade')
            self.assertIn('союзников',book.warning.text)
            self.assertIn('15%',book.description.text)
            book.dismiss(animation=False);view.dismiss(animation=False);ui_fixture.settle()

    def test_browsing_does_not_cast_and_preparation_returns_to_targeting(self):
        view,book=self.book();battle=view.battle
        hp={key:s.hp for key,s in battle.stacks.items()};events=len(battle.events)
        age=view.age;view.tick(.1)
        self.assertEqual(view.age,age)
        book.tiles['grenade'].dispatch('on_release')
        self.assertEqual(book.selected,'grenade');self.assertIsNone(view.selected_skill)
        self.assertEqual(hp,{key:s.hp for key,s in battle.stacks.items()})
        self.assertEqual(len(battle.events),events)
        book.cast.dispatch('on_release');ui_fixture.settle()
        self.assertEqual(view.selected_skill,'grenade');self.assertIsNone(view.selection)
        self.assertFalse(view.help_open)

    def test_cooldown_can_be_inspected_but_cannot_be_prepared(self):
        view,book=self.book();view.battle.active.cooldowns['grenade']=view.battle.round+2
        book.select_skill('grenade');self.assertTrue(book.cast.disabled)
        self.assertIn('2 р.',book.availability.text)
        book.choose('grenade');self.assertIsNone(view.selected_skill)
        self.assertIsNotNone(book.parent)

    def test_army_spell_preselects_hero_and_owner_close_removes_book(self):
        view,book=self.book('Изабэлл');book.select_skill('vampirism')
        book.choose('vampirism');ui_fixture.settle()
        self.assertEqual(view.selection,view.battle.active.pos)
        second=view.show_skills();self.views.append(second);ui_fixture.settle()
        self.assertIsNone(view.show_skills())
        view.dismiss(animation=False);ui_fixture.settle()
        self.assertIsNone(second.parent);self.assertFalse(view.help_open)

    def test_every_ability_has_an_existing_illustration(self):
        self.assertEqual(set(ICONS),set(ABILITIES))
        for icon in ICONS.values():self.assertTrue((ROOT/'files/pict/artifacts'/icon).is_file())


if __name__=='__main__':unittest.main()
