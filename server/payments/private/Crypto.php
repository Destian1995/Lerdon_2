<?php
declare(strict_types=1);

/** OpenSSL-only crypto, supported by PHP 8.2+; no Sodium dependency. */
final class PayCrypto {
    private const AAD='LerdonPay:storage:gcm1';
    public static function requirements(): array {
        $checks=['PHP 8.2+'=>PHP_VERSION_ID>=80200];
        foreach (['openssl','pdo_mysql','curl'] as $extension) $checks[$extension]=extension_loaded($extension);
        $checks['AES-256-GCM']=extension_loaded('openssl') && in_array('aes-256-gcm',openssl_get_cipher_methods(),true);
        $checks['RSA/SHA256']=function_exists('openssl_pkey_new') && function_exists('openssl_sign') &&
            in_array('sha256',openssl_get_md_methods(),true);
        return $checks;
    }
    public static function generateSigningSecret(): string {
        $key=openssl_pkey_new(['private_key_bits'=>3072,'private_key_type'=>OPENSSL_KEYTYPE_RSA]);
        if ($key===false || !openssl_pkey_export($key,$pem)) throw new PayError(503,'Cannot generate RSA key; check OpenSSL configuration');
        return base64_encode($pem);
    }
    private static function key(string $encoded): string {
        $key=base64_decode($encoded,true);
        if ($key===false || strlen($key)!==32) throw new PayError(503,'Encryption key not configured');
        return $key;
    }
    public static function encrypt(string $plain,string $encodedKey): string {
        $key=self::key($encodedKey);$iv=random_bytes(12);$tag='';
        $cipher=openssl_encrypt($plain,'aes-256-gcm',$key,OPENSSL_RAW_DATA,$iv,$tag,self::AAD,16);
        if ($cipher===false || strlen($tag)!==16) throw new PayError(503,'Cannot encrypt stored data');
        return 'gcm1:'.base64_encode($iv.$tag.$cipher);
    }
    public static function decrypt(string $envelope,string $encodedKey): string {
        $key=self::key($encodedKey);
        if (!str_starts_with($envelope,'gcm1:')) throw new PayError(503,'Unsupported encrypted data version');
        $raw=base64_decode(substr($envelope,5),true);
        // Reject short tags explicitly; OpenSSL accepts caller-selected tag lengths.
        if ($raw===false || strlen($raw)<28) throw new PayError(503,'Invalid stored data');
        $plain=openssl_decrypt(substr($raw,28),'aes-256-gcm',$key,OPENSSL_RAW_DATA,substr($raw,0,12),substr($raw,12,16),self::AAD);
        if ($plain===false) throw new PayError(503,'Cannot authenticate stored data');
        return $plain;
    }
    private static function signingKey(string $encoded): OpenSSLAsymmetricKey {
        $pem=base64_decode($encoded,true);
        $key=$pem===false?false:@openssl_pkey_get_private($pem);
        if ($key===false) throw new PayError(503,'RSA signing key not configured; existing keys must not be overwritten');
        $details=openssl_pkey_get_details($key);
        if (!$details || $details['type']!==OPENSSL_KEYTYPE_RSA || $details['bits']<3072) throw new PayError(503,'RSA-3072 signing key required');
        return $key;
    }
    public static function publicKey(string $encodedSecret): string {
        return base64_encode(openssl_pkey_get_details(self::signingKey($encodedSecret))['key']);
    }
    public static function sign(string $payload,string $encodedSecret): string {
        if (!openssl_sign($payload,$signature,self::signingKey($encodedSecret),OPENSSL_ALGO_SHA256)) throw new PayError(503,'License signing failed');
        return base64_encode($signature);
    }
}
