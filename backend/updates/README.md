# APP 更新文件目录

手机端 APP 自动更新所需的 APK 文件和版本元数据。

## 目录结构

```
updates/
├── qingnang-v0.1.0.apk   ← APK 文件（命名规则：qingnang-v{MAJOR.MINOR.PATCH}.apk）
├── qingnang-v0.1.1.apk   ← ...更高版本自动成为最新
└── manifest.json          ← 可选。手管版本信息 + SHA256；不存在时后端自动扫描生成
```

## 发布流程

### 方式一：自动扫描（推荐）

1. 构建 APK：`cd frontend && npm run build && npx cap sync android`
2. 找 APK：`frontend/android/app/build/outputs/apk/debug/app-debug.apk` 或 release 版本
3. 重命名并复制到本目录：

```bash
# 假设当前版本是 0.1.1
copy frontend\android\app\build\outputs\apk\release\app-release.apk updates\qingnang-v0.1.1.apk
```

4. 调用后端接口自动生成 manifest：

```
POST http://localhost:8767/api/v1/version/manifest/regenerate
```

后端会：
- 扫描本目录下所有 `qingnang-v*.apk`
- 取版本号最高的 APK 作为 latest
- 自动计算 SHA256 校验和 + 文件大小
- 写入 manifest.json

### 方式二：手管 manifest.json

创建 manifest.json：

```json
{
  "latest_version": "0.1.1",
  "min_required_version": "0.1.0",
  "force_update": false,
  "platforms": {
    "android": {
      "url": "https://your-cdn.com/updates/qingnang-v0.1.1.apk",
      "checksum_sha256": "abc123...",
      "size_bytes": 12345678,
      "update_note": "新增 XXX 功能，修复 YYYY 问题"
    }
  }
}
```

> manifest.json 优先级最高——存在时后端直接使用，不再自动扫描。

## 版本比较规则

- **semver**：MAJOR.MINOR.PATCH（如 0.1.0 → 0.1.1）
- `has_update` = latest_version > current_version
- `force_update` = min_required_version > current_version（老版本可能不兼容）

## 安全说明

- 生产环境强烈建议配置 CDN（阿里云 OSS / AWS S3）存放 APK，不要直接用后端静态文件服务
- `checksum_sha256` 由前端在下载完成后校验，防止 APK 被篡改
- 建议后端走 HTTPS，防止 APK 在传输中被中间人替换
