# -*- coding: utf-8 -*-
"""青囊一键发布脚本 — 版本号单信源 build.gradle 的 bump / 发布 / manifest 生成。

用法:
    python scripts/release.py bump patch          # 0.1.0 → 0.1.1
    python scripts/release.py bump minor          # 0.1.0 → 0.2.0
    python scripts/release.py bump major          # 0.1.0 → 1.0.0
    python scripts/release.py set 0.3.0           # 直接指定版本
    python scripts/release.py bump patch --apk <path>  # bump 后把 APK 拷入 updates/ 并生成 manifest

说明:
    1. ✅ 同时修改两处：
       - frontend/android/app/build.gradle（versionCode+1, versionName）
       - version.json（项目根目录，保持同步）
    2. --apk 会把文件拷为 backend/updates/qingnang-v{ver}.apk
    3. 默认调用 POST /api/v1/version/manifest/regenerate 自动生成 manifest.json
    4. vite.config.js 从 build.gradle 读版本 → 永远和 APK 内部一致
"""
import argparse
import hashlib
import json
import re
import shutil
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VERSION_FILE = ROOT / "version.json"
GRADLE_FILE = ROOT / "frontend" / "android" / "app" / "build.gradle"
UPDATES_DIR = ROOT / "backend" / "updates"
REGEN_URL = "http://localhost:8767/api/v1/version/manifest/regenerate"


# ── 读写 version.json ──
def read_version_json() -> str:
    try:
        return json.loads(VERSION_FILE.read_text(encoding="utf-8"))["version"]
    except Exception:
        return "0.1.0"


def write_version_json(ver: str) -> None:
    VERSION_FILE.write_text(json.dumps({"version": ver}, indent=2) + "\n", encoding="utf-8")


# ── 读写 build.gradle ──
def read_gradle_version() -> tuple:
    """返回 (versionCode: int, versionName: str)"""
    try:
        text = GRADLE_FILE.read_text(encoding="utf-8")
        code_m = re.search(r'versionCode\s+(\d+)', text)
        name_m = re.search(r'versionName\s+["\'](\d+\.\d+\.\d+)["\']', text)
        code = int(code_m.group(1)) if code_m else 0
        name = name_m.group(1) if name_m else "0.1.0"
        return code, name
    except Exception:
        return 0, "0.1.0"


def write_gradle_version(ver: str, bump_code: bool = True) -> None:
    """写 build.gradle 的 versionName，versionCode 默认 +1。"""
    old_code, old_name = read_gradle_version()
    new_code = old_code + 1 if bump_code else old_code

    text = GRADLE_FILE.read_text(encoding="utf-8")
    text = re.sub(
        r'(versionCode\s+)\d+',
        rf'\g<1>{new_code}',
        text,
    )
    text = re.sub(
        r'(versionName\s+["\'])\d+\.\d+\.\d+(["\'])',
        rf'\g<1>{ver}\g<2>',
        text,
    )
    GRADLE_FILE.write_text(text, encoding="utf-8")
    print(f"  build.gradle: {old_name}(code={old_code}) → {ver}(code={new_code})")


# ── Semver bump ──
def bump(ver: str, part: str) -> str:
    major, minor, patch = (int(x) for x in ver.split("."))
    if part == "major":
        return f"{major + 1}.0.0"
    if part == "minor":
        return f"{major}.{minor + 1}.0"
    return f"{major}.{minor}.{patch + 1}"


# ── APK 工具 ──
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
    ap = argparse.ArgumentParser(description="青囊版本发布脚本（单信源：build.gradle）")
    ap.add_argument("action", choices=["bump", "set"], help="bump=递增版本, set=直接指定")
    ap.add_argument("target", help="bump: major|minor|patch；set: x.y.z")
    ap.add_argument("--apk", default=None, help="APK 文件路径（拷入 updates/ 并生成 manifest）")
    ap.add_argument("--no-regen", action="store_true", help="跳过 manifest 自动生成")
    ap.add_argument("--no-code-bump", action="store_true", help="不自动递增 versionCode（仅 set 时可能需要）")
    args = ap.parse_args()

    # 读取当前版本（从 build.gradle，单信源）
    _, old_ver = read_gradle_version()
    new_ver = bump(old_ver, args.target) if args.action == "bump" else args.target

    # 校验 x.y.z
    parts = new_ver.split(".")
    if len(parts) != 3 or not all(p.isdigit() for p in parts):
        print(f"❌ 非法版本号: {new_ver}（需 MAJOR.MINOR.PATCH）")
        return 1

    print(f"📦 版本升级: {old_ver} → {new_ver}")

    # 同时修改两处（确保永远同步）
    write_gradle_version(new_ver, bump_code=not args.no_code_bump)
    write_version_json(new_ver)
    print(f"  version.json: → {new_ver}")

    if args.apk:
        src = Path(args.apk)
        if not src.is_file():
            print(f"❌ APK 不存在: {src}")
            return 1
        UPDATES_DIR.mkdir(parents=True, exist_ok=True)
        dst = UPDATES_DIR / f"qingnang-v{new_ver}.apk"
        shutil.copy2(src, dst)
        print(f"✅ APK 已拷入: {dst}")
        print(f"   SHA256: {sha256_file(dst)}")
        print(f"   大小:   {dst.stat().st_size} 字节")
        if not args.no_regen:
            regenerate_manifest()
    elif not args.no_regen:
        regenerate_manifest()

    print("✅ 完成！")
    return 0


if __name__ == "__main__":
    sys.exit(main())
