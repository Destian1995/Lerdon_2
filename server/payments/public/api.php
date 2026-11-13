<?php
declare(strict_types=1);
ini_set('display_errors','0');
header('Content-Type: application/json; charset=utf-8');
header('Cache-Control: no-store');
header('X-Content-Type-Options: nosniff');
$requestId=bin2hex(random_bytes(8));
try {
    if (($_SERVER['HTTPS']??'')!=='on' && ($_SERVER['HTTPS']??'')!=='1') {
        http_response_code(400);echo '{"error":"HTTPS required"}';exit;
    }
    require __DIR__.'/../../lerdon-pay-private/bootstrap.php';
    $action=$_GET['action']??'';
    if (!is_string($action)) throw new PayError(400,'Invalid action');
    $method=$_SERVER['REQUEST_METHOD']??'GET';
    $get=in_array($action,['catalog','entitlement','order'],true);
    if ($method!==($get?'GET':'POST')) throw new PayError(405,'Method not allowed');
    if ((int)($_SERVER['CONTENT_LENGTH']??0)>16384) throw new PayError(413,'Request too large');
    $billing->rate('api',$_SERVER['REMOTE_ADDR']??'unknown',90,60);
    $data=[];
    if (!$get) {
        $raw=file_get_contents('php://input',false,null,0,16385);
        if (strlen($raw)>16384) throw new PayError(413,'Request too large');
        try { $data=json_decode($raw,true,32,JSON_THROW_ON_ERROR); }
        catch (JsonException) { throw new PayError(400,'Invalid JSON'); }
        if (!is_array($data)) throw new PayError(400,'JSON object required');
    }
    if ($action==='catalog') {
        $out=['currency'=>'RUB','plans'=>Billing::PLANS,'subscriptions_available'=>$config['recurring_enabled'],
            'test'=>$config['test_mode'],'support'=>$config['support_email']];
    } elseif ($action==='register') {
        $billing->rate('register',$_SERVER['REMOTE_ADDR']??'unknown',5,3600);
        if (!is_string($data['email']??null)) throw new PayError(400,'Email required');
        $out=$billing->register(trim($data['email']));
    } elseif ($action==='webhook') {
        // Always GET the actual object from YooKassa; no posted status is trusted.
        try { $billing->webhook($data); }
        catch (PayError $e) { if ($e->http!==404) throw $e; }
        $out=['ok'=>true];
    } else {
        $header=$_SERVER['HTTP_AUTHORIZATION']??$_SERVER['REDIRECT_HTTP_AUTHORIZATION']??'';
        if (!preg_match('/^Bearer ([a-f0-9]{64})$/D',$header,$m)) throw new PayError(401,'Access code required');
        $a=$billing->authenticate($m[1]);
        if ($action==='create') {
            $billing->rate('create',$a['id'],6,3600);
            $out=$billing->create($a['id'],$data);
        } elseif ($action==='order') {
            if (!is_string($_GET['id']??null)) throw new PayError(400,'Order ID required');
            $out=$billing->order($a['id'],$_GET['id']);
        } elseif ($action==='redeem_gift') {
            $billing->rate('gift-ip',$_SERVER['REMOTE_ADDR']??'unknown',10,3600);
            $billing->rate('gift-account',$a['id'],5,3600);
            if (!is_string($data['key']??null)) throw new PayError(400,'Gift key required');
            $out=$billing->redeemGift($a['id'],$data['key']);
        } elseif ($action==='entitlement') $out=$billing->entitlement($a['id']);
        elseif ($action==='cancel') $out=$billing->cancel($a['id']);
        else throw new PayError(404,'Unknown action');
    }
    echo json_encode($out,JSON_UNESCAPED_UNICODE|JSON_THROW_ON_ERROR);
} catch (Throwable $e) {
    $known=$e instanceof PayError;
    http_response_code($known?$e->http:503);
    // Do not log request bodies, tokens, customer emails or configuration.
    error_log('LerdonPay request='.$requestId.' error='.get_class($e));
    echo json_encode(['error'=>$known?$e->getMessage():'Service temporarily unavailable','request_id'=>$requestId]);
}
