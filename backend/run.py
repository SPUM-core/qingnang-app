"""青囊后端启动脚本

本地/云端通用：
  - 自动检测并安装 requirements.txt（绝对路径，不依赖 CWD）
  - sys.path 注入 backend/ 后再 import uvicorn
  - reload=False 以便看完整 traceback
"""
import sys
import subprocess
from pathlib import Path

# 1. 把 backend/ 加入 sys.path
BACKEND_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BACKEND_DIR))

# 2. 自动安装依赖（requirements.txt 就在 backend/ 目录里）
REQ_FILE = BACKEND_DIR / "requirements.txt"
if REQ_FILE.exists():
    try:
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "-r", str(REQ_FILE)],
            check=True,
        )
        print(f"✅ Dependencies installed from {REQ_FILE}")
    except subprocess.CalledProcessError as e:
        print(f"⚠️  pip install failed (may already be installed): {e}")
else:
    print(f"ℹ️  No requirements.txt at {REQ_FILE}, skipping auto-install")

# 3. 启动 uvicorn
import uvicorn
uvicorn.run("app.main:app", host="0.0.0.0", port=8767, reload=False, log_level="debug")
