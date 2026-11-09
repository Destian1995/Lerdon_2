"""Every named noble uses an aligned animated cutout, including new appearances."""
import hashlib
import json
import math
from pathlib import Path
import unittest
from strategy_ui_fixture import Window
from tactical_battle_ui import SpriteLibrary,ASSETS
import mirror_monster_quest as hunt


class NobleSpriteTests(unittest.TestCase):
    def test_all_thirty_nobles_and_gender_changes_resolve_distinct_sprite_atlases(self):
        library=SpriteLibrary();self.addCleanup(library.clear)
        keys=set()
        for faction,names in hunt.NOBLES.items():
            for name in names:
                story=dict(nobles=[dict(name=name)],culprit=0)
                case=dict(faction=faction,scenario=json.dumps(story))
                image=hunt.noble_image(case);key=library.key(dict(unit_image=image))
                self.assertIsNotNone(key,image);keys.add(key)
                self.assertEqual(key,library.key(dict(image_path='C:/Game/'+image)))
                self.assertEqual(key,library.key(dict(unit_image=image.replace('/','\\'))))
                for gender in ('lord','lady'):
                    story['companion_gender']=gender;case['scenario']=json.dumps(story)
                    self.assertIsNotNone(library.key(dict(unit_image=hunt.noble_image(case))))
        self.assertEqual(len(keys),30)

    def test_new_appearances_play_six_actions_without_portrait_fallback(self):
        library=SpriteLibrary();self.addCleanup(library.clear)
        manifest=json.loads(Path('assets/noble-animation-prompts.json').read_text(encoding='utf-8'))
        self.assertEqual(len(manifest['sprites']),20)
        for row in manifest['sprites']:
            key=row['id'];unit=dict(unit_image=row['reference'])
            self.assertEqual(library.key(unit),key)
            metadata=json.loads((ASSETS/library.index['characters'][key]).read_text(encoding='utf-8'))
            self.assertEqual(metadata['grid'],[6,6])
            self.assertEqual(metadata['idle_registration']['shifts'][0],[0,0])
            for action in ('idle','walk','attack','hit','death','melee'):
                clip=metadata['animations'][action]
                first,offset,anchor=library.frame(unit,action,0)
                second,_,_=library.frame(unit,action,1.1/clip['fps'])
                self.assertIsNotNone(first);self.assertIsNot(first,second)
                self.assertEqual(tuple(first.size),tuple(metadata['frame_size']))
                self.assertTrue(all(math.isfinite(v) for v in (*offset,*anchor)))
                if not clip['loop']:
                    last,_,_=library.frame(unit,action,1000)
                    self.assertIs(last,library.atlases[key][2][action][-1])
            self.assertFalse(library.fallbacks)

    def test_every_investigation_essence_plays_its_own_monster_atlas(self):
        library=SpriteLibrary();self.addCleanup(library.clear)
        keys=set()
        for faction in hunt.NOBLES:
            for story in hunt.STORIES:
                for variant in range(1,6):
                    case=dict(faction=faction,season=0,
                              scenario=json.dumps(dict(story,variant=variant,monster='Essence')))
                    unit=hunt.monster(case);key=library.key(unit)
                    self.assertIsNotNone(key,unit['unit_image']);keys.add(key)
                    self.assertTrue(key.startswith('monsters/'))
                    metadata=json.loads((ASSETS/library.index['characters'][key]).read_text(encoding='utf-8'))
                    for action in ('idle','walk','attack','hit','death'):
                        clip=metadata['animations'][action]
                        first,_,_=library.frame(unit,action,0)
                        second,_,_=library.frame(unit,action,1.1/clip['fps'])
                        self.assertIsNotNone(first);self.assertIsNot(first,second)
                    self.assertFalse(library.fallbacks)
        self.assertEqual(len(keys),30)

    def test_companion_form_switch_updates_both_garrison_and_battle_sprite(self):
        from test_soul_pact import SoulPactTests
        fixture=SoulPactTests();fixture.setUp();self.addCleanup(fixture.doCleanups)
        prize=hunt.claim_heart(fixture.db,'Север','Hero')
        library=SpriteLibrary();self.addCleanup(library.clear)
        keys=[]
        for form in ('noble','monster','noble'):
            shape=hunt.set_form(fixture.db,'Север',form)
            image=fixture.db.execute('SELECT unit_image FROM garrisons WHERE unit_name=?',
                                     (prize['name'],)).fetchone()[0]
            self.assertEqual(image,shape['image'])
            unit=dict(unit_image=image);keys.append(library.key(unit))
            self.assertIsNotNone(library.frame(unit,'walk',.2)[0])
            self.assertFalse(library.fallbacks)
        self.assertEqual(keys[0],keys[2]);self.assertNotEqual(keys[0],keys[1])
        self.assertTrue(keys[1].startswith('monsters/'))


if __name__=='__main__':unittest.main()
