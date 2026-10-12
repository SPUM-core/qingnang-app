# 部署同步与 APP 打包更新手册

> **定位**：本地代码修改 → 服务器部署的全链路操作手册 + 手机端 APP 打包发布注意事项。
> **维护**：2026-10-12 依据实际服务器（110.40.143.164）操作经验整理。
> **版本**：v0.1

---

## 一、部署链路总览

```
本地修改代码
  → ① 本地验证（编译 / pyflakes / 导入链 / 前端构建）
  → ② git add + commit + push（gitee）
  → ③ 服务器 git pull
  → ④ 若含 DB 迁移：alembic upgrade head
  → ⑤ 重启后端 systemd 服务
  → ⑥ 若含前端改动：上传新 dist + 覆盖 Nginx 静态目录
  → ⑦ 线上验证（curl / 浏览器实测）
```

服务器信息：
- 前端入口：`http://110.40.143.164/`（Nginx 80 端口托管 `frontend/dist`）
- 后端 API：`http://110.40.143.164/api/v1/*`（Nginx 反代到 `localhost:8767`）
- 后端服务名：`qingnang-backend`（systemd）
- 仓库位置：`/home/ubuntu/qingnang-APP`
- 远端：`https://gitee.com/space-particle-universe-model/qingnang-app`

---

## 二、本地操作

### 2.1 修改与自检

```bash
# 后端：编译 + 导入链验证
cd e:\工作\qingnang-APP\backend
python -m py_compile <改动的文件>
python -c "from app.xxx import ..."   # 验证关键符号可导入

# 前端：生产构建（产物在 frontend/dist）
cd e:\工作\qingnang-APP\frontend
npm run build
```

**历史教训（必须执行）**：模块化拆分重构极易遗漏符号导入。修复后必须：
1. `py_compile` 全部改动文件
2. 用 `python -c "from ..."` 验证被引用符号（函数/类/常量）确实可导入
3. 有 alembic 迁移时单独编译迁移文件

> ⚠️ 已有 2 次线上 500 因遗漏导入导致：`build_response_schema_prompt`、`AIResponseTemplate`、`_generate_generic_reply`、`_call_qingmeng_lifestyle`（reasoning.py 相对导入层级错写 3 次）。

### 2.2 提交与推送

```bash
cd e:\工作\qingnang-APP
git add <具体文件>            # 不要 git add -A（会误提交 updates/*.apk 大文件）
git commit -m "fix: 说明改了什么"
git push origin master
```

> ⚠️ 注意 `backend/updates/*.apk` 是部署产物，**不要**提交进仓库（体积大）。若本地 untracked 里有，提交时逐个指定文件即可。

---

## 三、服务器部署

### 3.1 标准部署命令

```bash
cd /home/ubuntu/qingnang-APP
git log -1 --oneline        # 确认本地版本与远端一致
git pull
cd backend
.venv/bin/alembic current   # 若本次有迁移，先看当前版本
# 若有新增迁移：
.venv/bin/alembic upgrade head
sudo systemctl restart qingnang-backend
```

### 3.2 数据库迁移注意事项（重点风险区）

| 风险 | 现象 | 处理 |
|------|------|------|
| **多 head** | `Multiple head revisions are present` | 迁移链存在未合并分支。查看 `alembic heads`，用 `alembic merge -m "merge heads" <rev1> <rev2>` 生成合并迁移，先提交推送再 upgrade |
| **列已存在** | `DuplicateColumn` / `column ... already exists` | 之前手动补过列（如 birth_city）。对该迁移执行 `alembic stamp <该迁移id>` 跳过，或按实际报错处理 |
| **版本漂移** | `alembic current` 落后 | 迁移链按「已标记版本 + 祖先链」推断，手动 stamp 过某版本后，其祖先不会重跑 |

**关键认知**：`alembic_version` 只存一个值，按链推断祖先「已应用」。手动 stamp 的版本及其祖先均视为已应用，不会重复执行——这既是保护，也是坑（确认 stamp 前版本链是对的）。

### 3.3 前端 dist 上传（仅当有前端改动）

服务器 Nginx root 目录托管的是**仓库内 `frontend/dist`** 还是独立目录，需先确认：

```bash
sudo grep -r "root " /etc/nginx/sites-enabled/ /etc/nginx/conf.d/ 2>/dev/null | grep -v "#"
```

若 Nginx 直接指向 `/home/ubuntu/qingnang-APP/frontend/dist`，则：

```powershell
# 本地 PowerShell 执行
scp -r "e:\工作\qingnang-APP\frontend\dist\*" ubuntu@110.40.143.164:/home/ubuntu/qingnang-APP/frontend/dist/
```

**注意**：
- 覆盖前先备份：`cp -r dist dist_bak_$(date +%Y%m%d)`
- 确认上传后首页 HTML 引用的 JS hash（`index-*.js`）与本地一致，否则浏览器还在旧版本
- Nginx 静态目录用缓存时，必要时 `sudo nginx -s reload` 或清缓存

### 3.4 部署后验证

```bash
# 后端健康
curl -s http://110.40.143.164/api/v1/assistant/health
# 应返回 {"llm":{"provider":"deepseek","configured":true,...}}

# AI 对话
curl -s -X POST http://110.40.143.164/api/v1/assistant/chat \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>" \
  -d '{"message":"推荐今天吃什么","history":[]}' -w "\nHTTP=%{http_code}\n"

# 生活提醒
curl -s -X POST http://110.40.143.164/api/v1/assistant/reasoning/lifestyle \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>" \
  -d '{}' -w "\nHTTP=%{http_code}\n"
# 期望：200，engine 字段 = llm 或 unified
```

