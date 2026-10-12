package com.qingnang.app;

import android.os.Build;
import android.os.Bundle;
import android.view.View;
import android.view.WindowManager;
import android.view.WindowInsets;
import androidx.core.view.ViewCompat;
import androidx.core.view.WindowCompat;
import androidx.core.view.WindowInsetsCompat;
import androidx.core.view.WindowInsetsControllerCompat;

import com.getcapacitor.BridgeActivity;

public class MainActivity extends BridgeActivity {
    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        // 1) Edge-to-edge：内容铺满，让 WindowInsets 决定谁让开
        WindowCompat.setDecorFitsSystemWindows(getWindow(), false);

        // 2) 图标明暗（浅背景 → 深色图标）
        WindowInsetsControllerCompat wic =
            WindowCompat.getInsetsController(getWindow(), getWindow().getDecorView());
        if (wic != null) {
            wic.setAppearanceLightStatusBars(true);
            wic.setAppearanceLightNavigationBars(true);
        }

        // 3) 实时监听 WindowInsets → 传给 JS
        //    覆盖状态栏 + 挖孔 + 导航栏 + 手势条
        //    旋转/分屏/折叠屏/沉浸式切换 → 自动重触发
        ViewCompat.setOnApplyWindowInsetsListener(
            getWindow().getDecorView(),
            (v, insetsCompat) -> {
                android.view.WindowInsets raw = insetsCompat.toWindowInsets();
                if (raw == null) return insetsCompat;

                int top, bottom, left, right;
                if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) {
                    // Android 11+：用更干净的 WindowInsets.getInsets(Type)
                    top    = raw.getInsets(WindowInsets.Type.systemBars() | WindowInsets.Type.displayCutout()).top;
                    bottom = raw.getInsets(WindowInsets.Type.systemBars() | WindowInsets.Type.displayCutout()).bottom;
                    left   = raw.getInsets(WindowInsets.Type.systemBars() | WindowInsets.Type.displayCutout()).left;
                    right  = raw.getInsets(WindowInsets.Type.systemBars() | WindowInsets.Type.displayCutout()).right;
                } else {
                    // 旧版：systemWindowInset 已经包含状态栏，
                    // cutout 在 API 28 以下不存在，这里 fallback
                    top    = raw.getSystemWindowInsetTop();
                    bottom = raw.getSystemWindowInsetBottom();
                    left   = raw.getSystemWindowInsetLeft();
                    right  = raw.getSystemWindowInsetRight();
                }

                String js =
                    "document.documentElement.style.setProperty('--status-bar-height', '" + top    + "px');" +
                    "document.documentElement.style.setProperty('--nav-bar-height',    '" + bottom + "px');" +
                    "document.documentElement.style.setProperty('--safe-left',         '" + left   + "px');" +
                    "document.documentElement.style.setProperty('--safe-right',        '" + right  + "px');";
                runOnUiThread(() -> {
                    if (getBridge() != null && getBridge().getWebView() != null) {
                        getBridge().getWebView().evaluateJavascript(js, null);
                    }
                });
                return insetsCompat;
            }
        );
    }
}
