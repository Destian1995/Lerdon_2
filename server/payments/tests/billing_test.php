<?php
declare(strict_types=1);
require __DIR__.'/../private/Billing.php';
$checks=0;
function check(bool $ok,string $message): void {global $checks;$checks++;if (!$ok) throw new RuntimeException($message);}
function fails(callable $fn,int $http): void {try {$fn();} catch (PayError $e) {check($e->http===$http,'Wrong error: '.$e->getMessage());return;}throw new RuntimeException('Expected rejection');}
$db=new PDO('sqlite::memory:');
$db->exec('CREATE TABLE pay_accounts(id TEXT PRIMARY KEY,token_hash TEXT UNIQUE,email TEXT,created_at INTEGER,auto_renew INTEGER DEFAULT 0,consent_revision INTEGER DEFAULT 0,method_cipher TEXT,monthly_until INTEGER DEFAULT 0,permanent INTEGER DEFAULT 0);
CREATE TABLE pay_orders(id TEXT PRIMARY KEY,account_id TEXT,request_key TEXT,plan TEXT,amount INTEGER,status TEXT DEFAULT "creating",provider_id TEXT UNIQUE,payload_cipher TEXT,created_at INTEGER,applied_at INTEGER,grant_start INTEGER,grant_end INTEGER,consent_revision INTEGER,recurring INTEGER DEFAULT 0,refunded INTEGER DEFAULT 0,receipt_status TEXT DEFAULT "not_due",UNIQUE(account_id,request_key));
CREATE TABLE pay_rate_limits(bucket TEXT PRIMARY KEY,hits INTEGER,expires_at INTEGER);
CREATE TABLE pay_gift_keys(id TEXT PRIMARY KEY,key_hash TEXT NOT NULL UNIQUE,label TEXT,test_mode INTEGER,created_at INTEGER,redeemed_by TEXT,redeemed_at INTEGER,revoked INTEGER DEFAULT 0);');
$config=['shop_id'=>'12345','api_secret'=>'test_secret','test_mode'=>true,'live_enabled'=>false,'npd_receipts_ready'=>false,
    'recurring_enabled'=>true,'app_key'=>base64_encode(random_bytes(32)),
    'signing_secret'=>PayCrypto::generateSigningSecret()];
$payments=[];$posts=[];$unknownOnce=false;$wrongAmount=false;
$transport=function($method,$path,$data,$key) use (&$payments,&$posts,&$unknownOnce,&$wrongAmount): array {
    if ($method==='GET') {
        $id=substr($path,strlen('payments/'));if (!isset($payments[$id])) throw new PayError(404,'Unknown provider ID');
        return $payments[$id];
    }
    $posts[]=$key;$id='provider-'.$key;
    if (!isset($payments[$id])) $payments[$id]=['id'=>$id,'status'=>'succeeded','paid'=>true,'test'=>true,
        'recipient'=>['account_id'=>'12345'],'amount'=>$data['amount'],'metadata'=>$data['metadata'],
        'payment_method'=>['saved'=>true,'id'=>'saved-method'],'refunded_amount'=>['value'=>'0.00','currency'=>'RUB']];
    if ($wrongAmount) {$p=$payments[$id];$p['amount']['value']='1.00';return $p;}
    if ($unknownOnce) {$unknownOnce=false;throw new PayError(503,'Simulated timeout after provider accepted payment');}
    return $payments[$id];
};
$b=new Billing($db,$config,$transport);
function user(): array {global $b;return $b->register('player@example.org');}
function input(string $plan,string $request): array {return ['plan'=>$plan,'request_id'=>$request,'payment_token'=>'sdk-test-token','recurring_consent'=>true];}
$u=user();$a=$b->authenticate($u['recovery_code']);check($a['id']===$u['account_id'],'Recovery code authentication');
fails(fn()=>$b->authenticate(str_repeat('0',64)),401);
check(Billing::money(Billing::PLANS['full_permanent'])==='250.00' && Billing::money(Billing::PLANS['full_monthly'])==='55.00','Price precision');
check(gmdate('Y-m-d H:i:s',Billing::nextMonth(strtotime('2028-01-31 13:20:30 UTC')))==='2028-02-29 13:20:30','Leap-year month clamp');
check(gmdate('Y-m-d',Billing::nextMonth(strtotime('2027-01-31 UTC')))==='2027-02-28','Calendar-month clamp');
$result=$b->create($a['id'],input('full_monthly','monthly-request-0001'));
$before=$b->account($a['id']);check((int)$before['monthly_until']>time() && $before['auto_renew']==1,'Monthly access and saved method');
$b->create($a['id'],input('full_monthly','monthly-request-0001'));
check($b->account($a['id'])['monthly_until']===$before['monthly_until'],'Duplicate request must not extend access');
check(count($posts)===1,'Duplicate request must not create second payment');
$b->webhook(['event'=>'payment.succeeded','object'=>['id'=>$result['payment_id'],'status'=>'canceled']]);
check($b->account($a['id'])['monthly_until']===$before['monthly_until'],'Posted webhook data ignored');
$b->cancel($a['id']);check($b->account($a['id'])['auto_renew']==0,'Cancel renewal');
check($b->account($a['id'])['monthly_until']===$before['monthly_until'],'Cancellation preserves paid access');
$b->sync($result['payment_id']);check($b->account($a['id'])['auto_renew']==0,'Repeated success cannot re-enable consent');
$p=$b->create($a['id'],input('full_permanent','permanent-request-01'));
check($b->account($a['id'])['permanent']==1 && $b->account($a['id'])['auto_renew']==0,'Permanent supersedes renewal');
$license=$b->entitlement($a['id']);
check($license['algorithm']==='RS256','Explicit signature algorithm');
check(openssl_verify($license['signed_payload'],base64_decode($license['signature']),base64_decode($license['public_key']),OPENSSL_ALGO_SHA256)===1,'License signature');
check(openssl_verify($license['signed_payload'].'x',base64_decode($license['signature']),base64_decode($license['public_key']),OPENSSL_ALGO_SHA256)===0,'Tampered license rejected');
$payments[$p['payment_id']]['refunded_amount']['value']='250.00';$b->sync($p['payment_id']);
check($b->account($a['id'])['permanent']==0 && (int)$b->account($a['id'])['monthly_until']>time(),'Refund removes only refunded grant');
$u2=user();$unknownOnce=true;
fails(fn()=>$b->create($u2['account_id'],input('full_permanent','network-request-0001')),503);
$r=$b->create($u2['account_id'],input('full_permanent','network-request-0001'));
check($posts[count($posts)-1]===$posts[count($posts)-2],'Unknown outcome must retry same idempotency key');
check($b->account($u2['account_id'])['permanent']==1,'Timeout recovery applies one purchase');
fails(fn()=>$b->order($u2['account_id'],$result['order_id']),404);
$u3=user();$wrongAmount=true;fails(fn()=>$b->create($u3['account_id'],input('full_permanent','wrong-price-request-1')),502);$wrongAmount=false;
check($b->account($u3['account_id'])['permanent']==0,'Wrong amount cannot grant access');
$u4=user();$r4=$b->create($u4['account_id'],input('full_monthly','renewal-request-0001'));
$b->run('UPDATE pay_accounts SET monthly_until=? WHERE id=?',[time()-1,$u4['account_id']]);
$oldPosts=count($posts);$b->cron();check(count($posts)===$oldPosts+1,'One automatic renewal');
check(end($payments)['amount']['value']==='55.00','Renewal uses current monthly price');
$b->cron();check(count($posts)===$oldPosts+1,'Repeated cron does not charge twice');
$b->cancel($u4['account_id']);$b->run('UPDATE pay_accounts SET monthly_until=? WHERE id=?',[time()-1,$u4['account_id']]);
$b->cron();check(count($posts)===$oldPosts+1,'No renewals after cancellation');
$liveConfig=$config;$liveConfig['test_mode']=false;$live=new Billing($db,$liveConfig,$transport);
fails(fn()=>$live->create($u4['account_id'],input('full_permanent','disabled-live-request')),503);
$b->rate('test','127.0.0.1',1,60);fails(fn()=>$b->rate('test','127.0.0.1',1,60),429);
$gift=$b->createGift('Gift batch');$owner=user();$other=user();
check((bool)preg_match('/^LERDON-(?:[A-F0-9]{8}-){4}[A-F0-9]{8}$/D',$gift['key']),'High entropy key format');
$stored=$b->run('SELECT * FROM pay_gift_keys WHERE id=?',[$gift['id']])->fetch();
check(strlen($stored['key_hash'])===64 && !str_contains(json_encode($stored),$gift['key']),'Only gift digest is stored');
fails(fn()=>$b->redeemGift($owner['account_id'],'not-a-key'),404);
fails(fn()=>$live->redeemGift($owner['account_id'],$gift['key']),404);
$oldPosts=count($posts);$license=$b->redeemGift($owner['account_id'],strtolower($gift['key']));
check($license['entitlement']['permanent'] && $license['entitlement']['full_access'],'Gift grants permanent signed access');
check(count($posts)===$oldPosts,'Gift never charges a payment method');
$claimed=$b->run('SELECT redeemed_at FROM pay_gift_keys WHERE id=?',[$gift['id']])->fetchColumn();
$b->redeemGift($owner['account_id'],$gift['key']);
check($b->run('SELECT redeemed_at FROM pay_gift_keys WHERE id=?',[$gift['id']])->fetchColumn()===$claimed,'Same account retry is idempotent');
fails(fn()=>$b->redeemGift($other['account_id'],$gift['key']),409);
check(!$b->account($other['account_id'])['permanent'],'Cannot reuse another account gift');
$unused=$b->createGift('Unused');
fails(fn()=>$b->redeemGift($owner['account_id'],$unused['key']),409);
check($b->run('SELECT redeemed_by FROM pay_gift_keys WHERE id=?',[$unused['id']])->fetchColumn()===null,'Already active owner does not waste another gift');
$b->run('UPDATE pay_gift_keys SET revoked=1 WHERE id=?',[$unused['id']]);
fails(fn()=>$b->redeemGift($other['account_id'],$unused['key']),404);
$gift2=$b->createGift('Monthly upgrade');$b->redeemGift($u4['account_id'],$gift2['key']);
check(!$b->account($u4['account_id'])['auto_renew'],'Gift disables renewals');
$payments[$r4['payment_id']]['refunded_amount']['value']='55.00';$b->sync($r4['payment_id']);
check((bool)$b->account($u4['account_id'])['permanent'],'Refund of paid order preserves independent gift grant');
echo "OK: $checks checks; fake provider, SQLite test store; no real payments.\n";
