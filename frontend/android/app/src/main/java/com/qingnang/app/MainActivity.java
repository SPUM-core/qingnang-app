package com.qingnang.app;

import android.os.Build;
import android.os.Bundle;
import android.view.View;
import android.view.WindowManager;
import android.view.WindowInsetsController;
import androidx.core.view.WindowCompat;
import androidx.core.view.WindowInsetsCompat;
import androidx.core.view.WindowInsetsControllerCompat;

import com.getcapacitor.BridgeActivity;

public class MainActivity extends BridgeActivity {
    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        // Edge-to-edge：透明状态栏 + WebView 延伸到状态栏后面
        WindowCompat.setDecorFitsSystemWindows(getWindow(), false);

        WindowInsetsControllerCompat wic = WindowCompat.getInsetsController(
            getWindow(), getWindow().getDecorView());
        if (wic != null) {
            wic.setAppearanceLightStatusBars(true);
            wic.setAppearanceLightNavigationBars(true);
        }

        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            getWindow().setNavigationBarContrastEnforced(false);
        }

        // ⚠️ 关键：原生计算状态栏高度 → 传给 CSS 变量
        // env(safe-area-inset-top) 在部分 ROM（MIUI/HyperOS）返回 0
        // 直接用资源值算最可靠
        int statusBarH = calcStatusBarHeight();
        int navBarH    = calcNavBarHeight();
        final String js =
            "document.documentElement.style.setProperty('--status-bar-height', '" + statusBarH + "px');" +
            "document.documentElement.style.setProperty('--nav-bar-height', '"    + navBarH    + "px');";
        // 等 WebView ready 再 evaluate（post 到主线程队列末尾）
        if (getBridge() != null && getBridge().getWebView() != null) {
            getBridge().getWebView().post(() ->
                getBridge().getWebView().evaluateJavascript(js, null));
        }
    }

    /** 反射读取系统 status_bar_height 资源（几乎所有 ROM 都有） */
    private int calcStatusBarHeight() {
        int resId = getResources().getIdentifier("status_bar_height", "dimen", "android");
        return resId > 0 ? getResources().getDimensionPixelSize(resId) : 0;
    }

    /** 反射读取系统 navigation_bar_height 资源 */
    private int calcNavBarHeight() {
        int resId = getResources().getIdentifier("navigation_bar_height", "dimen", "android");
        return resId > 0 ? getResources().getDimensionPixelSize(resId) : 0;
    }
}
