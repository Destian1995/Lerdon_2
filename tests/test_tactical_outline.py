"""The acting figure receives an alpha outline, including the opponent's turn."""
import unittest
import test_tactical_battle_ui as ui_fixture


class TacticalOutlineTests(unittest.TestCase):
    setUp=ui_fixture.TacticalUITests.setUp
    tearDown=ui_fixture.TacticalUITests.tearDown

    def test_shader_compiles_and_one_context_follows_the_actual_active_stack(self):
        view=ui_fixture.TacticalUITests.viewer(self)
        board=view.board;outline=board.active_outline
        self.assertTrue(outline.context.shader.success)
        board.draw()
        attacker=view.battle.active
        frame=board.library.frame(attacker.unit,*view.visual(attacker)[:2])[0]
        self.assertIs(outline.rectangle.texture,frame)
        context=outline.context
        view.battle.queue.reverse();board.draw()
        defender=view.battle.active
        self.assertEqual(defender.side,'defender')
        frame=board.library.frame(defender.unit,*view.visual(defender)[:2])[0]
        self.assertIs(outline.rectangle.texture,frame)
        self.assertIs(outline.context,context)
        self.assertIn(context,board.canvas.children)
        bounds=outline.context['uv_bounds']
        self.assertLess(bounds[0],bounds[2]);self.assertLess(bounds[1],bounds[3])
        view.cleanup()
        # Kivy replaces a cleared texture with its tiny default white texture.
        self.assertIsNot(outline.rectangle.texture,frame)
        self.assertNotIn(context,board.canvas.children)


if __name__=='__main__':unittest.main()
