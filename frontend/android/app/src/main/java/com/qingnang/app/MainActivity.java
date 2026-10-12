package com.qingnang.app;

import android.os.Build;
import android.os.Bundle;
import android.view.View;
import android.view.WindowManager;
import androidx.core.graphics.Insets;
import androidx.core.view.ViewCompat;
import androidx.core.view.WindowCompat;
import androidx.core.view.WindowInsetsCompat;
import androidx.core.view.WindowInsetsControllerCompat;

import com.getcapacitor.BridgeActivity;

/**
 * 状态栏 / 挖孔 / 导航栏 inset 监听。
 *
 * 策略:
 *   1) WindowCompat.setDecorFitsSystemWindows(false) → edge-to-edge，WebView 铺满
 *   2) WindowInsetsCompat.Type.systemBars() | displayCutout() → 并集取真实 inset
 *   3) 实时监听（旋转/分屏/挖孔开关切换/字体放大都会重触发）
 *   4) evaluateJavascript 直接写 CSS 变量，比 env(safe-area-inset-*) 可靠
 *      （env() 在 MIUI/HyperOS 经常返回 0）
 */
public class MainActivity extends BridgeActivity {

    /** 最后一次传给 JS 的值，用于去重 + fallback 对比 */
    private int lastTop = -1, lastBottom = -1, lastLeft = -1, lastRight = -1;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        // 1) Edge-to-edge
        WindowCompat.setDecorFitsSystemWindows(getWindow(), false);

        // 2) 图标明暗
        WindowInsetsControllerCompat wic =
            WindowCompat.getInsetsController(getWindow(), getWindow().getDecorView());
        if (wic != null) {
            wic.setAppearanceLightStatusBars(true);
            wic.setAppearanceLightNavigationBars(true);
        }

        // 3) 监听 WindowInsets
        ViewCompat.setOnApplyWindowInsetsListener(
            getWindow().getDecorView(),
            (v, insetsCompat) -> {
                pushInsetsToJs(insetsCompat);
                return insetsCompat; // 不消费
            }
        );

        // 4) ⚠️ Capacitor BridgeActivity 有时会吞第一次 insets 事件
        //    保险：onCreate 后延迟 100ms 强制再算一次
        getWindow().getDecorView().postDelayed(() -> {
            View decor = getWindow().getDecorView();
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) {
                android.view.WindowInsets raw = decor.getRootWindowInsets();
                if (raw != null) {
                    pushInsetsToJs(WindowInsetsCompat.toWindowInsetsCompat(raw));
                }
            } else {
                // 旧版：手动用反射读资源（fallback）
                fallbackResourceCalcAndPush();
            }
        }, 200);
    }

    /** 把当前 insets 推给 JS（带去重 + console.log 调试） */
    private void pushInsetsToJs(WindowInsetsCompat insetsCompat) {
        if (insetsCompat == null) return;

        int top, bottom, left, right;
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) {
            // Android 11+：WindowInsetsCompat.getInsets(int) → android.graphics.Insets
            int mask = WindowInsetsCompat.Type.systemBars() | WindowInsetsCompat.Type.displayCutout();
            Insets ins = insetsCompat.getInsets(mask);
            top    = ins.top;
            bottom = ins.bottom;
            left   = ins.left;
            right  = ins.right;
        } else {
            top    = insetsCompat.getSystemWindowInsetTop();
            bottom = insetsCompat.getSystemWindowInsetBottom();
            left   = insetsCompat.getSystemWindowInsetLeft();
            right  = insetsCompat.getSystemWindowInsetRight();
        }

        // 去重
        if (top == lastTop && bottom == lastBottom && left == lastLeft && right == lastRight) {
            return;
        }
        lastTop = top; lastBottom = bottom; lastLeft = left; lastRight = right;

        String js =
            "document.documentElement.style.setProperty('--status-bar-height', '" + top    + "px');" +
            "document.documentElement.style.setProperty('--nav-bar-height',    '" + bottom + "px');" +
            "document.documentElement.style.setProperty('--safe-left',         '" + left   + "px');" +
            "document.documentElement.style.setProperty('--safe-right',        '" + right  + "px');" +
            "console.log('[insets] top="+top+" bottom="+bottom+" left="+left+" right="+right+");";

        runOnUiThread(() -> {
            if (getBridge() != null && getBridge().getWebView() != null) {
                getBridge().getWebView().evaluateJavascript(js, null);
            }
        });
    }

    /** 反射读资源 fallback（WindowInsets 不可用时） */
    private void fallbackResourceCalcAndPush() {
        int topId = getResources().getIdentifier("status_bar_height",    "dimen", "android");
        int navId = getResources().getIdentifier("navigation_bar_height","dimen", "android");
        int top = topId > 0 ? getResources().getDimensionPixelSize(topId) : 48;
        int nav = navId > 0 ? getResources().getDimensionPixelSize(navId) : 0;

        String js =
            "document.documentElement.style.setProperty('--status-bar-height', '"+top+"px');" +
            "document.documentElement.style.setProperty('--nav-bar-height',    '"+nav+"px');" +
            "console.log('[insets-fallback] top="+top+" nav="+nav+");";

        runOnUiThread(() -> {
            if (getBridge() != null && getBridge().getWebView() != null) {
                getBridge().getWebView().evaluateJavascript(js, null);
            }
        });
    }
}
