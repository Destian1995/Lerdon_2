import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
from rewarded_time import PlayTime, REWARD_SECONDS


class PlayTimeTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path=Path(self.temp.name)/'time.json'
        self.now=0
        self.bank=PlayTime(self.path,lambda:self.now)

    def award(self,session='a'):
        self.bank.issue(session)
        self.bank.grant(session)

    def test_only_confirmed_known_session_grants_and_replay_is_idempotent(self):
        self.assertFalse(self.bank.grant('unknown'))
        self.award()
        self.assertEqual(self.bank.remaining,900)
        self.assertFalse(self.bank.grant('a'))
        reopened=PlayTime(self.path)
        self.assertFalse(reopened.grant('a'))
        self.assertEqual(reopened.remaining,900)
        self.award('b')
        self.assertEqual(self.bank.remaining,1800)

    def test_active_play_only_background_and_restart_preserve_time(self):
        self.award()
        self.now=400;self.bank.tick(True)
        self.assertEqual(self.bank.remaining,900)  # Menu did not spend time.
        self.now+=60;self.bank.tick(False)
        self.assertEqual(self.bank.remaining,840)
        self.now+=600;self.bank.tick(False)
        self.assertEqual(self.bank.remaining,840)
        self.bank.save()
        reopened=PlayTime(self.path,lambda:999999)
        reopened.tick(True)
        self.assertEqual(reopened.remaining,840)

    def test_expiry_is_exactly_once_and_never_negative(self):
        self.award();self.bank.tick(True)
        self.now=901
        self.assertTrue(self.bank.tick(True))
        self.assertEqual(self.bank.caption,'00:00')
        self.now+=50
        self.assertFalse(self.bank.tick(True))
        self.assertEqual(self.bank.remaining,0)

    def test_corrupt_state_fails_closed(self):
        for content in ('bad','{}','{"remaining":-1}','{"remaining":"NaN"}'):
            self.path.write_text(content)
            self.assertEqual(PlayTime(self.path).remaining,0)

    def test_storage_failure_does_not_acknowledge_or_double_credit(self):
        self.bank.issue('a')
        with patch.object(self.bank,'save',side_effect=OSError):
            with self.assertRaises(OSError):self.bank.grant('a')
        self.assertEqual(self.bank.remaining,0)
        self.assertTrue(self.bank.grant('a'))


class RewardedControllerTests(PlayTimeTests):
    def controller(self):
        from rewarded_access import RewardedAccess
        return RewardedAccess(self.bank,Mock(poll=Mock(return_value=[])))

    def test_close_and_error_never_grant_minutes(self):
        c=self.controller();c.session='a';self.bank.issue('a')
        with patch('game_audio.get_audio'):
            c.event(dict(type='closed',session='a'))
            c.event(dict(type='error',session='a'))
        self.assertEqual(self.bank.remaining,0)

    def test_reward_is_saved_before_native_acknowledgement(self):
        c=self.controller();self.bank.issue('a')
        def ack(session):
            self.assertEqual(PlayTime(self.path).remaining,900)
        c.native.acknowledge.side_effect=ack
        c.event(dict(type='reward',session='a'))
        c.event(dict(type='reward',session='a'))
        self.assertEqual(self.bank.remaining,900)

    def test_expired_access_waits_until_battle_or_turn_has_finished(self):
        c=self.controller();self.bank.issue('a')
        c.show_expired=Mock()
        with patch('rewarded_access.game_screen',return_value=Mock()), \
             patch('rewarded_access.paid_access',return_value=False), \
             patch('rewarded_access.battle_or_turn_busy',return_value=True):
            c.tick();c.show_expired.assert_not_called()
        with patch('rewarded_access.game_screen',return_value=Mock()), \
             patch('rewarded_access.paid_access',return_value=False), \
             patch('rewarded_access.battle_or_turn_busy',return_value=False):
            c.tick();c.show_expired.assert_called_once()

    def test_paid_campaign_cannot_bypass_expiry_after_continuing_a_free_one(self):
        c=self.controller();c.expired_notice=True;c.show_expired=Mock()
        with patch('rewarded_access.game_screen',return_value=Mock()), \
             patch('rewarded_access.paid_access',return_value=False), \
             patch('rewarded_access.battle_or_turn_busy',return_value=False), \
             patch('rewarded_access.requires_full_access',return_value=True):
            c.tick();c.show_expired.assert_called_once()


if __name__=='__main__':unittest.main()
