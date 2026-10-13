"""一键部署脚本：git pull → 前端 rsync → 清缓存 → 重启后端 → 上传 APK → regenerate manifest"""
import sys
import time
from pathlib import Path
import paramiko
from scp import SCPClient

HOST = '110.40.143.164'
USER = 'ubuntu'
PASS = 'Hu@697758521'

APK_LOCAL = Path(r'e:\工作\qingnang-APP\frontend\android\app\build\outputs\apk\debug\app-debug.apk')
DIST_LOCAL = Path(r'e:\工作\qingnang-APP\frontend\dist')

REMOTE_APP = '/home/ubuntu/qingnang-APP'
REMOTE_UPDATES = f'{REMOTE_APP}/backend/updates'
REMOTE_DIST = '/var/www/qingnang'

def run(ssh, cmd, timeout=120):
    print(f'▶ {cmd}')
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode()
    err = stderr.read().decode()
    rc = stdout.channel.recv_exit_status()
    if out:
        print(out.rstrip())
    if err and rc != 0:
        print(f'⚠️ stderr: {err.rstrip()}')
    print(f'  → exit={rc}')
    return rc == 0, out, err

def main():
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    print(f'🔑 连接 {USER}@{HOST} ...')
    ssh.connect(HOST, username=USER, password=PASS, timeout=10)
    print('✅ SSH 连接成功')

    # ── 1. Git pull ──
    print('\n=== Step 1: git pull ===')
    ok, _, _ = run(ssh, f'cd {REMOTE_APP} && git pull origin master')
    if not ok:
        print('❌ git pull 失败')
        return 1

    # ── 2. rsync 前端 dist ──
    print('\n=== Step 2: rsync frontend/dist → /var/www/qingnang ===')
    # 用 SFTP 手动同步（paramiko 没有内置 rsync）
    print('  (paramiko sftp 上传...)')
    sftp = ssh.open_sftp()
    
    def upload_dir(local: Path, remote: str):
        try:
            sftp.stat(remote)
        except FileNotFoundError:
            sftp.mkdir(remote)
        for f in local.iterdir():
            r = f'{remote}/{f.name}'
            if f.is_dir():
                upload_dir(f, r)
            else:
                print(f'    {f.name}')
                sftp.put(str(f), r)
    
    # 先删旧的（等价 rsync --delete）
    run(ssh, f'rm -rf {REMOTE_DIST}/*')
    upload_dir(DIST_LOCAL, REMOTE_DIST)
    sftp.close()
    print('✅ 前端部署完成')

    # ── 3. 清缓存 + 重启后端 ──
    print('\n=== Step 3: 清缓存 + 重启后端 ===')
    run(ssh, 'rm -rf ~/.qingmeng/cache/lifestyle_*_2026101[23]_*')
    run(ssh, 'sudo systemctl restart qingnang-backend')
    time.sleep(2)
    run(ssh, 'sudo systemctl is-active qingnang-backend')
    
    # 健康检查
    ok, out, _ = run(ssh, 'curl -s http://127.0.0.1:8767/health')
    if 'ok' in (out or '') or ok:
        print(f'✅ 后端健康检查: {out.strip()[:80]}')
    else:
        print('⚠️ 健康检查异常')

    # ── 4. 上传 APK ──
    print('\n=== Step 4: 上传 APK ===')
    apk_remote = f'{REMOTE_UPDATES}/qingnang-v0.1.5.apk'
    print(f'  本地: {APK_LOCAL} ({APK_LOCAL.stat().st_size:,} bytes)')
    print(f'  远端: {apk_remote}')
    scp = SCPClient(ssh.get_transport())
    scp.put(str(APK_LOCAL), apk_remote)
    scp.close()
    
    # 计算远端 sha256
    ok, out, _ = run(ssh, f'sha256sum {apk_remote}')
    print(f'  SHA256: {out.split()[0] if out.strip() else "?"}')

    # ── 5. regenerate manifest ──
    print('\n=== Step 5: regenerate manifest ===')
    ok, out, _ = run(ssh, 'curl -s -X POST http://127.0.0.1:8767/api/v1/version/manifest/regenerate')
    print(f'  manifest: {out[:300]}')
    
    # 验证
    ok, out, _ = run(ssh, 'curl -s http://127.0.0.1:8767/api/v1/version/manifest')
    import json
    try:
        m = json.loads(out)
        print(f'\n✅ latest_version = {m["latest_version"]}')
        print(f'   android url     = {m["platforms"]["android"]["url"]}')
        print(f'   checksum        = {m["platforms"]["android"]["checksum_sha256"][:16]}...')
        print(f'   size            = {m["platforms"]["android"]["size_bytes"]:,} bytes')
    except Exception:
        print(f'   manifest raw: {out[:200]}')

    # 验证公网下载
    ok, out, _ = run(ssh, 'curl -s -o /dev/null -w "HTTP %{http_code} (%{size_download} bytes)" http://127.0.0.1:8767/updates/qingnang-v0.1.5.apk')
    print(f'\n✅ APK 公网下载测试: {out.strip()}')

    ssh.close()
    print('\n🎉 部署完成！')
    return 0

if __name__ == '__main__':
    sys.exit(main())
