#!/usr/bin/env bash
# 青囊 · Cloud Studio 免费空间一键初始化（幂等，可重复执行）
# 用法: bash scripts/bootstrap_cloudstudio.sh
set -e
cd "$(dirname "$0")/../backend"

echo "==> [1/4] 安装依赖"
pip install -q -r requirements.txt 2>/dev/null || pip3 install -q -r requirements.txt
echo "    依赖安装完成"

echo "==> [2/4] 生成 .env（已存在则跳过）"
mkdir -p data
if [ ! -f .env ]; then
  SECRET=$(python3 -c "import secrets; print(secrets.token_hex(32))")
  cat > .env <<EOF
# 青囊后端 · Cloud Studio 环境配置（自动生成）
DEBUG=false
SECRET_KEY=$SECRET
DATABASE_URL=sqlite:///./data/qingnang.db
CORS_ORIGINS=["http://localhost:5173","http://127.0.0.1:5173"]
APP_ENV=development
AUTO_SEED=false

# 填入你的 DeepSeek API Key（sk- 开头），前端设置里选 DeepSeek 才能用 AI 对话
DEEPSEEK_API_KEY=
DEEPSEEK_BASE_URL=https://api.deepseek.com/v1
DEEPSEEK_MODEL=deepseek-chat
EOF
  echo "    已生成 .env  ⚠️ 请编辑 backend/.env 填入 DEEPSEEK_API_KEY"
else
  echo "    .env 已存在，跳过"
fi

echo "==> [3/4] 建表"
if alembic upgrade head 2>/dev/null; then
  echo "    alembic 迁移完成"
else
  echo "    alembic 在 SQLite 下不可用，改用 create_all 兜底"
  python3 -c "from app.database import Base, engine; import app.models; Base.metadata.create_all(engine)"
  echo "    create_all 完成"
fi

echo "==> [4/4] 初始化完成"
echo "启动后端:  cd backend && python run.py   （端口 8767，端口预览打开 /docs 验证）"
echo "启动前端:  cd frontend && npm install && npm run dev   （端口 5173）"
