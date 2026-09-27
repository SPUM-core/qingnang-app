"""青囊后端启动脚本 - 不 reload 以便看完整 traceback"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import uvicorn
uvicorn.run("app.main:app", host="0.0.0.0", port=8767, reload=False, log_level="debug")
