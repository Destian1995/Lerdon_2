import gc
import unittest

from tutorial import TutorialProgress, lessons_for, notify_event, set_event_handler


class TutorialTests(unittest.TestCase):
    def tearDown(self):
        set_event_handler(None)

    def test_practical_steps_cannot_be_clicked_through(self):
        progress = TutorialProgress('Смирение')
        progress.next()
        progress.next()
        self.assertFalse(progress.next())
        progress.record('army_opened')
        self.assertFalse(progress.next())
        progress.record('tax_set')
        self.assertTrue(progress.next())
        self.assertEqual(progress.lesson.event, 'market_opened')
        self.assertFalse(progress.next())

    def test_whole_course_requires_actions_and_prepared_turn(self):
        progress = TutorialProgress('Борьба')
        progress.record('turn_finished')
        seen = []
        while progress.active:
            seen.append(progress.lesson.title)
            if progress.lesson.event:
                self.assertFalse(progress.can_advance)
                progress.record(progress.lesson.event)
            self.assertTrue(progress.next())
        self.assertEqual(len(seen), 10)
        self.assertFalse(progress.next())

    def test_earlier_exploration_is_remembered(self):
        progress = TutorialProgress('Смирение')
        progress.record('tax_set')
        progress.next()
        progress.next()
        self.assertTrue(progress.can_advance)
        progress.next()
        progress.back()
        self.assertTrue(progress.can_advance)

    def test_stop_prevents_late_events_and_navigation(self):
        progress = TutorialProgress('Смирение')
        progress.stop()
        progress.record('tax_set')
        self.assertFalse(progress.next())
        self.assertEqual(progress.events, set())

    def test_content_matches_ideology_without_fallback_claim(self):
        self.assertIn('+550%', lessons_for('Борьба')[2].text)
        self.assertIn('+700%', lessons_for('Смирение')[2].text)
        self.assertNotIn('+700%', lessons_for(None)[2].text)
        self.assertNotIn('+550%', lessons_for(None)[2].text)

    def test_event_subscription_does_not_keep_old_screen_alive(self):
        class Receiver:
            def receive(self, event):
                events.append(event)
        events = []
        receiver = Receiver()
        set_event_handler(receiver.receive)
        notify_event('tax_set')
        self.assertEqual(events, ['tax_set'])
        del receiver
        gc.collect()
        notify_event('market_opened')
        self.assertEqual(events, ['tax_set'])


if __name__ == '__main__':
    unittest.main()
