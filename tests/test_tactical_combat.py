import copy
import unittest

from tactical_combat import TacticalBattle, make_field, TERRAINS


def unit(name='Воин',count=100,kind='infantry',attack=100,defense=100,initiative=50,cls=1):
    return dict(unit_name=name,unit_count=count,units_stats={
        'Урон':attack,'Защита':defense,'Живучесть':0,'Тип':kind,
        'Класс юнита':cls,'Инициатива':initiative,'Крит':0})


def battle(a=None,b=None):
    model = TacticalBattle(a or [unit(initiative=100)],b or [unit('Враг')],
                           terrain={(x,y):'plain' for x in range(10) for y in range(6)})
    return model,model.stacks['attacker:0'],model.stacks['defender:0']


class TacticalCombatTests(unittest.TestCase):
    def test_full_armies_deploy_without_overlap_on_rectangular_field(self):
        m=TacticalBattle([unit(str(i)) for i in range(30)],
                         [unit('enemy'+str(i)) for i in range(30)])
        self.assertEqual(len({s.pos for s in m.stacks.values()}),60)
        self.assertTrue(all(s.pos in m.terrain for s in m.stacks.values()))
        for side in ('attacker','defender'):
            self.assertTrue(all(s.pos in m.deployment_cells(side) for s in m.stacks.values() if s.side==side))

    def test_protected_enemy_heroes_do_not_block_archers_like_in_reported_screenshot(self):
        archer=unit('Охотники',13500,kind='archer',initiative=100)
        archer['unit_image']='files/army/people/predator.jpg'
        defenders=[unit('Бестии',69000),unit('Изабэлл',1,cls=3),unit('Дитрих Фрост',1,cls=3)]
        m=TacticalBattle([archer],defenders,terrain={(x,y):'plain' for x in range(10) for y in range(6)})
        a,b,h1,h2=list(m.stacks.values())
        a.pos=(0,4);b.pos=(2,4);h1.pos=(1,3);h2.pos=(1,5)
        self.assertTrue(m.protected(h1));self.assertTrue(m.protected(h2))
        self.assertFalse(m.engaged(a))
        for x in range(2,8):
            b.pos=(x,4)
            self.assertTrue(m.can_attack(a,b),x)
        b.pos=(2,4);before=b.hp
        m.attack(b.id)
        self.assertLess(b.hp,before)

    def test_protected_hero_does_not_pin_movement_but_ordinary_troops_still_do(self):
        m,a,b=battle([unit(kind='archer',initiative=100)],[unit('Враг'),unit('Герой',1,cls=3)])
        h=m.stacks['defender:1']
        a.pos=(1,4);b.pos=(5,4);h.pos=(2,5)
        self.assertTrue(m.can_attack(a,b))
        self.assertIn((2,4),m.reachable())
        b.pos=(2,4)
        self.assertTrue(m.engaged(a))
        h.pos=(5,4)
        h.unit['units_stats']['Класс юнита']=1
        self.assertIn('соседний',m.attack_block_reason(a,h))

    def test_faction_type_does_not_turn_elven_archers_into_melee_troops(self):
        archer=unit(kind='infantry',initiative=100)
        archer['unit_image']='files/army/elfs/archer.jpg'
        m,a,b=battle([archer])
        a.pos=(1,4);b.pos=(5,4)
        self.assertEqual(a.kind,'infantry')
        self.assertEqual(a.role,'archer')
        self.assertTrue(m.can_attack(a,b))

    def test_deployment_stays_in_own_zone_and_swaps_friendly_stacks(self):
        m,a,b=battle([unit(initiative=100),unit('Другой')])
        other=m.stacks['attacker:1'];old=a.pos
        m.deploy(a.id,other.pos)
        self.assertEqual(other.pos,old)
        with self.assertRaises(ValueError):m.deploy(a.id,(5,5))
        m.defend()
        with self.assertRaises(ValueError):m.deploy(a.id,old)

    def test_ai_takes_long_detour_instead_of_stopping_at_a_cliff(self):
        m,a,b=battle()
        a.pos=(3,0);b.pos=(7,0)
        for y in range(4):m.terrain[5,y]='rock'
        first=m.ai_step()
        self.assertEqual(first['action'],'walk')
        self.assertGreater(a.pos[1],0)
        for _ in range(1200):
            if m.winner:break
            m.ai_step()
        self.assertIsNotNone(m.winner)
        self.assertTrue(any(e['action']=='attack' for e in m.events))

    def test_field_has_60_cells_mirrored_obstacles_and_open_crossings(self):
        for seed in range(40):
            for biome in ('plains','highland','lowland','snow'):
                field = make_field(seed,biome)
                self.assertEqual(len(field),60)
                for (x,y),kind in field.items():
                    self.assertEqual(kind,field[9-x,y])
                    if y in (2,4):
                        self.assertFalse(TERRAINS[kind].blocked)

    def test_weighted_path_routes_around_rocks_and_respects_budget(self):
        m,a,b = battle()
        a.pos = (1,1)
        m.terrain[2,1]='rock'
        m.terrain[1,2]='swamp'
        reachable = m.reachable()
        self.assertNotIn((2,1),reachable)
        self.assertEqual(reachable[1,2][0],30)
        self.assertTrue(all(cost<=a.mp for cost,path in reachable.values()))
        start = a.mp
        event = m.move((3,1))
        self.assertEqual(a.pos,(3,1))
        self.assertLess(a.mp,start)
        self.assertNotIn((2,1),event['path'])

    def test_cannot_cut_diagonal_corner_or_move_through_units(self):
        m,a,b = battle()
        a.pos=(0,0);b.pos=(0,1)
        m.terrain[1,0]='rock'
        self.assertEqual(m.reachable(),{})

    def test_entering_enemy_zone_ends_movement_and_no_teleport(self):
        m,a,b = battle()
        a.pos=(1,4);b.pos=(4,4)
        m.move((3,4))
        self.assertEqual(a.mp,0)
        self.assertEqual(m.reachable(),{})
        with self.assertRaises(ValueError):m.move((2,4))

    def test_ranged_los_range_engagement_and_hill(self):
        m,a,b = battle([unit(kind='archer',initiative=100)])
        a.pos=(1,4);b.pos=(7,4)
        self.assertTrue(m.can_attack(a,b))
        m.terrain[4,4]='forest'
        self.assertFalse(m.can_attack(a,b))
        m.terrain[4,4]='hill'
        self.assertFalse(m.can_attack(a,b))
        m.terrain[a.pos]='hill'
        self.assertTrue(m.can_attack(a,b))
        b.pos=(9,4)
        self.assertFalse(m.can_attack(a,b))
        b.pos=(8,4)
        self.assertTrue(m.can_attack(a,b))
        m.terrain[a.pos]='plain'
        self.assertFalse(m.can_attack(a,b))
        m.terrain[4,4]='plain'
        self.assertTrue(m.can_attack(a,b))

    def test_forest_cover_guard_distance_and_move_reduce_damage(self):
        m,a,b = battle([unit(kind='archer',initiative=100)])
        a.pos=(1,4);b.pos=(4,4)
        baseline=m.preview(b)['min_damage']
        m.terrain[b.pos]='forest'
        self.assertLess(m.preview(b)['min_damage'],baseline)
        m.terrain[b.pos]='plain'
        b.guarding=True
        self.assertLess(m.preview(b)['min_damage'],baseline)
        b.guarding=False;b.pos=(7,4)
        far=m.preview(b)['min_damage']
        self.assertEqual(far,baseline)
        a.moved=1
        self.assertLess(m.preview(b)['min_damage'],far)

    def test_preview_does_not_consume_random_or_change_health(self):
        m,a,b=battle()
        a.pos=(3,4);b.pos=(4,4)
        state=m.rng.getstate(); hp=b.hp
        self.assertEqual(m.preview(b),m.preview(b))
        self.assertEqual(m.preview(b)['critical_chance'],0)
        self.assertEqual(m.rng.getstate(),state)
        self.assertEqual(b.hp,hp)

    def test_melee_retaliates_once_ranged_and_dead_targets_do_not(self):
        m,a,b=battle([unit(initiative=100),unit('Второй',initiative=90)])
        a.pos=(3,4);b.pos=(4,4)
        other=m.stacks['attacker:1'];other.pos=(3,5)
        event=m.attack(b.id)
        self.assertEqual(len(event['strikes']),2)
        self.assertTrue(b.retaliated)
        self.assertEqual(m.active,other)
        self.assertEqual(len(m.attack(b.id)['strikes']),1)
        m,a,b=battle([unit(attack=1e9,initiative=100)])
        a.pos=(3,4);b.pos=(4,4)
        self.assertEqual(len(m.attack(b.id)['strikes']),1)
        self.assertEqual(m.winner,'attacker')
        m,a,b=battle([unit(kind='archer',initiative=100)])
        a.pos=(1,4);b.pos=(4,4)
        self.assertEqual(len(m.attack(b.id)['strikes']),1)

    def test_single_hero_accumulates_wounds_instead_of_minimum_one_death(self):
        m,a,b=battle([unit(attack=1,initiative=100)],[unit(count=1,cls=3,defense=1000)])
        a.pos=(3,4);b.pos=(4,4)
        old=b.hp
        m.attack(b.id)
        self.assertEqual(b.count,1)
        self.assertLess(b.hp,old)

    def test_wait_once_guard_duration_and_round_initiative(self):
        m,a,b=battle()
        self.assertIs(m.active,a)
        m.wait()
        self.assertIs(m.active,b)
        m.defend()
        self.assertIs(m.active,a)
        self.assertTrue(b.guarding)
        with self.assertRaises(ValueError):m.wait()
        m.defend()
        self.assertEqual(m.round,2)
        self.assertIs(m.active,a)
        self.assertFalse(a.guarding)
        self.assertTrue(b.guarding)

    def test_all_ai_battles_finish_reproducibly_and_do_not_mutate_input(self):
        armies=([unit(kind='archer'),unit('Герой',count=1,cls=3,attack=200,defense=300)],
                [unit(kind='cavalry'),unit('Маг',kind='mage')])
        before=copy.deepcopy(armies)
        results=[]
        for _ in range(2):
            m=TacticalBattle(*armies,seed=73)
            for step in range(5000):
                if m.winner:break
                m.ai_step()
                occupied=[s.pos for s in m.stacks.values() if s.alive]
                self.assertEqual(len(occupied),len(set(occupied)))
            self.assertIsNotNone(m.winner)
            results.append((m.winner,[(s.count,s.hp) for s in m.stacks.values()],m.events))
        self.assertEqual(results[0],results[1])
        self.assertEqual(armies,before)

    def test_apply_requires_finished_battle_and_preserves_metadata(self):
        attackers=[unit(attack=1e9,initiative=100)];defenders=[unit()]
        m,a,b=battle(attackers,defenders)
        with self.assertRaises(ValueError):m.apply_to(attackers,defenders)
        a.pos=(3,4);b.pos=(4,4)
        m.attack(b.id)
        m.apply_to(attackers,defenders)
        self.assertEqual(defenders[0]['unit_count'],0)
        self.assertEqual(defenders[0]['killed_count'],100)
        self.assertEqual(attackers[0]['units_stats']['Урон'],1e9)


if __name__=='__main__':unittest.main()
