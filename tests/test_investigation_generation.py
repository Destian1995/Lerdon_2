import json
import random
import unittest
import itertools
from test_otherworlds import fixture
import otherworld_quests as quests
from otherworld_quest_pool import generate,legacy,search_hint,SEARCH_HINTS,DETECTIVE
from otherworld_themes import THEMES,theme


class InvestigationGenerationTests(unittest.TestCase):
    def test_correct_suspect_wins_in_every_evidence_pinning_order(self):
        import otherworlds as worlds
        for order in itertools.permutations(quests.EVIDENCE_ORDER):
            with self.subTest(order=order):
                db=fixture()
                try:
                    worlds.enter(db,'Север','Home');quests.begin(db,'Север',random.Random(42))
                    run=quests.state(db,'Север');d=quests.details(run)['detective']
                    db.execute('UPDATE portal_parties SET city_id=?',(d['cities'][0],))
                    quests.action(db,'Север','witness')
                    db.execute('UPDATE portal_parties SET city_id=?',(d['cities'][1],))
                    quests.action(db,'Север','ledger',d['search_sites'][d['search_answer']])
                    db.execute('UPDATE portal_parties SET city_id=?',(d['cities'][2],))
                    for key in order:quests.action(db,'Север','arrange',key)
                    before=list(db.execute('SELECT * FROM resources'))
                    quests.action(db,'Север','accuse',d['suspects'][run['culprit']])
                    self.assertEqual(quests.state(db,'Север')['detective'],3)
                    self.assertEqual(list(db.execute('SELECT * FROM resources')),before)
                finally:db.close()

    def test_each_faction_and_template_has_valid_persistent_destinations(self):
        db=fixture();self.addCleanup(db.close);quests.ensure_schema(db)
        for faction in THEMES:
            seen=set()
            for cycle in range(1,13):
                scenario=generate(db,faction,cycle,random.Random(cycle))
                d=scenario['detective'];names=theme(faction)['cities']
                seen.add(d['id'])
                self.assertEqual(len(set(d['cities'])),3)
                self.assertTrue(all(2<=city<=7 for city in d['cities']))
                run=dict(scenario=json.dumps(scenario),detective=0,culprit=cycle%3)
                hint=quests.detective_hint(run,faction)
                self.assertIn(names[d['cities'][0]-1],hint)
                self.assertNotIn(' · '+d['search_sites'][d['search_answer']],hint)
                run['detective']=1
                hint=quests.detective_hint(run,faction)
                self.assertIn(names[d['cities'][1]-1],hint)
                self.assertIn(search_hint(d),hint)
                self.assertNotIn(' · '+d['search_sites'][d['search_answer']],hint)
                run['detective']=2
                self.assertIn(names[d['cities'][2]-1],quests.detective_hint(run,faction))
            self.assertTrue({'missing_workers','silent_carriage','last_supper','night_watch'}<=seen)

    def test_hints_are_saved_and_never_replace_the_short_choice_names(self):
        db=fixture();self.addCleanup(db.close);quests.ensure_schema(db)
        for cycle in range(1,31):
            scenario=generate(db,'Север',cycle,random.Random(cycle))
            d=scenario['detective'];site=d['search_sites'][d['search_answer']]
            self.assertEqual(d['search_sites'],['Архив','Склад','Сад'])
            self.assertIn(search_hint(d),SEARCH_HINTS[site])
            self.assertEqual(search_hint(d),search_hint(json.loads(json.dumps(d))))
            # Older saves receive a deterministic clue without regenerating the case.
            old=dict(d);old.pop('search_hint')
            self.assertEqual(search_hint(old),SEARCH_HINTS[site][0])
            self.assertNotIn('Место поиска: '+site,quests.detective_hint(dict(scenario=json.dumps(scenario),detective=1),'Север'))

    def test_legacy_scenario_without_search_options_still_names_city(self):
        run=dict(scenario=None,detective=1,culprit=0)
        self.assertIn(theme('Север')['cities'][legacy()['detective']['cities'][1]-1],quests.detective_hint(run,'Север'))
