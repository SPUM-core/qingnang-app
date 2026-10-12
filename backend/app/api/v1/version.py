"""APP 版本更新推送 API
=====================
手机端 APP 启动时调用，检查是否有新版本可下载安装。

更新文件组织：
    backend/updates/
    ├── manifest.json          ← 版本元数据（本文件也动态生成一份给 API）
    ├── qingnang-v0.1.0.apk   ← APK 文件（命名规则：qingnang-v{version}.apk）
    └── qingnang-v0.1.1.apk   ← ...

manifest.json 格式（手管）：
{
  "latest_version": "0.1.1",
  "min_required_version": "0.1.0",
  "force_update": false,
  "platforms": {
    "android": {
      "url": "http://cdn.example.com/updates/qingnang-v0.1.1.apk",
      "checksum_sha256": "abc123...",
      "size_bytes": 12345678,
      "update_note": "修复了XXX问题，新增了YYY功能"
    }
  }
}

自动生成 manifest：把 APK 丢进 updates/ 目录，调用 POST /api/v1/version/manifest/regenerate
即可自动从文件名 + SHA256 + 文件大小生成 manifest。
"""
import hashlib
import json
import logging
import re
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel

from app.config import settings

logger = logging.getLogger(__name__)

router = APIRouter()

# ── updates/ 目录解析 ──
BACKEND_DIR = Path(__file__).resolve().parent.parent.parent.parent
UPDATES_DIR = BACKEND_DIR / settings.APP_UPDATE_DIR
MANIFEST_PATH = UPDATES_DIR / "manifest.json"

# APK 文件名正则：qingnang-v{semver}.apk
APK_NAME_RE = re.compile(r"^qingnang-v(\d+\.\d+\.\d+)\.apk$")


class PlatformUpdate(BaseModel):
    url: str
    checksum_sha256: str
    size_bytes: int
    update_note: str = ""


class AppManifest(BaseModel):
    latest_version: str
    min_required_version: str
    force_update: bool = False
    platforms: dict


class UpdateCheckResponse(BaseModel):
    has_update: bool
    latest_version: str
    current_version: str
    force_update: bool = False
    update_url: Optional[str] = None
    checksum_sha256: Optional[str] = None
    size_bytes: Optional[int] = None
    update_note: str = ""
    min_required_version: str = ""
    disabled: bool = False


# ── 版本比较工具 ──

def _parse_semver(version: str) -> tuple[int, int, int]:
    """解析 MAJOR.MINOR.PATCH → (int, int, int)。解析失败返回 (0,0,0) 视为最低。"""
    try:
        parts = version.split(".")
        return tuple(int(p) for p in parts[:3])  # type: ignore[return-value]
    except (ValueError, AttributeError):
        return (0, 0, 0)


def _semver_gt(a: str, b: str) -> bool:
    """a > b？"""
    return _parse_semver(a) > _parse_semver(b)


# ── manifest 生成 ──

def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _scan_updates_dir(base_url: str = "") -> Optional[AppManifest]:
    """扫描 updates/ 目录下的 APK 文件，自动构建 manifest。找不到文件返回 None。

    Args:
        base_url: APK 下载地址前缀（如 "http://110.40.143.164/updates"）。
                  不传则用 settings.APP_UPDATE_BASE_URL（默认 localhost，仅开发用）。
    """
    if not UPDATES_DIR.is_dir():
        return None

    apk_versions: list[tuple[str, Path, int, str]] = []  # (version, path, size, sha256)
    for f in UPDATES_DIR.iterdir():
        if not f.is_file():
            continue
        m = APK_NAME_RE.match(f.name)
        if not m:
            continue
        ver = m.group(1)
        apk_versions.append((ver, f, f.stat().st_size, _sha256_file(f)))

    if not apk_versions:
        return None

    # 取最高版本
    apk_versions.sort(key=lambda x: _parse_semver(x[0]))
    latest_ver, latest_path, size, sha = apk_versions[-1]

    # base_url 优先用传入的，否则回退到 config 默认值
    base = (base_url or settings.APP_UPDATE_BASE_URL).rstrip("/")
    manifest = AppManifest(
        latest_version=latest_ver,
        # 默认不强制升级（用极低版本作底线，除非手动 manifest.json 覆盖）
        min_required_version="0.1.0",
        force_update=False,
        platforms={
            "android": PlatformUpdate(
                url=f"{base}/{latest_path.name}",
                checksum_sha256=sha,
                size_bytes=size,
                update_note=f"青囊 APP v{latest_ver}",
            ).model_dump()
        },
    )
    return manifest


