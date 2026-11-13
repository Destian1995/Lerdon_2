package com.lerdonlegends.billing;

import android.util.Base64;
import java.nio.charset.StandardCharsets;
import java.security.KeyFactory;
import java.security.Signature;
import java.security.interfaces.RSAPublicKey;
import java.security.spec.X509EncodedKeySpec;

public final class LicenseVerifier {
    public static boolean verify(String pinnedPemBase64, String payload, String signatureBase64) {
        try {
            String pem = new String(Base64.decode(pinnedPemBase64, Base64.DEFAULT), StandardCharsets.US_ASCII);
            String body = pem.replace("-----BEGIN PUBLIC KEY-----", "").replace("-----END PUBLIC KEY-----", "").replaceAll("\\s", "");
            RSAPublicKey key = (RSAPublicKey) KeyFactory.getInstance("RSA").generatePublic(
                new X509EncodedKeySpec(Base64.decode(body, Base64.DEFAULT)));
            if (key.getModulus().bitLength() < 3072) return false;
            Signature verifier = Signature.getInstance("SHA256withRSA");
            verifier.initVerify(key); verifier.update(payload.getBytes(StandardCharsets.US_ASCII));
            return verifier.verify(Base64.decode(signatureBase64, Base64.DEFAULT));
        } catch (Exception ignored) { return false; }
    }
    private LicenseVerifier() { }
}
