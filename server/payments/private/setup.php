<?php
declare(strict_types=1);
if (PHP_SAPI!=='cli') {http_response_code(404);exit;}
require_once __DIR__.'/Billing.php';
$checks=PayCrypto::requirements();
foreach ($checks as $capability=>$available) echo ($available?'OK: ':'MISSING: ').$capability."\n";
if (in_array(false,$checks,true)) {fwrite(STDERR,"Server requirements not satisfied. Configuration unchanged.\n");exit(1);}
if (($argv[1]??'')==='--check') exit;
$file=__DIR__.'/config.php';
if (!is_file($file)) {
    $c=require __DIR__.'/config.example.php';
    $c['app_key']=base64_encode(random_bytes(32));
    $c['signing_secret']=PayCrypto::generateSigningSecret();
    $old=umask(0077);file_put_contents($file,"<?php\nreturn ".var_export($c,true).";\n");umask($old);chmod($file,0600);
    echo "Создан закрытый config.php. Заполните в нём доступ к базе и тестовому магазину ЮKassa. Затем повторите команду.\n";
    exit;
}
require __DIR__.'/bootstrap.php';
$db->exec(file_get_contents(is_file(__DIR__.'/schema.sql')?__DIR__.'/schema.sql':__DIR__.'/../schema.sql'));
echo "Таблицы готовы. Режим: ".($config['test_mode']?'TEST':'LIVE')."\n";
echo "Открытый ключ подписи RSA/SHA256 (можно передавать разработчику): ".PayCrypto::publicKey($config['signing_secret'])."\n";
echo "Секретные ключи не выводятся.\n";
