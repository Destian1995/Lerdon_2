"""Payment protocol/state; no UI, card data, shop API secret or campaign DB."""
import base64
import json
import os
import re
import ssl
import threading
import time
import uuid
from pathlib import Path
from urllib.error import HTTPError,URLError
from urllib.parse import urlencode,urlsplit
from urllib.request import Request,build_opener,HTTPSHandler,HTTPRedirectHandler

from premium_plans import PLANS


class BillingError(Exception):
    pass


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):
        raise BillingError('Сервер оплаты перенаправляет запрос. Проверьте настройки HTTPS.')


class PaymentAPI:
    def __init__(self,base_url):
        parsed=urlsplit(base_url)
        if parsed.scheme!='https' or parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError('HTTPS payment endpoint required')
        self.base=base_url
        try:
            import certifi
            context=ssl.create_default_context(cafile=certifi.where())
        except ImportError:context=ssl.create_default_context()
        context.minimum_version=ssl.TLSVersion.TLSv1_2
        self.opener=build_opener(NoRedirect,HTTPSHandler(context=context))

    def __call__(self,action,body=None,token=None,**query):
        headers={'Accept':'application/json','User-Agent':'LerdonBilling/1'}
        if token:headers['Authorization']='Bearer '+token
        data=None
        if body is not None:
            headers['Content-Type']='application/json'
            data=json.dumps(body,separators=(',',':')).encode('utf-8')
        request=Request(self.base+'?'+urlencode(dict(action=action,**query)),data=data,headers=headers)
        try:
            with self.opener.open(request,timeout=20) as response:
                raw=response.read(65537)
        except HTTPError as error:
            if action=='redeem_gift' and error.code in (400,404,409):
                raise BillingError('Ключ не найден, уже использован или недоступен для этой версии игры.') from None
            messages={401:'Личный код не принят.',409:'Покупка уже выполняется или недоступна. Проверьте её состояние.',
                      429:'Слишком много запросов. Попробуйте позже.',503:'Платёжный сервис временно недоступен.'}
            raise BillingError(messages.get(error.code,'Сервер не принял запрос оплаты.')) from None
        except (URLError,TimeoutError,OSError):
            raise BillingError('Не удалось связаться с сервером. Проверьте интернет и повторите проверку покупки.') from None
        if len(raw)>65536:raise BillingError('Некорректный ответ сервера оплаты.')
        try:result=json.loads(raw)
        except (ValueError,UnicodeError):raise BillingError('Некорректный ответ сервера оплаты.') from None
        if not isinstance(result,dict):raise BillingError('Некорректный ответ сервера оплаты.')
        return result


def verify_rs256(public_key,payload,signature):
    """Native Android crypto; desktop verifier is used only by local checks."""
    from kivy.utils import platform
    if platform=='android':
        from jnius import autoclass
        return bool(autoclass('com.lerdonlegends.billing.LicenseVerifier').verify(public_key,payload,signature))
    try:
        from cryptography.hazmat.primitives.serialization import load_pem_public_key
        from cryptography.hazmat.primitives.asymmetric.padding import PKCS1v15
        from cryptography.hazmat.primitives.hashes import SHA256
        from cryptography.exceptions import InvalidSignature
        key=load_pem_public_key(base64.b64decode(public_key,validate=True))
        key.verify(base64.b64decode(signature,validate=True),payload.encode('ascii'),PKCS1v15(),SHA256())
        return True
    except ImportError:raise BillingError('Проверка подписи покупок доступна в Android-сборке.') from None
    except (ValueError,TypeError,InvalidSignature):return False


