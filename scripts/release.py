# -*- coding: utf-8 -*-
"""青囊一键发布脚本 — 版本号单一信源 version.json 的 bump / 发布 / manifest 生成。

用法:
    python scripts/release.py bump patch          # 0.1.0 → 0.1.1
    python scripts/release.py bump minor          # 0.1.0 → 0.2.0
    python scripts/release.py bump major          # 0.1.0 → 1.0.0
    python scripts/release.py set 0.3.0           # 直接指定版本
    python scripts/release.py bump patch --apk <path>  # bump 后把 APK 拷入 updates/ 并生成 manifest

说明:
    1. 只改根目录 version.json（单一信源）
    2. --apk 会把文件拷为 backend/updates/qingnang-v{ver}.apk
    3. 默认调用 POST /api/v1/version/manifest/regenerate 自动生成 manifest.json
"""
import argparse
import hashlib
import json
import shutil
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VERSION_FILE = ROOT / "version.json"
UPDATES_DIR = ROOT / "backend" / "updates"
REGEN_URL = "http://localhost:8767/api/v1/version/manifest/regenerate"


def read_version() -> str:
    return json.loads(VERSION_FILE.read_text(encoding="utf-8"))["version"]


def write_version(ver: str) -> None:
    VERSION_FILE.write_text(json.dumps({"version": ver}, indent=2) + "\n", encoding="utf-8")


def bump(ver: str, part: str) -> str:
    major, minor, patch = (int(x) for x in ver.split("."))
    if part == "major":
        return f"{major + 1}.0.0"
    if part == "minor":
        return f"{major}.{minor + 1}.0"
    return f"{major}.{minor}.{patch + 1}"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def regenerate_manifest() -> None:
    try:
        req = urllib.request.Request(REGEN_URL, method="POST")
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        print(f"✅ manifest 已生成：latest={data.get('latest_version')}")
    except Exception as exc:
        print(f"⚠️ manifest 重新生成失败（后端可能未启动？）：{exc}")


def main() -> int:
    ap = argparse.ArgumentParser(description="青囊版本发布脚本")
    ap.add_argument("action", choices=["bump", "set"], help="bump=递增版本, set=直接指定")
    ap.add_argument("target", help="bump: major|minor|patch；set: x.y.z")
    ap.add_argument("--apk", default=None, help="APK 文件路径（拷入 updates/ 并生成 manifest）")
    ap.add_argument("--no-regen", action="store_true", help="跳过 manifest 自动生成")
    args = ap.parse_args()

    old = read_version()
    new = bump(old, args.target) if args.action == "bump" else args.target
    # 简单校验 x.y.z 格式
    parts = new.split(".")
    if len(parts) != 3 or not all(p.isdigit() for p in parts):
        print(f"❌ 非法版本号: {new}（需 MAJOR.MINOR.PATCH）")
        return 1

    write_version(new)
    print(f"📦 版本 {old} → {new}（version.json）")

    if args.apk:
        src = Path(args.apk)
        if not src.is_file():
            print(f"❌ APK 不存在: {src}")
            return 1
        UPDATES_DIR.mkdir(parents=True, exist_ok=True)
        dst = UPDATES_DIR / f"qingnang-v{new}.apk"
        shutil.copy2(src, dst)
        print(f"✅ APK 已拷入: {dst}")
        print(f"   SHA256: {sha256_file(dst)}")
        print(f"   大小:   {dst.stat().st_size} 字节")
        if not args.no_regen:
            regenerate_manifest()
    elif not args.no_regen:
        regenerate_manifest()

    return 0


if __name__ == "__main__":
    sys.exit(main())
