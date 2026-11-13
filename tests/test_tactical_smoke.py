import unittest
from test_tactical_abilities import arena
from tactical_abilities import ABILITIES


class SmokeTests(unittest.TestCase):
    def cloud(self):
        m,a,g,b,h=arena('Владислав')
        a.pos=(1,0);g.pos=(1,2);b.pos=(7,2);h.pos=(9,5)
        b.role='archer';a.role='archer'
        event=m.use_ability('smoke',(4,2))
        return m,a,g,b,h,event

    def test_replaces_hero_volley_without_replacing_soldier_ability(self):
        m,a,*_=arena('Владислав')
        self.assertIn('smoke',m.skills(a));self.assertNotIn('burst',m.skills(a))
        self.assertIn('auto_burst',ABILITIES)

    def test_smoke_is_one_way_and_deals_no_damage(self):
        m,a,g,b,h,event=self.cloud()
        self.assertEqual(event['strikes'],[])
        self.assertTrue(m.can_attack(a,b))
        self.assertFalse(m.can_attack(b,g))
        self.assertIn('Дым',m.attack_block_reason(b,g))
        self.assertTrue(m.visible_to(a.side,b))
        self.assertFalse(m.smoke_blocks(a.pos,b.pos,a.side))
        b.pos=(2,2)
        self.assertTrue(m.can_attack(b,g))

    def test_ranged_abilities_cannot_see_through_enemy_smoke(self):
        m,a,g,b,h,event=self.cloud()
        b.unit['unit_name']='Валерия';b.unit['units_stats']['Класс юнита']=3;m.queue=[b.id]
        self.assertFalse(m.ability_valid('drain',g.pos))
        b.pos=(2,2)
        self.assertTrue(m.ability_valid('drain',g.pos))

    def test_three_round_duration_and_terrain_is_not_modified(self):
        m,a,g,b,h,event=self.cloud();start=m.round
        self.assertEqual(m.terrain[4,2],'plain')
        for expected in (start+1,start+2):
            m._new_round();self.assertEqual(m.round,expected)
            self.assertTrue(m.smoke_clouds)
        m._new_round();self.assertFalse(m.smoke_clouds)
        self.assertTrue(m.can_attack(b,g))

    def test_clouds_do_not_prevent_movement_or_disappear_with_caster(self):
        m,a,g,b,h,event=self.cloud()
        b.pos=(6,2);m.queue=[b.id];b.mp=100
        self.assertIn((4,2),m.reachable(b))
        m.move((2,2));self.assertTrue(m.can_attack(b,g))
        a.hp=0;a.count=0
        self.assertTrue(m.smoke_blocks((7,2),g.pos,b.side))

    def test_silver_blade_has_exactly_45_percent_more_area_damage(self):
        m,a,g,b,h=arena('Агилар');b.pos=(4,4);g.pos=(3,3)
        old=b.hp;ally=g.hp
        expected=m.skill_power(a,True)*1.45/m._resistance(b)
        self.assertAlmostEqual(m.ability_power('whirlwind',a),m.skill_power(a,True)*1.45)
        m.use_ability('whirlwind',a.pos)
        self.assertAlmostEqual(old-b.hp,expected)
        self.assertEqual(g.hp,ally)
        self.assertEqual(ABILITIES['whirlwind'].name,'Серебряный клинок')

    def test_enemy_ai_moves_instead_of_shooting_through_smoke(self):
        m,a,g,b,h,event=self.cloud();m.queue=[b.id];b.mp=30
        event=m.ai_step()
        self.assertIn(event['action'],('walk','defend'))

    def test_ai_can_place_a_screen_without_an_enemy_inside_the_cloud(self):
        m,a,g,b,h=arena('Владислав');b.role='archer';b.pos=(8,4)
        a.cooldowns['snipe']=m.round+4
        a.cooldowns['grenade']=m.round+4
        self.assertEqual(m._ai_ability(a)[0],'smoke')

    def test_overlapping_hostile_clouds_keep_their_own_visibility(self):
        m,a,g,b,h,event=self.cloud()
        m.smoke_clouds.append(dict(side=b.side,cells=[(3,2)],expires=m.round+3,source=b.id))
        self.assertTrue(m.smoke_blocks((1,2),(7,2),a.side))
        self.assertTrue(m.smoke_blocks((1,2),(7,2),b.side))


import test_tactical_battle_ui as ui_fixture
from tactical_battle_ui import TacticalBattlePopup
from unittest.mock import Mock


class SmokeUITests(unittest.TestCase):
    setUp=ui_fixture.TacticalUITests.setUp
    tearDown=ui_fixture.TacticalUITests.tearDown

    def test_smoke_draws_on_phone_and_book_has_updated_abilities(self):
        ui_fixture.Window.size=(640,360);ui_fixture.settle()
        m,a,g,b,h,event=SmokeTests.cloud(self)
        view=TacticalBattlePopup(m,a.side,lambda _:None);self.views.append(view)
        view.deploying=False;view.audio=Mock()
        view.open(animation=False);ui_fixture.settle()
        if view.clock_event:view.clock_event.cancel();view.clock_event=None
        view.animate(event);view.tick(.1);view.board.draw()
        view.audio.play.assert_any_call('throw',owner=view)
        m.queue=[a.id];view.busy=0
        book=view.show_skills();self.views.append(book);ui_fixture.settle()
        self.assertIn('smoke',book.tiles);self.assertNotIn('burst',book.tiles)
        book.select_skill('smoke')
        self.assertIn('3 раунда',book.description.text)


if __name__=='__main__':unittest.main()
