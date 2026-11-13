<?php
declare(strict_types=1);
require_once __DIR__.'/Billing.php';
$file=__DIR__.'/config.php';
if (!is_file($file)) throw new PayError(503,'Payment service not configured');
$config=require $file;
foreach (PayCrypto::requirements() as $capability=>$available) {
    if (!$available) throw new PayError(503,'Required PHP capability unavailable: '.$capability);
}
if (PHP_VERSION_ID<80200) throw new PayError(503,'PHP 8.2 or newer required');
$db=new PDO($config['dsn'],$config['db_user'],$config['db_password'],[
    PDO::ATTR_ERRMODE=>PDO::ERRMODE_EXCEPTION,PDO::ATTR_EMULATE_PREPARES=>false]);
$billing=new Billing($db,$config);
