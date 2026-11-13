package com.lerdonlegends.billing;

import android.app.Activity;
import android.content.Intent;
import android.os.Bundle;
import java.math.BigDecimal;
import java.util.Currency;
import java.util.EnumSet;
import ru.yoomoney.sdk.kassa.payments.Checkout;
import ru.yoomoney.sdk.kassa.payments.TokenizationResult;
import ru.yoomoney.sdk.kassa.payments.checkoutParameters.Amount;
import ru.yoomoney.sdk.kassa.payments.checkoutParameters.PaymentParameters;
import ru.yoomoney.sdk.kassa.payments.checkoutParameters.PaymentMethodType;
import ru.yoomoney.sdk.kassa.payments.checkoutParameters.SavePaymentMethod;

public final class BillingActivity extends Activity {
    private static final int TOKEN = 24101, CONFIRM = 24102;
    private String session = "";
    @Override public void onCreate(Bundle saved) {
        super.onCreate(saved);
        Intent input = getIntent(); session = input.getStringExtra("session");
        if (saved != null) return; // SDK screen is restored by Android, do not launch twice.
        try {
            String clientKey = input.getStringExtra("client_key"), shopId = input.getStringExtra("shop_id");
            if (input.hasExtra("confirmation_url")) {
                Intent confirm = Checkout.createConfirmationIntent(this, input.getStringExtra("confirmation_url"),
                    PaymentMethodType.valueOf(input.getStringExtra("method")), clientKey, shopId);
                startActivityForResult(confirm, CONFIRM);
            } else {
                int kopecks = input.getIntExtra("kopecks", 0);
                if (kopecks != 20000 && kopecks != 4500) throw new IllegalArgumentException();
                Amount amount = new Amount(BigDecimal.valueOf(kopecks, 2), Currency.getInstance("RUB"));
                PaymentParameters parameters = new PaymentParameters(amount, "Lerdon", input.getStringExtra("title"),
                    clientKey, shopId, input.getBooleanExtra("save_method", false) ? SavePaymentMethod.ON : SavePaymentMethod.OFF,
                    EnumSet.of(PaymentMethodType.BANK_CARD));
                startActivityForResult(Checkout.createTokenizeIntent(this, parameters), TOKEN);
            }
        } catch (Exception ignored) { BillingBridge.emit("error", session, null, null); finish(); }
    }
    @Override protected void onActivityResult(int request, int result, Intent data) {
        super.onActivityResult(request, result, data);
        if (request == TOKEN) {
            if (result == RESULT_OK && data != null) {
                try {
                    TokenizationResult token = Checkout.createTokenizationResult(data);
                    BillingBridge.emit("token", session, token.getPaymentToken(), token.getPaymentMethodType().name());
                } catch (Exception ignored) { BillingBridge.emit("error", session, null, null); }
            } else BillingBridge.emit("canceled", session, null, null);
            finish();
        } else if (request == CONFIRM) {
            // Even RESULT_OK is not proof of entitlement. Python checks the server.
            BillingBridge.emit("confirmation", session, null, null); finish();
        }
    }
}
