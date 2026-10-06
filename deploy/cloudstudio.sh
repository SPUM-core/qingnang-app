#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════
# 青囊 APP · Cloud Studio 一键部署脚本
# 用法: bash deploy/cloudstudio.sh
# 前提: 已上传代码到 Cloud Studio workspace
# ═══════════════════════════════════════════════════════════
set -e

RED='\033[0;31m'; GREEN='\033[0;32m'; CYAN='\033[0;36m'; YELLOW='\033[1;33m'; NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
BACKEND_DIR="$PROJECT_DIR/backend"
FRONTEND_DIR="$PROJECT_DIR/frontend"

echo -e "${CYAN}🌿 青囊 APP · Cloud Studio 部署${NC}"
echo "项目根: $PROJECT_DIR"
echo

# ── 0. 预览地址生成（Cloud Studio 端口转发） ──
gen_preview() {
  local port=$1
  local key="${X_IDE_SPACE_KEY:-pfgnju}"
  local region="${X_IDE_SPACE_REGION:-ap-guangzhou}"
  local host="${X_IDE_SPACE_HOST:-cloudstudio.work}"
  echo "https://${key}--${port}.${region}.${host}/"
}

# ── 1. 环境检查 ──
echo -e "${YELLOW}## 环境检查${NC}"
python3 --version || { echo "❌ 需要 Python 3"; exit 1; }
node --version || { echo "❌ 需要 Node.js"; exit 1; }
echo

# ── 2. 后端：.env ──
echo -e "${YELLOW}## 后端配置${NC}"
cd "$BACKEND_DIR"

if [ ! -f ".env" ]; then
  cp .env.cloud.example .env
  echo -e "  ${GREEN}✓ 已生成 .env${NC}"
  echo -e "  ${RED}⚠  请编辑 .env 把 DEEPSEEK_API_KEY 换成你自己的${NC}"
  read -rp "  改好了按 Enter 继续... "
else
  echo "  .env 已存在"
fi

echo "  安装后端依赖..."
pip install -q -r requirements.txt 2>/dev/null || pip3 install -q -r requirements.txt
echo -e "  ${GREEN}✓ 后端依赖就绪${NC}"
echo

# ── 3. 前端：npm install ──
echo -e "${YELLOW}## 前端依赖${NC}"
cd "$FRONTEND_DIR"
npm install --silent --no-audit --no-fund 2>/dev/null || npm install --silent
echo -e "  ${GREEN}✓ 前端依赖就绪${NC}"
echo

# ── 4. 清理旧进程 ──
echo -e "${YELLOW}## 清理旧进程${NC}"
pkill -f "uvicorn app.main:app" 2>/dev/null || true
pkill -f "vite.*4173" 2>/dev/null || true
sleep 1
echo "  已清理"
echo

# ── 5. 起后端（:8767） ──
echo -e "${YELLOW}## 启动后端 :8767${NC}"
cd "$BACKEND_DIR"
nohup python3 -m uvicorn app.main:app \
  --host 0.0.0.0 --port 8767 \
  --log-level info \
  > /tmp/qingnang-backend.log 2>&1 &
BACK_PID=$!
sleep 3
if kill -0 $BACK_PID 2>/dev/null; then
  echo -e "  ${GREEN}✓ 后端运行中 PID=$BACK_PID${NC}"
else
  echo -e "  ${RED}✗ 后端启动失败${NC}"
  tail -30 /tmp/qingnang-backend.log
  exit 1
fi
echo

# ── 6. 起前端 Vite dev server（:4173，自带 proxy /api → 后端） ──
echo -e "${YELLOW}## 启动前端 Vite dev :4173${NC}"
cd "$FRONTEND_DIR"
nohup npx vite --host 0.0.0.0 --port 4173 --strictPort \
  > /tmp/qingnang-frontend.log 2>&1 &
FRONT_PID=$!
sleep 4
if kill -0 $FRONT_PID 2>/dev/null; then
  echo -e "  ${GREEN}✓ 前端运行中 PID=$FRONT_PID${NC}"
else
  echo -e "  ${RED}✗ 前端启动失败${NC}"
  tail -30 /tmp/qingnang-frontend.log
  exit 1
fi
echo

# ── 7. 打印 ──
FRONT_URL=$(gen_preview 4173)
BACK_URL=$(gen_preview 8767)

echo -e "${GREEN}╔══════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║  🎉 青囊 APP · Cloud Studio 部署成功！                    ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════════════════════╝${NC}"
echo
echo -e "  ${CYAN}📱 前端（给用户访问）:${NC} ${FRONT_URL}"
echo -e "  ${CYAN}🔧 后端 API Docs:    ${NC} ${BACK_URL}docs"
echo
echo -e "  ${YELLOW}ℹ️  架构${NC}"
echo "  浏览器 → Cloud Studio 端口转发 → Vite Dev :4173"
echo "                                    ↓ proxy /api"
echo "                                 Uvicorn :8767 → SQLite + DeepSeek"
echo
echo -e "  ${YELLOW}⚠  重要${NC}"
echo "  1. 这个 URL 只有当 Cloud Studio 空间运行时才有效"
echo "  2. 空间休眠（默认 30 分钟无操作）后需要重启"
echo "  3. 正式上线请迁移到 CVM（deploy/nginx.conf 已备好）"
echo
echo -e "  ${YELLOW}🛠  运维${NC}"
echo "  后端日志: tail -f /tmp/qingnang-backend.log"
echo "  前端日志: tail -f /tmp/qingnang-frontend.log"
echo "  全部停掉: pkill -f uvicorn; pkill -f vite"
echo "  重跑部署: bash $SCRIPT_DIR/cloudstudio.sh"
echo
echo "✅ 复制前端链接发给用户试试吧！🚀"
