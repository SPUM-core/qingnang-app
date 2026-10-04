# Cloud Studio 免费空间调试指南（qingnang-APP）

> 目的：用腾讯云 Cloud Studio 免费工作空间（1核2G/8GB）远程调试 qingnang-APP。
> 注意：免费空间是**临时开发环境**——闲置会回收、不能对外提供生产服务，正式部署仍需轻量应用服务器。

## 一、新建工作空间弹窗怎么填

| 字段 | 填写 |
|---|---|
| 空间名称 | `qingnang-app` |
| 空间描述 | 青囊生活管家 · FastAPI 后端 + Vue3 前端调试 |
| 代码来源 | **导入仓库** → GitHub → `SPUM-core/qingnang-app`（私有仓库；若弹出 repo 权限授权页，完成授权并 Grant `SPUM-core` 组织） |
| 开发环境 | All in One（full 1.0.0，自带 Python + Node） |
| 规格配置 | 免费版 1核2GB / 8GB |

## 二、导入前：本地先提交推送（重要）

本地有未提交改动，云端只会拉到已推送的代码。当前为 Gitee + GitHub 双远仓：

```bash
cd E:\工作\qingnang-APP
git add -A
git commit -m "sync: 推送本地改动"
git push origin   # Gitee
git push github   # GitHub（Cloud Studio 从这里拉）
```

## 三、进入空间后的初始化

### 1. 后端依赖

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

### 2. 数据库：云端调试先用 SQLite（推荐）

免费空间装 PostgreSQL 麻烦且重启可能丢状态。项目 Phase 0 本就跑在 SQLite（`data/qingnang.db`）上，`.env` 里把 `DATABASE_URL` 改成：

```
DATABASE_URL=sqlite:///./data/qingnang.db
```

PostgreSQL 的 alembic 迁移等回到正式服务器再跑。

### 3. 配置 .env

```bash
cp .env.example .env
# 生成随机 SECRET_KEY
python -c "import secrets; print(secrets.token_hex(32))"
```

编辑 `.env`：
- `SECRET_KEY=` 上一步生成的值
- `DATABASE_URL=sqlite:///./data/qingnang.db`
- `DEEPSEEK_API_KEY=sk-你的key`（云端调试必须用 DeepSeek，qingmeng-engine/Ollama 在云空间里跑不了）
- `AUTO_SEED=true`（首次调试想自动灌种子数据时打开；否则手动 `python seed/seed_data.py`）

⚠️ `.env` 已在 .gitignore 里，不要提交。

### 4. 初始化表结构 + 启动后端

```bash
alembic upgrade head    # SQLite 下如有 PG 专属迁移报错，可改用: python -c "from app.database import Base, engine; import app.models; Base.metadata.create_all(engine)"
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

验证：浏览器访问 Cloud Studio 提示的 8000 端口预览链接 → `/docs` 应能看到 FastAPI Swagger 页。

### 5. 前端

```bash
cd ../frontend
npm install
npm run dev
```

用 Cloud Studio 的**端口预览**打开 5173 端口链接。

### 6. CORS 修正

Cloud Studio 的预览域名（形如 `https://xxx-5173.cloudstudio.work`）与后端 8000 不同源，需加进白名单——编辑 `backend/.env`：

```
CORS_ORIGINS=["http://localhost:5173","https://你的空间名-5173.cloudstudio.work","https://你的空间名-8000.cloudstudio.work"]
```

重启 uvicorn 生效。前端 `vite.config.js` 如配置了 proxy 指向 `localhost:8000`，则 CORS 可不动，走 proxy 更省事。

## 四、免费版限制（提前知道）

1. **闲置回收**：一段时间不用会被回收，代码靠 Gitee 保住——养成随手 `git push` 的习惯。
2. **数据不持久承诺**：SQLite 的调试数据可能随空间回收丢失，重要数据导出或推送。
3. **不能当生产服务器**：无固定公网 IP、无 SLA，正式上线仍按《腾讯云轻量服务器选型》走。
4. **密钥安全**：DEEPSEEK_API_KEY 只放空间内 `.env`，不进 git；空间用完可在设置里删除工作空间。

## 五、调试闭环

本地改代码 → `git push` → Cloud Studio 里 `git pull` → 热重载生效；
云端改动 → `git push` → 本地 `git pull`。Gitee 仓库是唯一真相源。
