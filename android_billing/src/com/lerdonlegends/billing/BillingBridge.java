package com.lerdonlegends.billing;

import android.app.Activity;
import android.content.Intent;
import org.json.JSONObject;
import java.util.concurrent.ConcurrentLinkedQueue;

/** Only one-time SDK tokens cross this bridge. Never log payment data. */
public final class BillingBridge {
    private static final ConcurrentLinkedQueue<String> events = new ConcurrentLinkedQueue<>();
    public static String poll() { String value = events.poll(); return value == null ? "" : value; }
    public static boolean verifyLicense(String key, String payload, String signature) {
        return LicenseVerifier.verify(key, payload, signature);
    }
    static void emit(String type, String session, String token, String method) {
        try {
            JSONObject event = new JSONObject().put("type", type).put("session", session);
            if (token != null) event.put("payment_token", token);
            if (method != null) event.put("method", method);
            events.add(event.toString());
        } catch (Exception ignored) { }
    }
    public static void tokenize(Activity activity, String session, String clientKey,
                                String shopId, int kopecks, String title, boolean saveMethod) {
        activity.runOnUiThread(() -> {
            try {
                Intent intent = new Intent(activity, BillingActivity.class);
                intent.putExtra("session", session).putExtra("client_key", clientKey).putExtra("shop_id", shopId);
                intent.putExtra("kopecks", kopecks).putExtra("title", title).putExtra("save_method", saveMethod);
                activity.startActivity(intent);
            } catch (Exception ignored) { emit("error", session, null, null); }
        });
    }
    public static void confirm(Activity activity, String session, String clientKey,
                               String shopId, String url, String method) {
        activity.runOnUiThread(() -> {
            try {
                Intent intent = new Intent(activity, BillingActivity.class);
                intent.putExtra("session", session).putExtra("client_key", clientKey).putExtra("shop_id", shopId);
                intent.putExtra("confirmation_url", url).putExtra("method", method);
                activity.startActivity(intent);
            } catch (Exception ignored) { emit("confirmation", session, null, null); }
        });
    }
    private BillingBridge() { }
}
