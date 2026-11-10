import hashlib
import json
import unittest
from pathlib import Path
from unittest.mock import Mock,patch
from PIL import Image
from strategy_ui_fixture import Window
from tactical_spell_art import SpellArt,ROOT,SPELLS,vortex_positions
from combat_text import critical_markup,CRITICAL_COLOR,CRITICAL_HEX
import test_tactical_battle_ui as fixture
from test_troop_abilities import field
from test_tactical_combat import unit
from tactical_combat import TacticalBattle
from tactical_battle_ui import TacticalBattlePopup


class SpellAssetTests(unittest.TestCase):
    def test_every_effect_has_36_distinct_transparent_android_sized_frames(self):
        art=SpellArt();self.addCleanup(art.clear)
        self.assertEqual(set(art.index),set(SPELLS.values()))
        for key,clip in art.index.items():
            path=ROOT/clip['image']
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(),clip['sha256'])
            with Image.open(path) as atlas:
                self.assertEqual(atlas.mode,'RGBA');self.assertLessEqual(max(atlas.size),2048)
                hist=atlas.getchannel('A').histogram();self.assertGreater(sum(hist[:11])/(atlas.width*atlas.height),.4)
                hashes=set()
                for i,(x,y,w,h) in enumerate(clip['frames']):
                    cut=atlas.crop((x,y,x+w,y+h));alpha=cut.getchannel('A')
                    # The final three frames may fade below visibility, but
                    # remain distinct, transparent frames rather than blanks.
                    self.assertIsNotNone(alpha.getbbox())
                    if i<33:self.assertIsNotNone(alpha.point(lambda a:255 if a>48 else 0).getbbox())
                    hashes.add(hashlib.sha256(cut.tobytes()).digest())
                    for rect in ((0,0,1,h),(w-1,0,w,h),(0,0,w,1),(0,h-1,w,h)):
                        self.assertLess(sum(alpha.crop(rect).histogram()[240:]),8)
                self.assertEqual(len(hashes),36)
            first=art.frame(key,0)
            self.assertIsNot(first,art.frame(key,1.1/clip['fps']))
            self.assertIs(first,art.frame(key,len(clip['frames'])/clip['fps'],loop=True))
            self.assertIs(art.frame(key,1000),art.atlases[key][1][-1])

    def test_final_vortex_traversal_does_not_vanish_when_gameplay_duration_expires(self):
        motion={7:([(2,2),(3,2),(4,3)],10)}
        self.assertEqual(vortex_positions([],motion,9.9)[0][1],(2,2))
        for age,expected in ((10.15,(2.5,2)),(10.45,(3.5,2.5)),(10.6,(4,3))):
            for actual,value in zip(vortex_positions([],motion,age)[0][1],expected):self.assertAlmostEqual(actual,value)
        self.assertAlmostEqual(vortex_positions([],motion,10.7)[0][2],.5)
        self.assertEqual(vortex_positions([],motion,10.8),[])

    def test_critical_markup_colors_only_critical_information_and_escapes_names(self):
        text=critical_markup('[Чемпион] · Урон: 20 · Крит: 75% · Критов: 3')
        self.assertIn('&bl;Чемпион&br;',text)
        self.assertIn('[color='+CRITICAL_HEX+']Крит: 75%[/color]',text)
        self.assertIn('[color='+CRITICAL_HEX+']Критов: 3[/color]',text)
        self.assertIn('Урон: 20',text)


