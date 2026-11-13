"""The Kivy side of the Java SDK bridge; all launch calls marshal to Android UI."""
import json


class AndroidPayments:
    def __init__(self):
        from jnius import autoclass
        self.bridge=autoclass('com.lerdonlegends.billing.BillingBridge')
        self.activity=autoclass('org.kivy.android.PythonActivity').mActivity
        # Resolve the application's class and static method on the Kivy thread.
        # Worker threads must not discover app classes through JNI FindClass.
        self._verify_license=self.bridge.verifyLicense
        self._verify_license('','','')  # Warm method resolution; invalid signature fails closed.

    def verify_license(self,key,payload,signature):
        return bool(self._verify_license(key,payload,signature))

    def tokenize(self,request,config):
        from premium_plans import PLANS
        plan=PLANS[request['plan']]
        self.bridge.tokenize(self.activity,request['request_id'],config['sdk_key'],config['shop_id'],
                             plan.price_kopecks,plan.title,request['plan']=='full_monthly')

    def confirm(self,pending,url,config):
        self.bridge.confirm(self.activity,pending['request_id'],config['sdk_key'],config['shop_id'],url,pending['method'])

    def poll(self):
        # Drain a bounded number so a native error cannot freeze a frame.
        for _ in range(8):
            value=self.bridge.poll()
            if not value:return
            yield json.loads(value)
