<?php
declare(strict_types=1);
require __DIR__.'/../private/Billing.php';
$checks=0;
function check(bool $ok,string $message): void {global $checks;$checks++;if (!$ok) throw new RuntimeException($message);}
function rejects(callable $fn): void {
    try {$fn();} catch (PayError $e) {check($e->http===503,'Wrong rejection');return;}
    throw new RuntimeException('Unauthenticated ciphertext accepted');
}
$key=base64_encode(random_bytes(32));
foreach (['','saved-payment-method','Защищённые данные',"\x00\xff\x00"] as $plain) {
    $cipher=PayCrypto::encrypt($plain,$key);
    check(PayCrypto::decrypt($cipher,$key)===$plain,'Encrypted roundtrip');
}
$cipher=PayCrypto::encrypt('secret',$key);
check($cipher!==PayCrypto::encrypt('secret',$key),'Fresh nonce on each encryption');
rejects(fn()=>PayCrypto::decrypt($cipher,base64_encode(random_bytes(32))));
rejects(fn()=>PayCrypto::decrypt($cipher,base64_encode('short-key')));
rejects(fn()=>PayCrypto::decrypt('old-sodium-blob',$key));
rejects(fn()=>PayCrypto::decrypt('gcm1:!!!',$key));
rejects(fn()=>PayCrypto::decrypt('gcm1:'.base64_encode(str_repeat('x',27)),$key));
$raw=base64_decode(substr($cipher,5),true);
foreach ([0,12,28] as $offset) {
    $modified=$raw;$modified[$offset]=chr(ord($modified[$offset])^1);
    rejects(fn()=>PayCrypto::decrypt('gcm1:'.base64_encode($modified),$key));
}
$signing=PayCrypto::generateSigningSecret();$payload='license-v2';
$public=base64_decode(PayCrypto::publicKey($signing),true);
$signature=base64_decode(PayCrypto::sign($payload,$signing),true);
check(openssl_verify($payload,$signature,$public,OPENSSL_ALGO_SHA256)===1,'RSA signature');
check(openssl_verify($payload.'tampered',$signature,$public,OPENSSL_ALGO_SHA256)===0,'Reject forged payload');
check(openssl_pkey_get_details(openssl_pkey_get_public($public))['bits']===3072,'RSA key size');
rejects(fn()=>PayCrypto::publicKey(base64_encode(random_bytes(64))));
echo "OK: $checks crypto checks; Sodium loaded: ".(extension_loaded('sodium')?'yes':'no')."\n";
