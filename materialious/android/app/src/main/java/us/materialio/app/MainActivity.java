package us.materialio.app;

import android.os.Bundle;
import android.util.Log;
import android.webkit.ConsoleMessage;
import android.webkit.WebChromeClient;
import android.webkit.WebView;
import android.webkit.WebSettings;

import com.getcapacitor.BridgeActivity;

public class MainActivity extends BridgeActivity {
    private static final String TAG = "Materialious";

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        registerPlugin(ColorTheme.class);
        registerPlugin(AndroidTv.class);
        super.onCreate(savedInstanceState);
    }

    @Override
    public void onStart() {
        super.onStart();
        WebView webview = getBridge().getWebView();
        webview.setOverScrollMode(WebView.OVER_SCROLL_NEVER);
        webview.setVerticalScrollBarEnabled(false);
        webview.setHorizontalScrollBarEnabled(false);

        WebView.setWebContentsDebuggingEnabled(true);

        WebSettings settings = webview.getSettings();
        settings.setMediaPlaybackRequiresUserGesture(false);
        settings.setMixedContentMode(WebSettings.MIXED_CONTENT_ALWAYS_ALLOW);
        settings.setDomStorageEnabled(true);
        settings.setDatabaseEnabled(true);
        settings.setAllowFileAccess(true);
        settings.setAllowContentAccess(true);

        webview.setWebChromeClient(new WebChromeClient() {
            @Override
            public boolean onConsoleMessage(ConsoleMessage consoleMessage) {
                Log.i(TAG, "[" + consoleMessage.messageLevel() + "] " 
                    + consoleMessage.message() + " (" 
                    + consoleMessage.sourceId() + ":" + consoleMessage.lineNumber() + ")");
                return true;
            }
        });
    }
}
