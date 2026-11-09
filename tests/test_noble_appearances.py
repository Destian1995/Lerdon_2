"""Distinct named nobles, legacy saves and companion portrait continuity."""
import hashlib
import itertools
import json
from pathlib import Path
import random
import sqlite3
import unittest

from test_otherworlds import fixture
import mirror_monster_quest as hunt
import otherworlds as worlds


class NobleAppearanceTests(unittest.TestCase):
    def case(self,faction,names,culprit=0):
        return dict(faction=faction,scenario=json.dumps(dict(nobles=[dict(name=n) for n in names],culprit=culprit)))

    def test_every_possible_legacy_lineup_has_three_distinct_correct_portraits(self):
        paths=set()
        for faction,roster in hunt.NOBLES.items():
            for names in itertools.combinations(roster,3):
                case=self.case(faction,names)
                portraits=[hunt.noble_portrait(case,n) for n in names]
                self.assertEqual(len(set(portraits)),3,(faction,names))
                for name,path in zip(names,portraits):
                    self.assertTrue(Path(path).is_file(),path)
                    identity=hunt.noble_identity(faction,name)
                    self.assertIn('noble-'+identity['gender'],path)
                    self.assertEqual(path,hunt.noble_image(self.case(faction,[name])))
                paths.update(portraits)
        self.assertEqual(len(paths),30)
        self.assertEqual(len({hashlib.sha256(Path(p).read_bytes()).digest() for p in paths}),30)

    def test_saved_identity_survives_reordering_and_has_no_random_selection(self):
        faction=next(iter(hunt.NOBLES));names=hunt.NOBLES[faction]
        case=self.case(faction,names[:3]);story=json.loads(case['scenario'])
        for n in story['nobles']:n.update(hunt.noble_identity(faction,n['name']))
        case['scenario']=json.dumps(story)
        before={n:hunt.noble_portrait(case,n) for n in names[:3]}
        story['nobles'].reverse();case['scenario']=json.dumps(story)
        self.assertEqual(before,{n:hunt.noble_portrait(case,n) for n in names[:3]})

    def test_gender_override_keeps_appearance_and_does_not_change_other_suspects(self):
        for faction,names in hunt.NOBLES.items():
            for i,name in enumerate(names):
                case=self.case(faction,names,i);story=json.loads(case['scenario'])
                before=[hunt.noble_portrait(case,n) for n in names]
                gender='lord' if i%2 else 'lady'
                story['companion_gender']=gender;case['scenario']=json.dumps(story)
                self.assertEqual(before,[hunt.noble_portrait(case,n) for n in names])
                self.assertEqual(hunt.noble_image(case),hunt.noble_portrait(case,name,gender=gender))
                self.assertTrue(Path(hunt.noble_image(case)).is_file())
                self.assertIn('noble-'+gender,hunt.noble_image(case))

    def test_new_case_persists_identities_and_companion_keeps_culprit_face(self):
        faction=next(iter(hunt.NOBLES));db=fixture();self.addCleanup(db.close)
        db.executescript('CREATE TABLE season(id,season_index); INSERT INTO season VALUES(1,0);')
        worlds.enter(db,faction,'Home');hunt.begin(db,faction,random.Random(3))
        case=hunt.state(db,faction);story=json.loads(case['scenario'])
        for n in story['nobles']:
            self.assertEqual({k:n[k] for k in ('gender','appearance')},hunt.noble_identity(faction,n['name']))
        expected=hunt.noble_portrait(case,hunt.noble_name(case))
        db.execute('UPDATE portal_parties SET city_id=?',(case['city_id'],))
        hunt.investigate(db,faction);hunt.investigate(db,faction)
        hunt.accuse(db,faction,hunt.noble_name(case));prize=hunt.claim_heart(db,faction,'Hero')
        self.assertEqual(prize['image'],expected)
        hunt.set_form(db,faction,'monster');self.assertEqual(hunt.set_form(db,faction,'noble')['image'],expected)
        saved=sqlite3.connect(':memory:');self.addCleanup(saved.close);db.commit();db.backup(saved)
        self.assertEqual(hunt.noble_image(hunt.state(saved,faction)),expected)
        for conn in (db,saved):
            form=hunt.companion_form(conn,faction)
            self.assertEqual(conn.execute('SELECT image_path FROM units WHERE unit_name=?',(form['unit_name'],)).fetchone()[0],expected)


if __name__=='__main__':unittest.main()
