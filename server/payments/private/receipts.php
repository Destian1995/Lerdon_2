<?php
declare(strict_types=1);
if (PHP_SAPI!=='cli') {http_response_code(404);exit;}
require __DIR__.'/bootstrap.php';
// Manual NPD receipt queue: this does not register income in My Tax.
if (($argv[1]??'')==='mark-issued') {
    $id=$argv[2]??'';
    if (!preg_match('/^[a-f0-9]{32}$/D',$id)) {fwrite(STDERR,"Order ID required\n");exit(1);}
    $billing->run("UPDATE pay_orders SET receipt_status='issued_manually' WHERE id=? AND receipt_status='pending_npd'",[$id]);
    echo "Отметка сохранена. Чек должен быть уже сформирован и отправлен покупателю.\n";exit;
}
$out=fopen('php://stdout','wb');
fputcsv($out,['order_id','payment_id','email','rubles','paid_at_utc','refunded','receipt_status']);
foreach ($billing->run("SELECT o.*,a.email FROM pay_orders o JOIN pay_accounts a ON a.id=o.account_id WHERE o.applied_at IS NOT NULL AND (o.receipt_status='pending_npd' OR o.refunded=1) ORDER BY o.applied_at")->fetchAll() as $r)
    fputcsv($out,[$r['id'],$r['provider_id'],$r['email'],Billing::money((int)$r['amount']),gmdate('c',(int)$r['applied_at']),$r['refunded'],$r['receipt_status']]);
