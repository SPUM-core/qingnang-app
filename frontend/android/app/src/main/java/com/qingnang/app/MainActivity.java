package com.qingnang.app;

import android.os.Build;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.view.View;
import android.webkit.WebView;
import android.widget.Toast;
import androidx.annotation.NonNull;
import androidx.core.graphics.Insets;
import androidx.core.view.ViewCompat;
import androidx.core.view.WindowCompat;
import androidx.core.view.WindowInsetsCompat;
import androidx.core.view.WindowInsetsControllerCompat;

import com.getcapacitor.BridgeActivity;

/**
 * 状态栏 / 挖孔 / 导航栏 inset → CSS 变量桥。
 *
 * 关键设计（为什么之前改了都不生效）：
 *   - BridgeActivity 的 getBridge().getWebView() 在远程页（server.url）加载时
 *     经常为 null（Bridge 初始化时机晚于本地页），所以改为遍历 decorView
 *     找 WebView 实例，直接 evaluateJavascript，完全绕过 Bridge
 *   - burst 重推 + 强制跳过去重（远程页 DOM ready 晚、页面重载会丢 CSS 变量）
 *   - 物理像素 / devicePixelRatio 校准
 *   - systemBars 与 displayCutout 分别取再 max
 */
public class MainActivity extends BridgeActivity {

    private static final long[] REPUSH_DELAYS = { 0L, 150L, 400L, 800L, 1500L, 2500L, 4000L, 6000L, 9000L };

    // 返回键双击退出逻辑
    private long lastBackPressTime = 0;
    private static final long EXIT_CONFIRM_WINDOW_MS = 2000L;
    private final Handler mainHandler = new Handler(Looper.getMainLooper());
    private Runnable resetBackPressRunnable;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        // Edge-to-edge
        WindowCompat.setDecorFitsSystemWindows(getWindow(), false);

        // 图标明暗
        WindowInsetsControllerCompat wic =
            WindowCompat.getInsetsController(getWindow(), getWindow().getDecorView());
        if (wic != null) {
            wic.setAppearanceLightStatusBars(true);
            wic.setAppearanceLightNavigationBars(true);
        }

        // 实时监听
        View decor = getWindow().getDecorView();
        ViewCompat.setOnApplyWindowInsetsListener(decor, (v, insetsCompat) -> {
            pushInsetsToJs(insetsCompat);
            return insetsCompat;
        });

        // Burst 兜底重推
        for (long delay : REPUSH_DELAYS) {
            decor.postDelayed(() -> {
                View root = getWindow().getDecorView();
                if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
                    android.view.WindowInsets raw = root.getRootWindowInsets();
                    if (raw != null) {
                        pushInsetsToJs(WindowInsetsCompat.toWindowInsetsCompat(raw));
                    }
                }
            }, delay);
        }
    }

    /**
     * 从 decorView 直接遍历找 WebView —— 绕过 BridgeActivity 的 bridge getter。
     * 原因：远程页加载时 Bridge 可能还没初始化，getBridge() 返回 null。
     */
    private WebView findWebView() {
        View root = getWindow().getDecorView();
        return findWebViewRecursive(root);
    }

    private WebView findWebViewRecursive(View v) {
        if (v instanceof WebView) return (WebView) v;
        if (v instanceof android.view.ViewGroup) {
            android.view.ViewGroup group = (android.view.ViewGroup) v;
            for (int i = 0; i < group.getChildCount(); i++) {
                WebView wv = findWebViewRecursive(group.getChildAt(i));
                if (wv != null) return wv;
            }
        }
        return null;
    }

    private void pushInsetsToJs(WindowInsetsCompat insetsCompat) {
        if (insetsCompat == null) return;

        int top, bottom, left, right;
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) {
            Insets bars = insetsCompat.getInsets(WindowInsetsCompat.Type.systemBars());
            Insets cut  = insetsCompat.getInsets(WindowInsetsCompat.Type.displayCutout());
            top    = Math.max(bars.top,    cut.top);
            bottom = Math.max(bars.bottom, cut.bottom);
            left   = Math.max(bars.left,   cut.left);
            right  = Math.max(bars.right,  cut.right);
        } else {
            top    = insetsCompat.getSystemWindowInsetTop();
            bottom = insetsCompat.getSystemWindowInsetBottom();
            left   = insetsCompat.getSystemWindowInsetLeft();
            right  = insetsCompat.getSystemWindowInsetRight();
        }

        // 强制推送（不去重）— 页面重载后 CSS 变量会丢，必须每次都写
        String js =
            "(function(){var r=window.devicePixelRatio||1;" +
            "var s=document.documentElement.style;" +
            "s.setProperty('--status-bar-height',(" + top    + "/r)+'px');" +
            "s.setProperty('--nav-bar-height',   (" + bottom + "/r)+'px');" +
            "s.setProperty('--safe-left',        (" + left   + "/r)+'px');" +
            "s.setProperty('--safe-right',       (" + right  + "/r)+'px');" +
            "console.log('[insets] raw=" + top + "/" + bottom + "/" + left + "/" + right +
            " dpr='+r+' -> top='+((" + top + ")/r)+'px');" +
            "})();";

        runOnUiThread(() -> {
            WebView wv = findWebView();
            if (wv != null) {
                wv.evaluateJavascript(js, null);
            }
        });
    }

    /**
     * 返回键逻辑：
     *   1. WebView history 栈有记录 → goBack()（页面内路由回退）
     *   2. history 栈空 → 双击退出（2s 内再按才退出）
     *
     * 为什么不依赖 Capacitor BridgeActivity 默认的 back handling？
     *   因为 BridgeActivity 只有在 Bridge 完全初始化并注册了 back button
     *   handler 时才会正确委托给 WebView。file:// + createWebHistory() 场景
     *   下 Bridge handler 的注册时机不稳定，直接从 decorView 拿 WebView
     *   自己处理更可靠。
     */
    @Override
    public void onBackPressed() {
        WebView wv = findWebView();
        if (wv != null && wv.canGoBack()) {
            // 页面有历史 → 走正常回退
            wv.goBack();
            return;
        }
        // 首页：双击退出
        long now = System.currentTimeMillis();
        if (now - lastBackPressTime < EXIT_CONFIRM_WINDOW_MS) {
            // 第二次按 → 真退出
            cleanupAndFinish();
            return;
        }
        lastBackPressTime = now;
        Toast.makeText(this, "再按一次退出青囊", Toast.LENGTH_SHORT).show();
        // 超时自动重置（防止留状态）
        if (resetBackPressRunnable != null) {
            mainHandler.removeCallbacks(resetBackPressRunnable);
        }
        resetBackPressRunnable = () -> lastBackPressTime = 0;
        mainHandler.postDelayed(resetBackPressRunnable, EXIT_CONFIRM_WINDOW_MS);
    }

    private void cleanupAndFinish() {
        try {
            WebView wv = findWebView();
            if (wv != null) {
                wv.stopLoading();
            }
        } catch (Throwable ignored) {}
        finish();
    }
}