**重要**：需要 token 的接口用裸 curl 会得到 422 `missing authorization`——这不是后端 bug，是缺 `Authorization: Bearer` 头。前端 axios 拦截器会自动附加，页面实测正常。

---

## 四、常见线上问题速查

| 现象 | 根因 | 处理 |
|------|------|------|
| AI 对话 500 秒崩（0.06s） | 后端遗漏导入 / 相对导入层级错 | 修导入，先本地验证再部署 |
| 所有接口 422 missing authorization | 客户端 token 失效/未带 | 重新登录；或用带 Bearer 的 curl 复验 |
| lifestyle 返回 `engine=backend_fallback_rule` | 青檬引擎（qingmeng-engine，localhost:8000）未运行 | **预期内优雅降级**，不影响功能；现已改 DeepSeek 优先，engine=llm |
| health 返回 `qingmeng: unreachable` | 青檬引擎未启动 | 同上，2核4G 机器不做模型推理，属预期 |
| 页面加载旧 JS（index-CwciRj94 等） | Nginx dist 未覆盖 | 上传新 dist + 确认 hash |
| 弹窗无「做法/出处」 | LLM 生成时字段缺失（重构遗漏） | 2026-10-11 已全链路补齐 detail/source_ref，部署后生效 |

---

## 五、APP 打包更新注意事项

### 5.1 版本号单一信源

- 根目录 `version.json` 是唯一版本信源（`vite.config.js` 读取；读不到回退 package.json）
- 发布新版本先改 `version.json` 的 `version` 字段

### 5.2 前端 API 地址

- 手机端必须用服务器地址：`frontend/.env.production` 设 `VITE_API_BASE=http://110.40.143.164`
- 本地 dev 回退 `http://localhost:8767`（vite proxy 已配）
- 后端在 8767 已监听 0.0.0.0（腾讯云防火墙已放行）

### 5.3 打包流程

```bash
cd e:\工作\qingnang-APP\frontend
npm run build                 # 生成 web dist（托管在 Nginx，网页版也用）
npx cap sync android          # 同步 web 资源到 Android 工程
# 构建 APK（Android Studio 或命令行 gradle）
# 产物：frontend/android/app/build/outputs/apk/release/app-release.apk
```

### 5.4 发布到更新目录

1. 重命名 APK：`qingnang-v0.1.1.apk`（命名规则：`qingnang-v{MAJOR.MINOR.PATCH}.apk`）
2. 复制到 `backend/updates/`
3. 生成 manifest：

```
POST http://110.40.143.164/api/v1/version/manifest/regenerate
```

后端自动扫描目录取最高版本 + 计算 SHA256 + 写 `manifest.json`。

> manifest.json 存在时优先级最高（不再自动扫描）——手管时注意字段：`latest_version` / `min_required_version` / `force_update` / `platforms.android.url / checksum_sha256 / size_bytes / update_note`。

### 5.5 APP 更新注意事项

| 事项 | 说明 |
|------|------|
| **APK 不进 git** | `backend/updates/*.apk` 是部署产物，勿提交（体积大） |
| **状态栏适配** | APK 0.1.1 已做 safe-area 适配；改 UI 后注意保留 `viewport-fit=cover` 与 safe-area 样式 |
| **版本递增** | 每次发布先改 `version.json`，再打包，否则用户不会收到更新 |
| **校验和** | 前端下载后校验 `checksum_sha256`，防止篡改 |
| **HTTPS 建议** | 生产强烈建议 CDN + HTTPS（当前为 http，APK 传输可被中间人替换，低风险可接受） |
| **force_update** | 有破坏性 DB 变更时设 `min_required_version` 强制老版本升级，避免不兼容 |
| **网页版同步** | 每次打包前 `npm run build` 的 dist 也要上传服务器（APP 与网页版共用同一份 dist） |

### 5.6 一次完整发布流程（示例 0.1.2）

```bash
# 1. 本地
改 version.json → 0.1.2
cd frontend && npm run build && npx cap sync android
# Android Studio 构建 release APK

# 2. 更新目录
copy app-release.apk backend\updates\qingnang-v0.1.2.apk
# 部署后调 regenerate 接口生成 manifest

# 3. 部署（同第三节）
git push → 服务器 git pull → 重启后端（updates/ 在仓库内则随 pull 同步）
scp dist → 覆盖 Nginx 目录

# 4. 验证
curl /api/v1/version/manifest/regenerate   # 或 GET 版本接口确认 latest=0.1.2
浏览器实测更新弹窗出现
```

---

## 六、操作纪律（红线）

1. **部署前必须本地自检通过**——编译 + 导入链 + 前端构建，缺一不可
2. **有迁移先 `alembic current` 再 `upgrade head`**——遇到 Duplicate Column 立即停，贴报错，不要硬冲
3. **APK / dist 产物不进 git 提交**——只提交源码
4. **改前端必传 dist**——服务器 80 端口是旧版时，页面功能「缺失」往往不是后端问题
5. **验证用带 Bearer 的 curl 或浏览器实测**——裸 curl 的 422 是缺 token，别误判为 bug
6. **青檬引擎 unreachable 是预期**——已改 DeepSeek 优先，无需处理
