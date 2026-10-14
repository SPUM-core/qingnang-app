# 🧬 青囊 qingnang-app · 新 LLM 助手部署手册

> **新助手接到的第一指令**：读完这个文件 + 检查 `.env` 是否存在 + 跑 `./deploy.ps1`
>
> 所有敏感信息（密码、密钥、服务器 IP）**只在 `.env` 文件里**，别在对话里复现。

---

## 0. 前提检查

```powershell
# 1. .env 存在吗？（没有 → 从 .env.example 复制填真实值）
Test-Path e:\工作\qingnang-APP\.env

# 2. 手机插 USB + 开开发者选项 + 开 USB 调试
# 3. npm install 已跑过（首次）
```

---

## 1. 一键部署（首选）

```powershell
cd e:\工作\qingnang-APP
.\deploy.ps1
```

6 步自动化：
1. 前端 build → `frontend/dist/`
2. 服务器 upload → `fix_sync.py` 用 paramiko ssh 到 `.env` 里的服务器
3. Capacitor sync → 把 dist 复制到 `frontend/android/app/src/main/assets/public/`
4. 手机 installDebug → gradlew 安装 APK
5. git push → origin (Gitee) + github
6. 验证 → 服务器 health check + adb devices

### 跳过选项

```powershell
.\deploy.ps1 -SkipGit           # 只部署不推 Gitee
.\deploy.ps1 -SkipInstall       # 只同步 Capacitor 不装机
.\deploy.ps1 -SkipBuild -SkipDeploy -SkipGit   # 只装机
.\deploy.ps1 -SkipVerify        # 跳过服务器+手机验证
```

---

## 2. 手动各步（排查时用）

### 2a. 前端构建

```powershell
cd e:\工作\qingnang-APP\frontend
npm run build                      # 产物：dist/
```

### 2b. 服务器上传

```powershell
cd e:\工作\qingnang-APP
python scripts/fix_sync.py         # 读 .env → ssh + tar + sudo cp
# 输出: Uploaded tar, >>> 各种远端命令, DONE
# 验证: curl http://110.40.143.164/
```

### 2c. Capacitor 同步（每次前端 dist 变了就要跑）

```powershell
cd e:\工作\qingnang-APP\frontend
Remove-Item -Recurse -Force "android\app\src\main\assets\public\*"
npx cap sync android
```

### 2d. 手机安装

```powershell
# 确保手机连 USB + 开 USB 调试
& "C:\Users\macotai\AppData\Local\Microsoft\WinGet\Packages\Google.PlatformTools_Microsoft.Winget.Source_8wekyb3d8bbwe\platform-tools\adb.exe" devices
# 看到设备后：
cd e:\工作\qingnang-APP\frontend\android
.\gradlew.bat installDebug
# 或者：.\gradlew.bat assembleDebug 然后用 adb install -r app-debug.apk
```

### 2e. Git Push

```powershell
cd e:\工作\qingnang-APP
git remote -v
# origin → gitee.com/space-particle-universe-model/qingnang-app.git
# github → github.com/SPUM-core/qingnang-app.git
git push origin main
git push github main
```

---

## 3. .env 变量速查（别在对话里复述真实值！）

| 变量 | 用途 | 例子 |
|------|------|------|
| `SERVER_HOST` | 服务器 IP | `110.40.143.164` |
| `SERVER_USER` | SSH 用户 | `ubuntu` |
| `SERVER_PASS` | SSH + sudo 密码 | `******` |
| `SERVER_DEPLOY_DIR` | 前端部署目录 | `/var/www/qingnang` |
| `LOCAL_DIST` | 本地前端产物路径 | `e:\工作\qingnang-APP\frontend\dist` |
| `ADB_PATH` | adb.exe 路径 | Windows Platform Tools 默认路径 |
| `ANDROID_GRADLEW` | gradlew.bat | `...frontend\android\gradlew.bat` |
| `SECRET_KEY` | Flask SECRET_KEY | `backend/.env` 里复制来的 |
| `DATABASE_URL` | postgresql | `postgresql+psycopg2://...` |

---

## 4. 常见故障

| 症状 | 原因 | 解决 |
|------|------|------|
| `fix_sync.py` 报 `paramiko` 未装 | 缺依赖 | `pip install paramiko` |
| Capacitor 报 `assets/public not found` | 首次没建目录 | `New-Item -ItemType Directory -Force frontend\android\app\src\main\assets\public` |
| `gradlew installDebug` 报 `adb not found` | adb 不在 PATH | 用 `.env` 的 `ADB_PATH` 或加到系统 PATH |
| 手机装不上 "INSTALL_FAILED_OLDER_SDK" | minSdk 太高 | `frontend/android/app/build.gradle` 改 `minSdkVersion` |
| nginx 403 | 权限不够 | fix_sync.py 里已经 `chown -R www-data`，如果还错手动 `sudo chmod -R 755 /var/www/qingnang` |
| git push 认证失败 | token 过期 | `git remote set-url origin https://<新token>@gitee.com/...` |

---

## 5. 目录结构速查

```
e:\工作\qingnang-APP\
├── .env                  ← 👈 敏感配置（加入 .gitignore）
├── .env.example          ← 示例（不含真实值，可 push）
├── .gitignore
├── deploy.ps1            ← 一键部署脚本（首选）
├── DEPLOY.md             ← 本文件
├── scripts/
│   └── fix_sync.py       ← 服务器上传（读 .env）
├── frontend/
│   ├── package.json
│   ├── vite.config.ts
│   ├── dist/             ← build 产物
│   └── android/
│       ├── gradlew.bat   ← gradle 包装器
│       └── app/build.gradle
└── backend/
    ├── .env              ← backend 自己的（已在 .gitignore）
    └── app/
        ├── api/v1/
        │   ├── router.py
        │   ├── reduction.py    ← 归约算法库 API
        │   └── spacetime.py
        └── utils/
            ├── spacetime_engine.py
            └── reduction_engine.py  ← 归约引擎核心
```

---

## 6. LLM 助手行为准则

1. **永不复现 .env 里的真实值**——对话里用 `$SERVER_HOST` 占位
2. **部署前先检查 .env 是否存在**
3. **优先用 deploy.ps1 一键脚本**，手跑各步只在排查时用
4. **fix_sync.py 失败时先看 paramiko 安装 + 服务器可达性**
5. **手机端问题先跑 `adb devices` 看有没有设备**
6. **Capacitor 报找不到 assets/public 时手动建目录**
