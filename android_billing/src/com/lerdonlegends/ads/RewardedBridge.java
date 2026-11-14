package com.lerdonlegends.ads;

import android.app.Activity;
import android.content.Context;
import android.content.SharedPreferences;
import com.yandex.mobile.ads.common.AdError;
import com.yandex.mobile.ads.common.AdRequest;
import com.yandex.mobile.ads.common.AdRequestError;
import com.yandex.mobile.ads.common.ImpressionData;
import com.yandex.mobile.ads.common.YandexAds;
import com.yandex.mobile.ads.rewarded.Reward;
import com.yandex.mobile.ads.rewarded.RewardedAd;
import com.yandex.mobile.ads.rewarded.RewardedAdEventListener;
import com.yandex.mobile.ads.rewarded.RewardedAdLoadListener;
import com.yandex.mobile.ads.rewarded.RewardedAdLoader;
import org.json.JSONObject;
import java.util.concurrent.ConcurrentLinkedQueue;

/** UI-thread SDK ownership and a durable reward inbox, acknowledged after Python saves. */
public final class RewardedBridge {
    private static final ConcurrentLinkedQueue<String> events = new ConcurrentLinkedQueue<>();
    private static RewardedAdLoader loader;
    private static RewardedAd ad;
    private static String active = "";
    private static boolean showing;

    private static SharedPreferences inbox(Context context) {
        return context.getApplicationContext().getSharedPreferences("lerdon_rewarded_inbox", Context.MODE_PRIVATE);
    }

    private static String message(String kind, String session) {
        try { return new JSONObject().put("type", kind).put("session", session).toString(); }
        catch (Exception ignored) { return ""; }
    }

    private static void emit(String kind, String session) { events.add(message(kind, session)); }

    public static String poll(Activity activity) {
        String event = events.poll();
        if (event != null) return event;
        // A process may die after onRewarded but before Kivy receives the event.
        for (String session : inbox(activity).getAll().keySet()) return message("reward", session);
        return "";
    }

    public static void acknowledge(Activity activity, String session) {
        inbox(activity).edit().remove(session).commit();
    }

    public static void show(Activity activity, String session, String unit) {
        activity.runOnUiThread(() -> {
            if (!active.isEmpty() || activity.isFinishing() || activity.isDestroyed()) {
                emit("error", session);
                return;
            }
            active = session;
            try {
                // No location collection is needed for a strategy game.
                YandexAds.setLocationTracking(false);
                YandexAds.initialize(activity.getApplicationContext(), () -> {
                    if (!session.equals(active)) return;
                    try {
                        if (loader == null) loader = new RewardedAdLoader(activity.getApplicationContext());
                        loader.loadAd(new AdRequest.Builder(unit).build(), new RewardedAdLoadListener() {
                            @Override public void onAdLoaded(RewardedAd loaded) {
                                if (!session.equals(active)) { loaded.setAdEventListener(null); return; }
                                if (activity.isFinishing() || activity.isDestroyed()) { fail(session); return; }
                                ad = loaded;
                                ad.setAdEventListener(new RewardedAdEventListener() {
                                    @Override public void onAdShown() { showing = true; emit("shown", session); }
                                    @Override public void onAdFailedToShow(AdError error) { fail(session); }
                                    @Override public void onAdDismissed() { emit("closed", session); release(session); }
                                    @Override public void onAdClicked() { }
                                    @Override public void onAdImpression(ImpressionData data) { }
                                    @Override public void onRewarded(Reward reward) {
                                        // Only this callback earns access. Close/impression never do.
                                        inbox(activity).edit().putBoolean(session, true).commit();
                                        emit("reward", session);
                                    }
                                });
                                try { ad.show(activity); }
                                catch (Exception error) { fail(session); }
                            }
                            @Override public void onAdFailedToLoad(AdRequestError error) { fail(session); }
                        });
                    } catch (Exception error) { fail(session); }
                });
            } catch (Exception error) { fail(session); }
        });
    }

    private static void fail(String session) {
        emit("error", session);
        release(session);
    }

    private static void release(String session) {
        if (!session.equals(active)) return;
        if (ad != null) ad.setAdEventListener(null);
        ad = null;
        active = "";
        showing = false;
    }

    public static void cancel(Activity activity, String session) {
        activity.runOnUiThread(() -> { if (!showing) release(session); });
    }
}
