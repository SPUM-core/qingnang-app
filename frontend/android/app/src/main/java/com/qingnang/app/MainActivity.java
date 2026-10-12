package com.qingnang.app;

import android.os.Build;
import android.os.Bundle;
import android.view.View;
import androidx.core.graphics.Insets;
import androidx.core.view.ViewCompat;
import androidx.core.view.WindowCompat;
import androidx.core.view.WindowInsetsCompat;
import androidx.core.view.WindowInsetsControllerCompat;

import com.getcapacitor.BridgeActivity;

/**
 * 状态栏 / 挖孔 / 导航栏 inset → CSS 变量桥。
 *
 * 背景（为什么之前怎么改都不生效）：
 *   1) 运行时主题被 Capacitor 覆盖成「空壳 AppTheme.NoActionBar」，
 *      导致 styles.xml 里的透明状态栏 / edge-to-edge / cutout 全部失效
 *      → 已在 res/values/styles.xml 覆盖定义同名单修复。
 *   2) 本类早期把 **物理像素** 直接写成 CSS px（'90px'）。
 *      但 Android WebView 在 width=device-width 下，1 CSS px == 1 dp，
 *      所以会得到约 devicePixelRatio 倍（3x 左右）的间距。
 *      → 改为在 JS 侧除以 window.devicePixelRatio 自校准（不依赖手工换算）。
 *
 * 策略：
 *   1) setDecorFitsSystemWindows(false) → WebView 铺满，进入 edge-to-edge
 *   2) systemBars() 与 displayCutout() **分别取、再取 max**（比并集掩码更稳，
 *      部分 ROM 的并集掩码会漏掉 cutout）
 *   3) insets 变化即时推送（旋转 / 分屏 / 挖孔开关 / 字体放大 都会重触发）
 *   4) 兜底 burst 定时重推：远程页面（server.url）加载慢时首次 insets
 *      可能早于 DOM 就绪；页面重载后 CSS 变量也会丢 —— 用几次定时重推覆盖
 */
public class MainActivity extends BridgeActivity {

    private int lastTop = -1, lastBottom = -1, lastLeft = -1, lastRight = -1;

    /** 兜底重推时间点（ms），覆盖远程页加载与重载窗口 */
    private static final long[] REPUSH_DELAYS = { 0L, 150L, 400L, 800L, 1500L, 2500L, 4000L };

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        // 1) Edge-to-edge
        WindowCompat.setDecorFitsSystemWindows(getWindow(), false);

        // 2) 图标明暗（浅色背景 → 深色图标）
        WindowInsetsControllerCompat wic =
            WindowCompat.getInsetsController(getWindow(), getWindow().getDecorView());
        if (wic != null) {
            wic.setAppearanceLightStatusBars(true);
            wic.setAppearanceLightNavigationBars(true);
        }

        // 3) 实时监听 insets 变化
        View decor = getWindow().getDecorView();
        ViewCompat.setOnApplyWindowInsetsListener(decor, (v, insetsCompat) -> {
            pushInsetsToJs(insetsCompat, true);
            return insetsCompat;   // 不消费，交给子 View
        });

        // 4) 兜底 burst
        for (long delay : REPUSH_DELAYS) {
            decor.postDelayed(this::pushFromRootInsets, delay);
        }
    }

    /** 从 rootWindowInsets 取一次当前值并推送 */
    private void pushFromRootInsets() {
        View decor = getWindow().getDecorView();
        if (decor == null) return;
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
            android.view.WindowInsets raw = decor.getRootWindowInsets();
            if (raw != null) {
                pushInsetsToJs(WindowInsetsCompat.toWindowInsetsCompat(raw), true);
            }
        }
    }

    /**
     * 把当前 insets 推给 JS。
     *
     * @param force true = 跳过值去重（用于定时重推：页面重载后 CSS 变量会丢，
     *              但原生侧 lastTop 缓存还在，不去重就会被误判为「已推送」而跳过）
     */
    private void pushInsetsToJs(WindowInsetsCompat insetsCompat, boolean force) {
        if (insetsCompat == null) return;

        int top, bottom, left, right;
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) {
            // 分别取，再取 max —— 比 windowInsetsCompat.getInsets(union) 更稳
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

        if (!force
                && top == lastTop && bottom == lastBottom
                && left == lastLeft && right == lastRight) {
            return;
        }
        lastTop = top; lastBottom = bottom; lastLeft = left; lastRight = right;

        // ⚠️ 单位：原生 insets 是物理像素；Android WebView 下 1 CSS px == 1 dp。
        //    因此必须在 JS 侧除以 window.devicePixelRatio（== density），否则偏大约 3 倍。
        String js =
            "(function(){var r=window.devicePixelRatio||1;" +
            "var s=document.documentElement.style;" +
            "s.setProperty('--status-bar-height',(" + top    + "/r)+'px');" +
            "s.setProperty('--nav-bar-height',   (" + bottom + "/r)+'px');" +
            "s.setProperty('--safe-left',        (" + left   + "/r)+'px');" +
            "s.setProperty('--safe-right',       (" + right  + "/r)+'px');" +
            "s.setProperty('--inset-raw','" + top + "," + bottom + "," + left + "," + right + "');" +
            "console.log('[insets] raw=" + top + "/" + bottom + "/" + left + "/" + right +
            " dpr='+r+' -> top='+((" + top + ")/r)+'px');" +
            "})();";

        runOnUiThread(() -> {
            if (getBridge() != null && getBridge().getWebView() != null) {
                getBridge().getWebView().evaluateJavascript(js, null);
            }
        });
    }
}