class SpellUITests(unittest.TestCase):
    setUp=fixture.TacticalUITests.setUp
    tearDown=fixture.TacticalUITests.tearDown

    def view(self,model):
        view=TacticalBattlePopup(model,'attacker',lambda _:None);self.views.append(view)
        view.audio=Mock();view.open(animation=False);fixture.settle()
        view.clock_event.cancel();view.clock_event=None;view.deploying=False;view.refresh()
        return view

    def test_actual_vortex_uses_painted_frames_at_the_moving_location_and_releases_texture(self):
        Window.size=(1000,650)
        model,a,g,b,c=field('Маг крови','mage');view=self.view(model)
        view.animate(model.use_ability('blood_vortex',b.pos));view.tick(.1)
        self.assertEqual(set(view.board.spell_art.atlases),{'blood_vortex'})
        old=model.vortices[0]['pos'];model.round+=1;model.advance_vortices()
        extra=next(e for e in reversed(model.events) if e.get('vortex'))
        view.vortex_motion[extra['vortex']]=(extra['path'],view.age)
        view.age+=.3
        with patch.object(view.board.spell_art,'draw',wraps=view.board.spell_art.draw) as draw:
            view.board.draw()
        self.assertTrue(draw.called)
        self.assertEqual(draw.call_args.args[0],'blood_vortex')
        view.export_to_png('.release/tactical-painted-vortex.png')
        view.dismiss(animation=False);self.assertFalse(view.board.spell_art.atlases)

    def test_other_spell_casts_draw_images_and_survive_for_the_full_animation(self):
        model,a,g,b,c=field('Маг крови','mage');view=self.view(model)
        for key in ('whirlwind','blizzard','freeze','flame','fire_shield',
                    'heal','inspire','vampirism','vampire_raise','dominate','blood','drain'):
            view.ability_fx=[([(4,2)],view.age,key)];view.spell_origins[(view.age,key)]=(4,2)
            view.age+=.9;view.board.draw()
            self.assertIn(SPELLS[key],view.board.spell_art.atlases)
            view.tick(.01);self.assertTrue(any(k==key for _,_,k in view.ability_fx))

    def test_six_new_effects_draw_separate_animated_images(self):
        Window.size=(1000,650)
        model,a,g,b,c=field('Маг крови','mage');view=self.view(model)
        keys=('heal','inspire','vampirism','dominate','blood','drain')
        cells=((2,1),(4,1),(6,1),(2,4),(4,4),(6,4))
        view.ability_fx=[([pos],view.age,key) for key,pos in zip(keys,cells)]
        view.age+=.45;view.board.draw()
        self.assertTrue({SPELLS[k] for k in keys}.issubset(view.board.spell_art.atlases))
        view.export_to_png('.release/tactical-new-spell-effects.png')

    def test_real_critical_hit_is_red_in_preview_floating_text_and_log(self):
        hunter=unit('Охотник',count=100,kind='archer',initiative=100)
        hunter['units_stats']['Крит']=100
        enemy=unit('Цель',count=10000)
        model=TacticalBattle([hunter],[enemy],seed=5)
        a,b=list(model.stacks.values());a.pos=(2,2);b.pos=(5,2)
        view=self.view(model);view.selection=b.pos;view.refresh()
        self.assertIn('[color='+CRITICAL_HEX+']Крит: 100%[/color]',view.info.text)
        view.animate(model.attack(b.id));view.tick(.01)
        self.assertIn('КРИТ',view.log_label.text);self.assertEqual(tuple(view.log_label.color),CRITICAL_COLOR)
        with patch.object(view.board,'label',wraps=view.board.label) as draw:
            view.board.draw()
        crit=next(call for call in draw.call_args_list if call.args[0].startswith('КРИТ'))
        self.assertEqual(crit.args[-1],CRITICAL_COLOR)
        view.export_to_png('.release/tactical-red-critical.png')

    def test_quick_battle_critical_message_uses_the_same_red_markup(self):
        from battle_ui import BattleViewer
        frames=[dict(round=1,atk_max=1000,def_max=1000,atk_total=900,def_total=850,
                     atk_crits=2,def_crits=0,heroes=[])]
        view=BattleViewer(frames,'Север','Эльфы','attacker','Север','Источник','Город')
        self.views.append(view);view.open(animation=False);fixture.settle()
        if view.clock_event:view.clock_event.cancel();view.clock_event=None
        view.show_frame(0)
        self.assertTrue(view.event_label.markup)
        self.assertIn('[color='+CRITICAL_HEX+']критические удары ×2[/color]',view.event_label.text)


if __name__=='__main__':unittest.main()