class BillingClient:
    def __init__(self,path,config,api=None,verifier=verify_rs256,now=time.time):
        self.path=Path(path);self.config=config;self.api=api or PaymentAPI(config['api_url'])
        self.verify=verifier;self.now=now;self.catalog=None;self.lock=threading.RLock()
        try:
            self.state=json.loads(self.path.read_text(encoding='utf-8'))
            if not isinstance(self.state,dict):self.state={}
        except (OSError,ValueError):self.state={}

    def save(self):
        with self.lock:
            self.path.parent.mkdir(parents=True,exist_ok=True)
            temp=self.path.with_suffix('.tmp')
            fd=os.open(str(temp),os.O_WRONLY|os.O_CREAT|os.O_TRUNC,0o600)
            with os.fdopen(fd,'w',encoding='utf-8') as stream:
                json.dump(self.state,stream,ensure_ascii=False);stream.flush();os.fsync(stream.fileno())
            os.replace(temp,self.path)

    @property
    def code(self):return self.state.get('recovery_code','')

    @property
    def pending(self):return self.state.get('pending')

    def load_catalog(self):
        result=self.api('catalog')
        prices={key:plan.price_kopecks for key,plan in PLANS.items()}
        if result.get('test') is not self.config['test_mode'] or result.get('currency')!='RUB' or result.get('plans')!=prices:
            raise BillingError('Настройки магазина или цены изменились. Обновите приложение.')
        self.catalog=result
        return result

    def ensure_account(self,email):
        if self.code:return
        email=email.strip()
        if len(email)>254 or not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',email):
            raise BillingError('Укажите почту для чека и связи по покупке.')
        result=self.api('register',{'email':email})
        code=result.get('recovery_code','');account=result.get('account_id','')
        if not re.fullmatch('[a-f0-9]{64}',code) or not re.fullmatch('[a-f0-9]{32}',account):
            raise BillingError('Сервер не создал аккаунт оплаты.')
        self.state.update(recovery_code=code,account_id=account,email=email);self.save()

    def prepare(self,plan,email='',consent=False):
        if self.pending:raise BillingError('Сначала проверьте незавершённую покупку.')
        if plan not in PLANS:raise BillingError('Неизвестный тариф.')
        if not self.config.get('public_key'):
            raise BillingError('Магазин ещё настраивается: не указан ключ проверки покупок.')
        if self.catalog is None:self.load_catalog()
        if plan=='full_monthly' and (not self.catalog.get('subscriptions_available') or not consent):
            raise BillingError('Подписка недоступна или не подтверждено согласие на продление.')
        if not self.config.get('sdk_key'):raise BillingError('Ключ мобильного SDK ещё не настроен.')
        self.ensure_account(email)
        self.state['pending']=dict(plan=plan,request_id=uuid.uuid4().hex,stage='tokenizing',consent=consent)
        self.save();return dict(self.pending)

    def token_received(self,session,token,method):
        pending=self.pending
        if not pending or pending['request_id']!=session or pending['stage']!='tokenizing':return False
        if not isinstance(token,str) or not 8<=len(token)<=4096 or method!='BANK_CARD':
            raise BillingError('SDK вернул некорректные данные оплаты.')
        pending.update(payment_token=token,method=method,stage='creating');self.save();return True

    def token_canceled(self,session):
        if self.pending and self.pending['request_id']==session and self.pending['stage']=='tokenizing':
            self.state.pop('pending',None);self.save()

    def check_order(self):
        pending=self.pending
        if not pending:return None
        if pending['stage']=='tokenizing':raise BillingError('Форма оплаты ещё не завершена. Если она закрыта — отмените подготовку и повторите.')
        if pending.get('order_id'):
            result=self.api('order',token=self.code,id=pending['order_id'])
        else:
            result=self.api('create',dict(plan=pending['plan'],request_id=pending['request_id'],
                payment_token=pending['payment_token'],recurring_consent=pending['consent']),token=self.code)
        if result.get('plan')!=pending['plan'] or result.get('status') not in ('creating','pending','succeeded','canceled','review'):
            raise BillingError('Не удалось проверить состояние покупки.')
        order=result.get('order_id','')
        if not re.fullmatch('[a-f0-9]{32}',order):raise BillingError('Некорректный номер заказа.')
        if pending.get('order_id') and order!=pending['order_id']:raise BillingError('Сервер вернул другой заказ.')
        pending['order_id']=order;pending['stage']='checking';self.save()
        if result['status']=='succeeded':
            self.refresh_access()
            self.state.pop('pending',None);self.save()
        elif result['status']=='canceled':
            self.state.pop('pending',None);self.save()
        return result

    def validate_license(self,envelope,account=None):
        if not isinstance(envelope,dict) or envelope.get('algorithm')!='RS256':raise BillingError('Неверная подпись доступа.')
        payload=envelope.get('signed_payload','');signature=envelope.get('signature','')
        if not isinstance(payload,str) or len(payload)>8192 or not isinstance(signature,str) or len(signature)>2048:
            raise BillingError('Некорректная лицензия.')
        if not self.verify(self.config['public_key'],payload,signature):raise BillingError('Подпись доступа не подтверждена.')
        try:claims=json.loads(base64.b64decode(payload,validate=True))
        except (ValueError,UnicodeError):raise BillingError('Некорректная лицензия.') from None
        if (not isinstance(claims,dict) or claims.get('version')!=2 or
            not isinstance(claims.get('account_id'),str) or not re.fullmatch('[a-f0-9]{32}',claims['account_id']) or
            (account is not None and claims['account_id']!=account) or claims.get('test') is not self.config['test_mode'] or
            any(type(claims.get(k)) is not bool for k in ('full_access','permanent','auto_renew')) or
            any(type(claims.get(k)) is not int for k in ('issued_at','expires_at')) or claims['expires_at']<0 or
            claims['issued_at']>self.now()+300 or claims['issued_at']<=0 or
            claims['full_access']!=(claims['permanent'] or claims['expires_at']>claims['issued_at'])):
            raise BillingError('Лицензия относится к другому магазину или аккаунту.')
        return claims

    def refresh_access(self):
        if not self.code:return None
        envelope=self.api('entitlement',token=self.code)
        claims=self.validate_license(envelope,self.state['account_id'])
        self.state.update(license=envelope,last_verified_time=int(self.now()));self.save()
        return claims

    def restore(self,code):
        if self.pending:raise BillingError('Сначала проверьте незавершённую покупку.')
        code=code.strip().lower()
        if not re.fullmatch('[a-f0-9]{64}',code):raise BillingError('Личный код содержит 64 символа. Проверьте его.')
        envelope=self.api('entitlement',token=code)
        claims=self.validate_license(envelope)
        self.state.update(recovery_code=code,account_id=claims['account_id'],license=envelope,last_verified_time=int(self.now()))
        self.save();return claims

    def redeem_gift(self,key,email=''):
        if self.pending:raise BillingError('Сначала проверьте незавершённую покупку.')
        key=key.strip().upper()
        if not re.fullmatch(r'LERDON-(?:[A-F0-9]{8}-){4}[A-F0-9]{8}',key):
            raise BillingError('Проверьте подарочный ключ: LERDON и пять групп по 8 символов.')
        access=self.access()
        if access and access['permanent']:raise BillingError('Полная версия уже открыта навсегда. Ключ можно подарить другому игроку.')
        self.ensure_account(email)
        envelope=self.api('redeem_gift',{'key':key},token=self.code)
        claims=self.validate_license(envelope,self.state['account_id'])
        if not claims['permanent'] or not claims['full_access']:
            raise BillingError('Сервер не подтвердил активацию полной версии. Повторите проверку доступа.')
        self.state.update(license=envelope,last_verified_time=int(self.now()))
        self.save();return claims

    def access(self):
        envelope=self.state.get('license')
        if not envelope:return None
        try:claims=self.validate_license(envelope,self.state.get('account_id'))
        except BillingError:return None
        if self.now()<self.state.get('last_verified_time',0)-300:return None
        if not claims['permanent'] and self.now()>=claims['expires_at']:return None
        return claims if claims['full_access'] else None

    def cancel_subscription(self):
        if not self.code:raise BillingError('Сначала восстановите доступ по личному коду.')
        result=self.api('cancel',{},token=self.code)
        if result.get('auto_renew') is not False:raise BillingError('Не удалось подтвердить отмену подписки.')
        return self.refresh_access()
