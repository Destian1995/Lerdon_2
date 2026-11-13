<?php
declare(strict_types=1);
if (PHP_SAPI!=='cli') {http_response_code(404);exit;}
try {
    require __DIR__.'/bootstrap.php';
    echo json_encode($billing->cron(),JSON_THROW_ON_ERROR)."\n";
} catch (Throwable $e) {fwrite(STDERR,'LerdonPay cron failed: '.get_class($e)."\n");exit(1);}
