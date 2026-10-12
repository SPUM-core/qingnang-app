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

        // Edge-to-edge：让 WebView 能拿到正确的 safe-area-inset
        // 透明状态栏 + 透明导航栏 + 内容延伸到刘海/挖孔区域
        WindowCompat.setDecorFitsSystemWindows(getWindow(), false);

        WindowInsetsControllerCompat wic = WindowCompat.getInsetsController(
            getWindow(), getWindow().getDecorView());
        if (wic != null) {
            // 状态栏图标颜色（浅色背景用深色图标）
            wic.setAppearanceLightStatusBars(true);
            wic.setAppearanceLightNavigationBars(true);
        }

        // Android 10+：导航栏也透明 + 手势导航
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            getWindow().setNavigationBarContrastEnforced(false);
        }
    }
}
