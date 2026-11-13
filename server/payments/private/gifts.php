<?php
declare(strict_types=1);
if (PHP_SAPI!=='cli') {http_response_code(404);exit;}
require __DIR__.'/bootstrap.php';
try {
    $command=$argv[1]??'';
    if ($command==='create') {
        $count=filter_var($argv[2]??'1',FILTER_VALIDATE_INT,['options'=>['min_range'=>1,'max_range'=>100]]);
        if ($count===false) throw new RuntimeException('Count must be 1..100');
        echo 'Mode: '.($config['test_mode']?'TEST':'LIVE').". Keys are printed only once.\n";
        for ($i=0;$i<$count;$i++) {
            $gift=$billing->createGift($argv[3]??'Gift');echo $gift['id']."\t".$gift['key']."\n";
        }
    } elseif ($command==='list') {
        $rows=$billing->run('SELECT id,label,redeemed_by,revoked FROM pay_gift_keys WHERE test_mode=? ORDER BY created_at DESC LIMIT 200',[$config['test_mode']?1:0])->fetchAll();
        foreach ($rows as $row) echo $row['id']."\t".($row['redeemed_by']?'USED':($row['revoked']?'REVOKED':'READY'))."\t".$row['label']."\n";
    } elseif ($command==='revoke' && preg_match('/^[a-f0-9]{32}$/D',$argv[2]??'')) {
        $result=$billing->run('UPDATE pay_gift_keys SET revoked=1 WHERE id=? AND test_mode=? AND redeemed_by IS NULL AND revoked=0',[$argv[2],$config['test_mode']?1:0]);
        echo $result->rowCount()===1?"Unused key revoked.\n":"No unused key found.\n";
    } else {fwrite(STDERR,"Usage: php gifts.php create [1..100] [label] | list | revoke ID\n");exit(1);}
} catch (Throwable $e) {fwrite(STDERR,'Gift operation failed: '.get_class($e).". Check server setup.\n");exit(1);}
