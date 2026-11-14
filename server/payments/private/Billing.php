<?php
declare(strict_types=1);
require_once __DIR__.'/Crypto.php';

final class PayError extends RuntimeException {
    public function __construct(public readonly int $http, string $message) { parent::__construct($message); }
}

final class Billing {
    public const PLANS = ['full_monthly'=>5500, 'full_permanent'=>25000];
    public function __construct(public PDO $db, public array $config, private $transport=null) {
        $db->setAttribute(PDO::ATTR_ERRMODE, PDO::ERRMODE_EXCEPTION);
        $db->setAttribute(PDO::ATTR_DEFAULT_FETCH_MODE, PDO::FETCH_ASSOC);
    }
    public function run(string $sql, array $args=[]): PDOStatement {
        $s=$this->db->prepare($sql); $s->execute($args); return $s;
    }
    private function lock(): string { return $this->db->getAttribute(PDO::ATTR_DRIVER_NAME)==='mysql'?' FOR UPDATE':''; }
    public static function money(int $kopecks): string { return intdiv($kopecks,100).'.'.str_pad((string)($kopecks%100),2,'0',STR_PAD_LEFT); }
    public static function kopecks(mixed $value): int {
        if (!is_string($value) || !preg_match('/^\d{1,8}\.\d{2}$/D',$value)) throw new PayError(502,'Invalid provider amount');
        [$r,$k]=explode('.',$value); return (int)$r*100+(int)$k;
    }
    public static function nextMonth(int $start): int {
        $d=(new DateTimeImmutable('@'.$start))->setTimezone(new DateTimeZone('UTC'));
        $next=$d->modify('first day of next month');
        return $next->setDate((int)$next->format('Y'),(int)$next->format('m'),min((int)$d->format('d'),(int)$next->format('t')))->getTimestamp();
    }
    public function encrypt(string $plain): string {
        return PayCrypto::encrypt($plain,$this->config['app_key']);
    }
    private function decrypt(string $cipher): string {
        return PayCrypto::decrypt($cipher,$this->config['app_key']);
    }
    public function rate(string $scope, string $identity, int $limit, int $seconds): void {
        $now=time(); $bucket=hash_hmac('sha256',$scope.':'.$identity.':'.intdiv($now,$seconds),$this->config['app_key']);
        $driver=$this->db->getAttribute(PDO::ATTR_DRIVER_NAME);
        $sql=$driver==='mysql'?'INSERT INTO pay_rate_limits VALUES(?,1,?) ON DUPLICATE KEY UPDATE hits=hits+1':
            'INSERT INTO pay_rate_limits VALUES(?,1,?) ON CONFLICT(bucket) DO UPDATE SET hits=hits+1';
        $this->run($sql,[$bucket,$now+$seconds]);
        if ((int)$this->run('SELECT hits FROM pay_rate_limits WHERE bucket=?',[$bucket])->fetchColumn()>$limit) throw new PayError(429,'Too many requests');
    }
    public function register(string $email): array {
        if (strlen($email)>254 || !filter_var($email,FILTER_VALIDATE_EMAIL)) throw new PayError(400,'Valid email required');
        $id=bin2hex(random_bytes(16)); $token=bin2hex(random_bytes(32));
        $this->run('INSERT INTO pay_accounts(id,token_hash,email,created_at) VALUES(?,?,?,?)',[$id,hash('sha256',$token),$email,time()]);
        return ['account_id'=>$id,'recovery_code'=>$token];
    }
    public function authenticate(string $token): array {
        if (!preg_match('/^[a-f0-9]{64}$/D',$token)) throw new PayError(401,'Invalid access code');
        $a=$this->run('SELECT * FROM pay_accounts WHERE token_hash=?',[hash('sha256',$token)])->fetch();
        if (!$a) throw new PayError(401,'Invalid access code'); return $a;
    }
    public function createGift(string $label): array {
        if (strlen($label)>120 || preg_match('/[\x00-\x1f]/',$label)) throw new PayError(400,'Invalid label');
        $raw=strtoupper(bin2hex(random_bytes(20)));$id=bin2hex(random_bytes(16));
        $this->run('INSERT INTO pay_gift_keys(id,key_hash,label,test_mode,created_at) VALUES(?,?,?,?,?)',
            [$id,hash('sha256',$raw),$label,$this->config['test_mode']?1:0,time()]);
        return ['id'=>$id,'key'=>'LERDON-'.implode('-',str_split($raw,8))];
    }
    public function redeemGift(string $accountId,string $key): array {
        $key=strtoupper(trim($key));
        if (!preg_match('/^LERDON-(?:[A-F0-9]{8}-){4}[A-F0-9]{8}$/D',$key)) throw new PayError(404,'Gift key unavailable');
        $hash=hash('sha256',str_replace('-','',substr($key,7)));
        $this->db->beginTransaction();
        try {
            $a=$this->account($accountId,true);
            $gift=$this->run('SELECT * FROM pay_gift_keys WHERE key_hash=?'.$this->lock(),[$hash])->fetch();
            if (!$gift || $gift['revoked'] || (bool)$gift['test_mode']!==$this->config['test_mode']) throw new PayError(404,'Gift key unavailable');
            if ($gift['redeemed_by']!==null && $gift['redeemed_by']!==$accountId) throw new PayError(409,'Gift key already used');
            if ($gift['redeemed_by']===null) {
                if ($a['permanent']) throw new PayError(409,'Permanent access already active');
                $changed=$this->run('UPDATE pay_gift_keys SET redeemed_by=?,redeemed_at=? WHERE id=? AND redeemed_by IS NULL AND revoked=0',[$accountId,time(),$gift['id']]);
                if ($changed->rowCount()!==1) throw new PayError(409,'Gift key already used');
                $this->run('UPDATE pay_accounts SET permanent=1 WHERE id=?',[$accountId]);
                $this->stopRenewal($accountId);
            }
            $this->db->commit();
        } catch (Throwable $e) { if ($this->db->inTransaction()) $this->db->rollBack(); throw $e; }
        return $this->entitlement($accountId);
    }
    public function account(string $id, bool $lock=false): array {
        $a=$this->run('SELECT * FROM pay_accounts WHERE id=?'.($lock?$this->lock():''),[$id])->fetch();
        if (!$a) throw new PayError(404,'Account not found'); return $a;
    }
    public function ready(bool $monthly=false): void {
        if (!$this->config['shop_id'] || !$this->config['api_secret']) throw new PayError(503,'Payments not configured');
        if (!$this->config['test_mode'] && (!$this->config['live_enabled'] || !$this->config['npd_receipts_ready'])) throw new PayError(503,'Live payments not enabled');
        if ($monthly && !$this->config['recurring_enabled']) throw new PayError(409,'Subscriptions not enabled');
    }
    private function api(string $method, string $path, ?array $data=null, ?string $key=null): array {
        if ($this->transport!==null) return ($this->transport)($method,$path,$data,$key);
        $ch=curl_init('https://api.yookassa.ru/v3/'.$path);
        $headers=['Content-Type: application/json']; if ($key!==null) $headers[]='Idempotence-Key: '.$key;
        curl_setopt_array($ch,[CURLOPT_RETURNTRANSFER=>true,CURLOPT_CUSTOMREQUEST=>$method,
            CURLOPT_USERPWD=>$this->config['shop_id'].':'.$this->config['api_secret'],
            CURLOPT_HTTPHEADER=>$headers,CURLOPT_CONNECTTIMEOUT=>8,CURLOPT_TIMEOUT=>25,
            CURLOPT_SSL_VERIFYPEER=>true,CURLOPT_SSL_VERIFYHOST=>2,CURLOPT_FOLLOWLOCATION=>false]);
        if ($data!==null) curl_setopt($ch,CURLOPT_POSTFIELDS,json_encode($data,JSON_THROW_ON_ERROR));
        $raw=curl_exec($ch); $code=curl_getinfo($ch,CURLINFO_HTTP_CODE); curl_close($ch);
        if ($raw===false || $code>=500 || $code===429) throw new PayError(503,'Payment provider temporarily unavailable');
        if ($code<200 || $code>=300) throw new PayError(502,'Payment provider rejected request');
        try { $obj=json_decode($raw,true,64,JSON_THROW_ON_ERROR); }
        catch (JsonException) { throw new PayError(502,'Invalid provider response'); }
        if (!is_array($obj)) throw new PayError(502,'Invalid provider response'); return $obj;
    }
    public function create(string $accountId, array $input): array {
        $plan=$input['plan']??''; $request=$input['request_id']??''; $token=$input['payment_token']??'';
        if (!is_string($plan) || !isset(self::PLANS[$plan])) throw new PayError(400,'Invalid plan');
        if (!is_string($request) || !preg_match('/^[a-zA-Z0-9_-]{16,64}$/D',$request)) throw new PayError(400,'Invalid request_id');
        if (!is_string($token) || strlen($token)<8 || strlen($token)>4096) throw new PayError(400,'SDK payment_token required');
        $monthly=$plan==='full_monthly'; $this->ready($monthly);
        if ($monthly && ($input['recurring_consent']??false)!==true) throw new PayError(400,'Explicit subscription consent required');
        $this->db->beginTransaction();
        try {
            $a=$this->account($accountId,true);
            $old=$this->run('SELECT * FROM pay_orders WHERE account_id=? AND request_key=?',[$accountId,$request])->fetch();
            if ($old) {
                if ($old['plan']!==$plan) throw new PayError(409,'Request already used for another plan');
                $this->db->commit(); return $this->dispatch($old['id']);
            }
            if ($a['permanent']) throw new PayError(409,'Permanent access already active');
            if ($monthly && (int)$a['monthly_until']>time()) throw new PayError(409,'Subscription already active');
            if ($this->run("SELECT id FROM pay_orders WHERE account_id=? AND status IN ('creating','pending','review')",[$accountId])->fetch()) throw new PayError(409,'Payment already in progress');
            $id=bin2hex(random_bytes(16)); $revision=(int)$a['consent_revision']+1;
            $this->run('UPDATE pay_accounts SET consent_revision=?,auto_renew=? WHERE id=?',[$revision,$monthly?1:0,$accountId]);
            $payload=['amount'=>['value'=>self::money(self::PLANS[$plan]),'currency'=>'RUB'],
                'capture'=>true,'payment_token'=>$token,
                'description'=>$monthly?'Lerdon — полный доступ на месяц':'Lerdon — полный доступ навсегда',
                'metadata'=>['order_id'=>$id,'account_id'=>$accountId,'plan'=>$plan]];
            if ($monthly) $payload['save_payment_method']=true;
            $this->insertOrder($id,$a,$request,$plan,$revision,false,$payload);
            $this->db->commit();
        } catch (Throwable $e) { if ($this->db->inTransaction()) $this->db->rollBack(); throw $e; }
        return $this->dispatch($id);
    }
    private function insertOrder(string $id,array $a,string $request,string $plan,int $revision,bool $recurring,array $payload): void {
        $this->run('INSERT INTO pay_orders(id,account_id,request_key,plan,amount,payload_cipher,created_at,consent_revision,recurring) VALUES(?,?,?,?,?,?,?,?,?)',
            [$id,$a['id'],$request,$plan,self::PLANS[$plan],$this->encrypt(json_encode($payload,JSON_THROW_ON_ERROR)),time(),$revision,$recurring?1:0]);
    }
    public function dispatch(string $id): array {
        $o=$this->run('SELECT * FROM pay_orders WHERE id=?',[$id])->fetch();
        if (!$o) throw new PayError(404,'Order not found');
        if ($o['provider_id']) return $this->sync($o['provider_id']);
        if ($o['status']!=='creating') return $this->orderView($o);
        if ((int)$o['created_at']<time()-23*3600) {
            $this->run("UPDATE pay_orders SET status='review' WHERE id=?",[$id]);
            throw new PayError(409,'Payment requires support review');
        }
        $this->ready($o['plan']==='full_monthly');
        // Serialize sends and cancellation; retry always uses the stored UUID.
        $this->db->beginTransaction();
        try {
            $a=$this->account($o['account_id'],true);
            $o=$this->run('SELECT * FROM pay_orders WHERE id=?'.$this->lock(),[$id])->fetch();
            if ($o['provider_id']) { $this->db->commit(); return $this->sync($o['provider_id']); }
            if ($o['status']!=='creating') { $this->db->commit(); return $this->orderView($o); }
            if ($o['recurring'] && (!$a['auto_renew'] || $a['permanent'] || $a['consent_revision']!=$o['consent_revision'])) {
                $this->run("UPDATE pay_orders SET status='canceled',payload_cipher=NULL WHERE id=?",[$id]);
                $this->db->commit(); return ['order_id'=>$id,'status'=>'canceled'];
            }
            $payload=json_decode($this->decrypt($o['payload_cipher']),true,64,JSON_THROW_ON_ERROR);
            $p=$this->api('POST','payments',$payload,$id);
            $this->validatePayment($p,$o);
            $this->run('UPDATE pay_orders SET provider_id=?,status=?,payload_cipher=NULL WHERE id=?',[$p['id'],$p['status'],$id]);
            $this->db->commit();
        } catch (Throwable $e) {
            if ($this->db->inTransaction()) $this->db->rollBack();
            if ($e instanceof PayError && $e->getMessage()==='Payment verification failed')
                $this->run("UPDATE pay_orders SET status='review' WHERE id=?",[$id]);
            throw $e;
        }
        return $this->applyPayment($p);
    }
    public function validatePayment(array $p,array $o): void {
        if (!preg_match('/^[a-zA-Z0-9-]{1,64}$/D',$p['id']??'') ||
            !in_array($p['status']??'', ['pending','waiting_for_capture','succeeded','canceled'],true) ||
            (string)($p['recipient']['account_id']??'')!==(string)$this->config['shop_id'] ||
            ($p['test']??null)!==$this->config['test_mode'] || ($p['amount']['currency']??'')!=='RUB' ||
            self::kopecks($p['amount']['value']??null)!==(int)$o['amount'] ||
            ($p['metadata']['order_id']??'')!==$o['id'] || ($p['metadata']['account_id']??'')!==$o['account_id'] ||
            ($p['metadata']['plan']??'')!==$o['plan'] || ($o['provider_id'] && $o['provider_id']!==$p['id'])) throw new PayError(502,'Payment verification failed');
        if ($p['status']==='succeeded' && ($p['paid']??false)!==true) throw new PayError(502,'Payment not paid');
    }
    public function sync(string $providerId): array {
        if (!preg_match('/^[a-zA-Z0-9-]{1,64}$/D',$providerId)) throw new PayError(400,'Invalid payment ID');
        return $this->applyPayment($this->api('GET','payments/'.$providerId));
    }
    private function applyPayment(array $p): array {
        $id=$p['metadata']['order_id']??'';
        if (!is_string($id) || !preg_match('/^[a-f0-9]{32}$/D',$id)) throw new PayError(404,'Unknown payment');
        $o=$this->run('SELECT * FROM pay_orders WHERE id=?',[$id])->fetch();
        if (!$o) throw new PayError(404,'Unknown payment');
        $this->validatePayment($p,$o);
        $this->db->beginTransaction();
        try {
            $a=$this->account($o['account_id'],true);
            $o=$this->run('SELECT * FROM pay_orders WHERE id=?'.$this->lock(),[$id])->fetch();
            $this->validatePayment($p,$o);
            // A slower concurrent poll must never undo a verified refund or
            // move an already final payment back into a pending state.
            if (in_array($o['status'],['succeeded','canceled'],true) && $p['status']!==$o['status']) {
                $this->db->commit(); return $this->orderView($o);
            }
            $refunded=(bool)$o['refunded'] || (isset($p['refunded_amount']) && self::kopecks($p['refunded_amount']['value'])>0);
            if ($p['status']==='succeeded' && !$o['applied_at'] && !$refunded) {
                $start=max(time(),(int)$a['monthly_until']);
                $end=$o['plan']==='full_monthly'?self::nextMonth($start):0;
                $this->run("UPDATE pay_orders SET applied_at=?,grant_start=?,grant_end=?,receipt_status='pending_npd' WHERE id=?",[time(),$start,$end,$id]);
                if ($o['plan']==='full_permanent') $this->stopRenewal($a['id']);
                elseif ($a['auto_renew'] && $a['consent_revision']==$o['consent_revision']) {
                    if (($p['payment_method']['saved']??false)===true && !empty($p['payment_method']['id']))
                        $this->run('UPDATE pay_accounts SET method_cipher=? WHERE id=?',[$this->encrypt($p['payment_method']['id']),$a['id']]);
                    else $this->stopRenewal($a['id']);
                }
            }
            if ($refunded && !$o['refunded']) $this->stopRenewal($a['id']);
            if ($p['status']==='canceled' && $o['status']!=='canceled' && $a['consent_revision']==$o['consent_revision']) $this->stopRenewal($a['id']);
            $this->run('UPDATE pay_orders SET provider_id=?,status=?,refunded=?,payload_cipher=NULL WHERE id=?',[$p['id'],$p['status'],$refunded?1:0,$id]);
            $this->recalculate($a['id']);
            $this->db->commit();
        } catch (Throwable $e) { if ($this->db->inTransaction()) $this->db->rollBack(); throw $e; }
        $o=$this->run('SELECT * FROM pay_orders WHERE id=?',[$id])->fetch();
        $result=$this->orderView($o);
        $result['confirmation_url']=$p['confirmation']['confirmation_url']??null;
        return $result;
    }
    private function orderView(array $o): array { return ['order_id'=>$o['id'],'payment_id'=>$o['provider_id'],'status'=>$o['status'],'plan'=>$o['plan'],'refunded'=>(bool)$o['refunded']]; }
    private function recalculate(string $id): void {
        $rows=$this->run("SELECT plan,grant_end FROM pay_orders WHERE account_id=? AND status='succeeded' AND applied_at IS NOT NULL AND refunded=0",[$id])->fetchAll();
        $until=0; $permanent=(int)(bool)$this->run('SELECT 1 FROM pay_gift_keys WHERE redeemed_by=? AND revoked=0 LIMIT 1',[$id])->fetchColumn();
        foreach ($rows as $r) { if ($r['plan']==='full_permanent') $permanent=1; else $until=max($until,(int)$r['grant_end']); }
        $this->run('UPDATE pay_accounts SET permanent=?,monthly_until=? WHERE id=?',[$permanent,$until,$id]);
    }
    private function stopRenewal(string $id): void {
        $this->run('UPDATE pay_accounts SET auto_renew=0,method_cipher=NULL,consent_revision=consent_revision+1 WHERE id=?',[$id]);
    }
    public function cancel(string $id): array {
        $this->db->beginTransaction();
        try {
            $this->account($id,true);$this->stopRenewal($id);$this->db->commit();
        } catch (Throwable $e) { if ($this->db->inTransaction()) $this->db->rollBack(); throw $e; }
        return ['auto_renew'=>false,'message'=>'Продление отключено. Оплаченный доступ сохранён.'];
    }
    public function order(string $accountId,string $id): array {
        $o=$this->run('SELECT * FROM pay_orders WHERE id=? AND account_id=?',[$id,$accountId])->fetch();
        if (!$o) throw new PayError(404,'Order not found'); return $this->dispatch($id);
    }
    public function entitlement(string $id): array {
        $a=$this->account($id); $now=time();
        $claims=['version'=>2,'account_id'=>$id,'issued_at'=>$now,'permanent'=>(bool)$a['permanent'],
            'expires_at'=>(int)$a['monthly_until'],'full_access'=>(bool)$a['permanent'] || (int)$a['monthly_until']>$now,
            'auto_renew'=>(bool)$a['auto_renew'],'test'=>$this->config['test_mode']];
        $payload=base64_encode(json_encode($claims,JSON_UNESCAPED_UNICODE|JSON_THROW_ON_ERROR));
        return ['algorithm'=>'RS256','entitlement'=>$claims,'signed_payload'=>$payload,
            'signature'=>PayCrypto::sign($payload,$this->config['signing_secret']),
            'public_key'=>PayCrypto::publicKey($this->config['signing_secret'])];
    }
    public function webhook(array $event): void {
        $kind=$event['event']??''; $id=$event['object']['id']??'';
        if (!is_string($id) || !preg_match('/^[a-zA-Z0-9-]{1,64}$/D',$id)) throw new PayError(400,'Invalid notification');
        if ($kind==='refund.succeeded') {
            $refund=$this->api('GET','refunds/'.$id);
            if (($refund['status']??'')==='succeeded') $this->sync($refund['payment_id']);
        } elseif (in_array($kind,['payment.succeeded','payment.canceled'],true)) $this->sync($id);
        // The posted object is never trusted to grant access.
    }
    public function cron(): array {
        $processed=0;$errors=0;
        $this->run('DELETE FROM pay_rate_limits WHERE expires_at<?',[time()-86400]);
        foreach ($this->run("SELECT id FROM pay_orders WHERE status IN ('creating','pending') ORDER BY created_at LIMIT 50")->fetchAll() as $o) {
            try { $this->dispatch($o['id']);$processed++; } catch (Throwable) {$errors++;}
        }
        if ($this->config['recurring_enabled']) {
            $this->ready(true);
            $due=$this->run('SELECT id FROM pay_accounts WHERE auto_renew=1 AND permanent=0 AND method_cipher IS NOT NULL AND monthly_until>0 AND monthly_until<=? LIMIT 50',[time()])->fetchAll();
            foreach ($due as $row) {
                try {
                    $this->db->beginTransaction();$a=$this->account($row['id'],true);
                    if (!$a['auto_renew'] || $a['permanent'] || !$a['method_cipher'] || (int)$a['monthly_until']>time()) {$this->db->commit();continue;}
                    $request='renew:'.$a['monthly_until'];
                    $old=$this->run('SELECT id FROM pay_orders WHERE account_id=? AND request_key=?',[$a['id'],$request])->fetch();
                    if ($old || $this->run("SELECT id FROM pay_orders WHERE account_id=? AND status IN ('creating','pending','review')",[$a['id']])->fetch()) {$this->db->commit();continue;}
                    $id=bin2hex(random_bytes(16));
                    $payload=['amount'=>['value'=>self::money(self::PLANS['full_monthly']),'currency'=>'RUB'],'capture'=>true,
                        'payment_method_id'=>$this->decrypt($a['method_cipher']),'description'=>'Lerdon — продление полного доступа на месяц',
                        'metadata'=>['order_id'=>$id,'account_id'=>$a['id'],'plan'=>'full_monthly']];
                    $this->insertOrder($id,$a,$request,'full_monthly',(int)$a['consent_revision'],true,$payload);
                    $this->db->commit();$this->dispatch($id);$processed++;
                } catch (Throwable) {if ($this->db->inTransaction()) $this->db->rollBack();$errors++;}
            }
        }
        return ['processed'=>$processed,'errors'=>$errors];
    }
}
