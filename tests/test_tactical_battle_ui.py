import time
import unittest
from strategy_ui_fixture import Window,Clock
from kivy.base import EventLoop
from tactical_battle_ui import TacticalBattlePopup,SpriteLibrary
from tactical_combat import TacticalBattle
from test_tactical_combat import unit
from window_theme import install_window_theme


def settle():
    for _ in range(5):
        time.sleep(.015)
        EventLoop.idle()


class TacticalUITests(unittest.TestCase):
    def setUp(self):
        self.size=Window.size
        install_window_theme()
        self.views=[]

    def tearDown(self):
        for view in self.views:view.dismiss(animation=False)
        settle()
        Window.size=self.size

    def viewer(self):
        archer=unit('Охотники',kind='archer',initiative=100)
        archer['unit_image']='files/army/people/predator.jpg'
        enemy=unit('Паладины',kind='cavalry')
        enemy['unit_image']='files/army/adepts/paladin.jpg'
        model=TacticalBattle([archer],[enemy],seed=7)
        view=TacticalBattlePopup(model,'attacker',lambda result:None,'Виндгар')
        self.views.append(view)
        view.open(animation=False);settle()
        view.clock_event.cancel();view.clock_event=None
        view.deploying=False
        view.refresh()
        return view

    def test_field_and_touch_controls_fit_landscape_and_portrait_phone(self):
        for size in ((568,320),(640,360),(800,480),(360,640)):
            with self.subTest(size=size):
                Window.size=size;settle()
                view=self.viewer()
                for widget in (view.board,view.panel,view.action,view.guard,view.wait_button,view.auto_button):
                    self.assertGreaterEqual(widget.x,-1)
                    self.assertGreaterEqual(widget.y,-1)
                    self.assertLessEqual(widget.right,Window.width+1)
                    self.assertLessEqual(widget.top,Window.height+1)
                self.assertGreaterEqual(view.action.height,44)
                self.assertGreaterEqual(view.guard.height,40)
                self.assertGreaterEqual(view.board.cell,25)
                if size[0]>size[1]:
                    self.assertGreater(view.board.cell*10,Window.width*.70)
                    self.assertGreater(view.board.cell*6,Window.height*.75)
                self.assertEqual(view.board.library.key(view.battle.active.unit),'north-hunter')
                view.dismiss(animation=False);settle()

    def test_selection_previews_then_confirm_moves_and_disables_wait(self):
        Window.size=(640,360);settle()
        view=self.viewer()
        model=view.battle;actor=model.active
        pos=next(iter(model.reachable()))
        before=actor.pos
        view.select(pos)
        self.assertEqual(actor.pos,before)
        self.assertFalse(view.action.disabled)
        view.confirm()
        self.assertEqual(actor.pos,pos)
        self.assertTrue(view.wait_button.disabled)
        self.assertGreater(view.busy,0)
        view.tick(2)
        view.dismiss(animation=False)
        self.assertIsNone(view.clock_event)

    def test_all_five_atlas_actions_animate_and_death_holds_last_frame(self):
        library=SpriteLibrary()
        soldier={'unit_image':'files/army/people/predator.jpg'}
        for state in ('idle','walk','attack','hit','death'):
            first=library.frame(soldier,state,0)[0]
            last=library.frame(soldier,state,.4)[0]
            self.assertNotEqual(first.tex_coords,last.tex_coords)
        self.assertEqual(library.frame(soldier,'death',100)[0].tex_coords,
                         library.frame(soldier,'death',10)[0].tex_coords)
        library.clear()
        self.assertEqual(library.atlases,{})

    def test_hero_skill_menu_and_target_confirmation_fit_small_phone(self):
        from strategy_ui import StrategyButton
        from kivy.uix.popup import Popup
        Window.size=(640,360);settle()
        hero=unit('Владислав',1,cls=3,initiative=100)
        model=TacticalBattle([hero,unit('Солдаты')],[unit('Враг')],biome='forest')
        model.stacks['attacker:0'].pos=(2,4);model.stacks['defender:0'].pos=(5,4)
        for p in ((3,4),(4,4)):model.terrain[p]='plain'
        view=TacticalBattlePopup(model,'attacker',lambda result:None,'Лес')
        view.deploying=False;self.views.append(view);view.open(animation=False);settle()
        view.refresh()
        self.assertFalse(view.skill_button.disabled)
        view.show_skills();settle()
        picker=next(w for w in Window.children if isinstance(w,Popup) and 'Владислав · Способности'==w.title)
        grenade=next(w for w in picker.walk() if isinstance(w,StrategyButton) and w.text=='Граната')
        grenade.dispatch('on_release');settle()
        view.select((5,4))
        self.assertEqual(view.selected_skill,'grenade');self.assertFalse(view.action.disabled)
        view.confirm()
        self.assertEqual(model.events[0]['ability'],'grenade')
        self.assertTrue(view.ability_fx)
        self.assertEqual(len(view.grenades),1)
        self.assertTrue(all(when==view.age+.65 for when,hit in view.pending_strikes if hit.get('grenade')))
        self.assertFalse(view.projectiles)
        # All blast victims react together on impact, after the ballistic throw.
        for _ in range(7):view.tick(.1)
        self.assertFalse(any(hit.get('grenade') for _,hit in view.pending_strikes))
        self.assertTrue(view.damage_labels)
        for _ in range(10):view.tick(.1)
        self.assertEqual(view.grenades,[])
        self.assertIsNone(view.selected_skill)


if __name__=='__main__':unittest.main()
