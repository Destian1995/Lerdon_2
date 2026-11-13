"""Regressions for the turn-14 collapse: income, champions and army growth."""
from contextlib import redirect_stdout
import io
import random
import unittest
from types import SimpleNamespace

from ai_economy import supply_reserve,tax_policy
from tools.ai_army_audit import simulate,extracted,snapshot


class ArmyRecoveryTests(unittest.TestCase):
    def test_production_is_not_treated_as_a_recruitment_cap(self):
        ai=SimpleNamespace(total_consumption=500,food_info=5000,food_peoples=2000,
            factories=5,load_political_system=lambda:'Борьба')
        self.assertEqual(supply_reserve(ai),100)

    def test_tax_policy_collects_revenue_before_food_shortage_ruins_growth(self):
        ai=SimpleNamespace(faction='Север',resources={'Население':1000},turn=2,factories=3,total_consumption=0)
        self.assertEqual(tax_policy(ai),0)
        ai.resources['Население']=10000
        self.assertEqual(tax_policy(ai),34)

    def test_recreated_controller_resumes_campaign_instead_of_build_only_turn(self):
        db=snapshot();self.addCleanup(db.close)
        db.execute('DELETE FROM turn');db.execute("INSERT INTO turn VALUES('Север',14)")
        with redirect_stdout(io.StringIO()):ai=extracted('ii.py','AIController')('Элины',db)
        self.assertEqual(ai.turn,13)

    def test_workers_are_credited_after_loading_previous_balances(self):
        from test_ai_economy import AIEconomyTests
        fixture=AIEconomyTests();fixture.setUp();self.addCleanup(fixture.tearDown)
        ai=fixture.ai
        ai.cities=ai.load_cities()
        ai.army_limit=ai.calculate_army_limit()
        ai.resources['Рабочие']=10;ai.resources['Кристаллы']=100000
        ai.save_resources_to_db()
        ai.update_resources()
        self.assertGreater(ai.resources['Рабочие'],10)

    def test_struggle_faction_can_build_hero_army_and_equipment_by_turn_fifteen(self):
        random.seed(23)
        with redirect_stdout(io.StringIO()):result=simulate('Элины',system='Борьба',turns=15)
        final=result['history'][-1]
        self.assertIn('Арн-гот',final['heroes'])
        self.assertGreater(final['soldiers'],1000)
        self.assertGreaterEqual(final['artifacts'],1)
        self.assertGreater(final['power'],10000000)

    def test_submission_faction_fields_equipped_army_by_turn_fifteen(self):
        random.seed(23)
        with redirect_stdout(io.StringIO()):result=simulate('Эльфы',system='Смирение',turns=15)
        final=result['history'][-1]
        self.assertIn('Валерия',final['heroes'])
        self.assertGreater(final['soldiers'],1000)
        self.assertGreaterEqual(final['artifacts'],1)
        self.assertGreater(final['power'],10000000)


if __name__=='__main__':unittest.main()
