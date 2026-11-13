import threading
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from billing_android import AndroidPayments


class AndroidVerifierTests(unittest.TestCase):
    def test_worker_uses_preloaded_bridge_without_class_lookup(self):
        lookups=[];calls=[]
        def verify(key,payload,signature):
            calls.append((key,payload,signature))
            return signature=='valid'
        bridge=SimpleNamespace(verifyLicense=verify)
        def autoclass(name):
            lookups.append(threading.current_thread())
            return bridge if name.endswith('BillingBridge') else SimpleNamespace(mActivity=object())
        with patch.dict('sys.modules',{'jnius':SimpleNamespace(autoclass=autoclass)}):
            native=AndroidPayments()
            result=[]
            worker=threading.Thread(target=lambda:result.append(native.verify_license('key','payload','valid')))
            worker.start();worker.join()
        self.assertEqual(result,[True])
        self.assertEqual(len(lookups),2)
        self.assertTrue(all(t is threading.current_thread() for t in lookups))
        self.assertEqual(calls[0],('','',''))
        self.assertFalse(native.verify_license('key','payload','tampered'))
