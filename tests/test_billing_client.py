import base64
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock

from cryptography.hazmat.primitives.asymmetric import rsa,padding
from cryptography.hazmat.primitives import hashes,serialization
from billing_client import BillingClient,BillingError,PaymentAPI,NoRedirect


class BillingClientTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.key=rsa.generate_private_key(public_exponent=65537,key_size=3072)
        cls.public=base64.b64encode(cls.key.public_key().public_bytes(serialization.Encoding.PEM,
            serialization.PublicFormat.SubjectPublicKeyInfo)).decode()

    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.now=2000000000
        self.config=dict(api_url='https://pay.example.org/api.php',shop_id='123',sdk_key='client-sdk-test-key',
                         public_key=self.public,test_mode=True)
        self.api=Mock()
        self.client=BillingClient(Path(self.temp.name)/'access.json',self.config,self.api,now=lambda:self.now)

    def signed(self,**changes):
        claims=dict(version=2,account_id='a'*32,issued_at=self.now,expires_at=self.now+2592000,
                    full_access=True,permanent=False,auto_renew=True,test=True)
        claims.update(changes)
        payload=base64.b64encode(json.dumps(claims,separators=(',',':')).encode()).decode()
        sig=self.key.sign(payload.encode(),padding.PKCS1v15(),hashes.SHA256())
        return dict(algorithm='RS256',signed_payload=payload,signature=base64.b64encode(sig).decode(),entitlement=claims)

    def account(self):self.client.state.update(account_id='a'*32,recovery_code='b'*64)

    def test_gift_activation_uses_server_signature_and_survives_restart_offline(self):
        self.account();key='LERDON-'+ '-'.join(['ABCDEF01']*5)
        envelope=self.signed(permanent=True,auto_renew=False,expires_at=0)
        self.api.return_value=envelope
        self.client.redeem_gift(key.lower())
        self.api.assert_called_once_with('redeem_gift',{'key':key},token='b'*64)
        restored=BillingClient(self.client.path,self.config,api=Mock(),now=lambda:self.now)
        self.assertTrue(restored.access()['permanent'])
        self.assertNotIn(key,self.client.path.read_text())
        restored.api.assert_not_called()

    def test_gift_untrusted_response_never_unlocks_or_replaces_existing_license(self):
        self.account();before=self.signed();self.client.state['license']=before
        key='LERDON-'+ '-'.join(['ABCDEF01']*5)
        self.api.return_value=self.signed(account_id='c'*32,permanent=True)
        with self.assertRaises(BillingError):self.client.redeem_gift(key)
        self.assertEqual(self.client.state['license'],before)
        self.api.return_value=self.signed(permanent=False)
        with self.assertRaises(BillingError):self.client.redeem_gift(key)
        self.assertEqual(self.client.state['license'],before)

    def test_bad_gift_pending_purchase_and_existing_permanent_access_do_not_spend_key(self):
        self.account();key='LERDON-'+ '-'.join(['ABCDEF01']*5)
        with self.assertRaises(BillingError):self.client.redeem_gift('bad-key')
        self.client.state['pending']={'stage':'checking'}
        with self.assertRaises(BillingError):self.client.redeem_gift(key)
        self.client.state.pop('pending');self.client.state['license']=self.signed(permanent=True)
        with self.assertRaises(BillingError):self.client.redeem_gift(key)
        self.api.assert_not_called()

    def ready(self):
        self.client.catalog=dict(currency='RUB',test=True,plans={'full_monthly':5500,'full_permanent':25000},subscriptions_available=True)
        self.account()

    def test_signature_covers_claims_and_does_not_trust_unsigned_fields(self):
        envelope=self.signed()
        envelope['entitlement']={'permanent':True}
        claims=self.client.validate_license(envelope,'a'*32)
        self.assertFalse(claims['permanent'])
        payload=json.loads(base64.b64decode(envelope['signed_payload']));payload['permanent']=True
        envelope['signed_payload']=base64.b64encode(json.dumps(payload).encode()).decode()
        with self.assertRaises(BillingError):self.client.validate_license(envelope)

    def test_untrusted_public_key_cannot_replace_pin(self):
        other=rsa.generate_private_key(public_exponent=65537,key_size=3072)
        envelope=self.signed()
        envelope['signature']=base64.b64encode(other.sign(envelope['signed_payload'].encode(),padding.PKCS1v15(),hashes.SHA256())).decode()
        envelope['public_key']=base64.b64encode(other.public_key().public_bytes(serialization.Encoding.PEM,
            serialization.PublicFormat.SubjectPublicKeyInfo)).decode()
        with self.assertRaises(BillingError):self.client.validate_license(envelope)

    def test_reject_wrong_account_mode_algorithm_or_future_issued_time(self):
        for envelope,account in [(self.signed(),'c'*32),(self.signed(test=False),None),
                                 (self.signed(issued_at=self.now+1000),None)]:
            with self.assertRaises(BillingError):self.client.validate_license(envelope,account)
        envelope=self.signed();envelope['algorithm']='none'
        with self.assertRaises(BillingError):self.client.validate_license(envelope)

    def test_expiry_and_clock_rollback_do_not_grant_offline_access(self):
        self.account();self.client.state.update(license=self.signed(),last_verified_time=self.now)
        self.assertTrue(self.client.access())
        self.now+=2592001;self.assertIsNone(self.client.access())
        self.now-=2593000;self.assertIsNone(self.client.access())

    def test_permanent_access_does_not_expire_with_monthly_period(self):
        self.account();self.client.state.update(license=self.signed(permanent=True,expires_at=0),last_verified_time=self.now)
        self.now+=86400*365;self.assertTrue(self.client.access()['permanent'])

    def test_unknown_creation_outcome_reuses_same_request_and_sdk_token_after_restart(self):
        self.ready();pending=self.client.prepare('full_permanent')
        self.client.token_received(pending['request_id'],'sdk-one-time-token','BANK_CARD')
        self.api.side_effect=BillingError('network error')
        with self.assertRaises(BillingError):self.client.check_order()
        first=self.api.call_args
        resumed=BillingClient(self.client.path,self.config,self.api,now=lambda:self.now)
        with self.assertRaises(BillingError):resumed.check_order()
        self.assertEqual(self.api.call_args,first)
        self.assertEqual(resumed.pending['request_id'],pending['request_id'])

    def test_does_not_accept_success_from_native_without_server_signature(self):
        self.ready();pending=self.client.prepare('full_permanent')
        self.client.token_received(pending['request_id'],'sdk-one-time-token','BANK_CARD')
        self.assertIsNone(self.client.access())
        self.api.side_effect=[dict(plan='full_permanent',order_id='c'*32,status='succeeded'),
                              dict(algorithm='RS256',signed_payload='garbage',signature='garbage')]
        with self.assertRaises(BillingError):self.client.check_order()
        self.assertIsNone(self.client.access());self.assertIsNotNone(self.client.pending)

    def test_valid_success_persists_signed_license_and_clears_pending(self):
        self.ready();pending=self.client.prepare('full_permanent')
        self.client.token_received(pending['request_id'],'sdk-one-time-token','BANK_CARD')
        self.api.side_effect=[dict(plan='full_permanent',order_id='c'*32,status='succeeded'),
                              self.signed(permanent=True,expires_at=0)]
        self.client.check_order()
        restored=BillingClient(self.client.path,self.config,self.api,now=lambda:self.now)
        self.assertTrue(restored.access()['permanent']);self.assertIsNone(restored.pending)

    def test_catalog_mismatch_blocks_payment_preparation(self):
        self.api.return_value=dict(currency='RUB',test=False,plans={'full_permanent':25000})
        with self.assertRaises(BillingError):self.client.prepare('full_permanent','a@example.org')
        self.assertIsNone(self.client.pending)

    def test_missing_live_signing_key_blocks_before_network_or_payment(self):
        self.config.update(test_mode=False,public_key='',shop_id='1525689')
        with self.assertRaisesRegex(BillingError,'ключ проверки'):
            self.client.prepare('full_permanent','player@example.org')
        self.api.assert_not_called()
        self.assertIsNone(self.client.pending)

    def test_subscription_requires_server_availability_and_explicit_consent(self):
        self.ready()
        with self.assertRaises(BillingError):self.client.prepare('full_monthly')
        self.client.catalog['subscriptions_available']=False
        with self.assertRaises(BillingError):self.client.prepare('full_monthly',consent=True)
        self.assertIsNone(self.client.pending)

    def test_duplicate_purchase_and_stale_native_events_are_ignored(self):
        self.ready();pending=self.client.prepare('full_permanent')
        with self.assertRaises(BillingError):self.client.prepare('full_permanent')
        self.assertFalse(self.client.token_received('wrong-session','sdk-test-token','BANK_CARD'))
        self.client.token_canceled('wrong-session');self.assertIsNotNone(self.client.pending)
        self.client.token_canceled(pending['request_id']);self.assertIsNone(self.client.pending)

    def test_failed_restore_keeps_existing_account(self):
        self.ready();self.client.save();self.api.side_effect=BillingError('invalid code')
        with self.assertRaises(BillingError):self.client.restore('d'*64)
        self.assertEqual(self.client.code,'b'*64)

    def test_successful_restore_verifies_signature_and_keeps_recovery_code(self):
        self.api.return_value=self.signed()
        self.client.restore('b'*64)
        self.assertEqual(self.client.code,'b'*64);self.assertTrue(self.client.access())

    def test_cancel_preserves_access_but_updates_recurring_status(self):
        self.ready();self.api.side_effect=[{'auto_renew':False},self.signed(auto_renew=False)]
        self.client.cancel_subscription()
        self.assertTrue(self.client.access());self.assertFalse(self.client.access()['auto_renew'])

    def test_authorization_is_not_followed_to_redirect(self):
        with self.assertRaises(BillingError):NoRedirect().redirect_request(None,None,301,None,None,None)
        with self.assertRaises(ValueError):PaymentAPI('http://pay.example.org/api.php')


if __name__=='__main__':unittest.main()