def _load_manifest() -> Optional[AppManifest]:
    """优先从 manifest.json 读（手管），读不到则扫描目录自动生成。"""
    # 1. 手管 manifest.json
    if MANIFEST_PATH.is_file():
        try:
            data = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
            return AppManifest(**data)
        except Exception as exc:
            logger.warning("manifest.json 解析失败，回退自动扫描: %s", exc)

    # 2. 自动扫描
    return _scan_updates_dir()


# ── API 端点 ──

@router.get("/app-update", response_model=UpdateCheckResponse)
def check_app_update(
    version: str = Query(..., description="当前 APP 版本号，如 0.1.0"),
    platform: str = Query("android", description="平台：android / ios"),
):
    """手机端启动时调用，检查是否有新版本。

    版本比较：严格 semver（MAJOR.MINOR.PATCH）。latest > current → has_update=true。
    force_update=true 时 APP 必须强制升级，否则可能有安全/兼容性问题。
    """
    if not settings.APP_UPDATE_ENABLED:
        return UpdateCheckResponse(
            has_update=False,
            latest_version=version,
            current_version=version,
            disabled=True,
        )

    manifest = _load_manifest()
    if manifest is None:
        return UpdateCheckResponse(
            has_update=False,
            latest_version=version,
            current_version=version,
            update_note="服务端暂无新版本",
        )

    platform_info = manifest.platforms.get(platform) if manifest.platforms else None
    if platform_info is None:
        return UpdateCheckResponse(
            has_update=False,
            latest_version=manifest.latest_version,
            current_version=version,
            update_note=f"平台 {platform} 暂无更新",
        )

    has_update = _semver_gt(manifest.latest_version, version)

    # 强制更新：当前版本低于 min_required_version
    below_min = _parse_semver(version) < _parse_semver(manifest.min_required_version)
    force = manifest.force_update or below_min

    return UpdateCheckResponse(
        has_update=has_update,
        latest_version=manifest.latest_version,
        current_version=version,
        force_update=force,
        update_url=platform_info.get("url") if has_update else None,
        checksum_sha256=platform_info.get("checksum_sha256") if has_update else None,
        size_bytes=platform_info.get("size_bytes") if has_update else None,
        update_note=platform_info.get("update_note", "") if has_update else "",
        min_required_version=manifest.min_required_version,
    )


@router.get("/manifest", response_model=AppManifest)
def get_manifest():
    """返回完整的版本 manifest（调试/手动查看用）。"""
    if not settings.APP_UPDATE_ENABLED:
        raise HTTPException(status_code=403, detail="APP updates disabled")
    manifest = _load_manifest()
    if manifest is None:
        raise HTTPException(status_code=404, detail="No APK files found in updates/")
    return manifest


@router.post("/manifest/regenerate", response_model=AppManifest)
def regenerate_manifest(request: Request):
    """手动触发：重新扫描 updates/ 目录，根据 APK 文件名 + SHA256 重新生成 manifest.json。

    下载地址从当前请求的公网 URL 动态推导（优先 settings.APP_UPDATE_BASE_URL 环境变量），
    确保手机端能正确访问到 APK。
    """
    if not UPDATES_DIR.is_dir():
        UPDATES_DIR.mkdir(parents=True, exist_ok=True)

    # 推导 APK 下载基址：
    # 1. 如果 settings.APP_UPDATE_BASE_URL 已显式配置（非默认 localhost），优先用它
    # 2. 否则从当前 Request 动态拼：{scheme}://{host}/updates
    #    （这样无论从哪个域名/端口进来 regenerate，生成的下载地址都是正确的公网地址）
    default_localhost = "http://localhost:8767/updates"
    configured = settings.APP_UPDATE_BASE_URL.rstrip("/")
    if configured and configured != default_localhost.rstrip("/"):
        updates_base = configured
    else:
        # 从 request.base_url 动态推导
        # request.base_url = "http://110.40.143.164:8767/api/v1/version/manifest/regenerate"
        # 我们只取 scheme + host，然后拼 /updates
        updates_base = f"{request.url.scheme}://{request.url.netloc}/updates"

    manifest = _scan_updates_dir(base_url=updates_base)
    if manifest is None:
        raise HTTPException(status_code=404, detail="No APK files found in updates/")

    MANIFEST_PATH.write_text(
        json.dumps(manifest.model_dump(), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    logger.info("manifest 已重新生成: latest=%s, base_url=%s", manifest.latest_version, updates_base)
    return manifest
