# 青囊生活管家 · UI 素材包 (ui-kit)

> 配套画布：Ardot《青囊UI系统方案》(fileId 730051700590884)
> 品牌规范总览：`../brand/qingnang-ui-system-board.png`

## 目录结构

```
ui-kit/
├── tokens/            设计令牌
│   ├── tokens.css     CSS 变量（色彩/字体/圆角/间距）
│   └── tokens.json    结构化令牌（含 tabBar 配置、按钮规格）
├── logo/              Logo 素材（透明底 PNG）
│   ├── icon-green.png        药囊图标 · 墨绿（497×662）
│   ├── icon-light.png        药囊图标 · 米白（用于深色底/图标底）
│   ├── wordmark-green-70.png 「青囊+QINGNANG」字标 · 墨绿 · 70% 扁（横版用）
│   ├── wordmark-green-66.png 字标 · 墨绿 · 66% 扁（竖版用）
│   └── wordmark-light-70.png 字标 · 米白 · 70% 扁
├── appicon/           App 图标（青囊绿底 22% 圆角 + 米白图标）
│   ├── appicon-1024.png   主尺寸（iOS/Android 商店）
│   └── appicon-{192/180/152/120/96/72/48}.png
├── icons/             图标库（48 viewBox · 线性 3px 圆头）
│   ├── svg/           源文件（透明底，改 stroke 色即可换态）
│   └── png/           288px @3x 导出（小程序 tabBar 可直接用）
└── splash/            启动页（国风水墨书法「正气存内，邪不可干」）
    ├── splash-1080x1920.png  Android
    ├── splash-750x1334.png   iPhone
    └── splash-640x1136.png   通用
```

## 色彩速查

| 令牌 | 值 | 用途 |
|---|---|---|
| 青囊绿 | `#17534C` | 主色：按钮、选中态、Logo |
| 松烟绿 | `#2E7D6A` | 辅助：悬浮、描边、次级强调 |
| 玄黑 | `#0B0F0E` | 深色底 |
| 宣纸米 | `#F2EFE7` | 浅色底 |
| 朱砂 | `#A8442F` | 点缀：警示/强调（慎用） |
| 图标未选 | `#A9B5B0` | Tab/图标默认态 |

## 使用约定

1. **Logo 三组合**：横版（图标+字标 70% 扁）、竖版（字标 66% 扁）、浅底一律用**绿色图形**，米白图形只放在青囊绿/玄黑底上。
2. **Tab 栏**（tokens.json → tabBar）：首页 / 养生 / 记录 / 我的，active `#17534C`、inactive `#A9B5B0`，PNG 已按 @3x 输出。
3. **按钮**：全圆角胶囊，高 56、圆角 28；主按钮青囊绿底米白字（字距 4），次按钮描边。
4. **卡片**：深底 `#101614` + 45% 松烟绿描边 + 圆角 16。
5. **动效**：开屏动画参考 `../splash/qingnang-splash-anim.mp4`（墨迹书写 5s）。

## 已知限制

- Logo/字标为位图（单边 ≤500px），放大易虚；定稿后建议矢量重绘。
- `wordmark-light` 仅用于玄黑底；勿放宣纸米底。
