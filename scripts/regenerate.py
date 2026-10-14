import paramiko, json

HOST = '110.40.143.164'
USER = 'ubuntu'
PASS = 'Hu@697758521'

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, username=USER, password=PASS, timeout=10)

def run(cmd):
    stdin, stdout, stderr = client.exec_command(cmd, timeout=30)
    out = stdout.read().decode().strip()
    err = stderr.read().decode().strip()
    return out, err

# 1. 确认后端活着
out, err = run(f'curl -s http://127.0.0.1:8767/api/v1/spacetime/context | head -c 100')
print(f"✅ 后端 health: {out[:80]}...")

# 2. regenerate manifest
out, err = run(f'curl -s -X POST http://127.0.0.1:8767/api/v1/version/manifest/regenerate')
print(f"\n=== regenerate 结果 ===")
print(out)

# 3. 验证 manifest
out, err = run('cat /home/ubuntu/qingnang-APP/backend/updates/manifest.json')
print(f"\n=== 当前 manifest.json ===")
print(out)

# 4. 模拟用户检查更新（当前装的 0.1.5，应该有更新到 0.1.6）
out, err = run('curl -s "http://127.0.0.1:8767/api/v1/version/app-update?version=0.1.5&platform=android"')
print(f"\n=== 用户端检查更新 (current=0.1.5) ===")
print(out)

# 5. 验证 APK 可下载（公网）
out, err = run(f'curl -s -o /dev/null -w "HTTP %{{http_code}}  Size: %{{size_download}}\n" http://110.40.143.164/updates/qingnang-v0.1.6.apk')
print(f"\n=== APK 公网可下载验证 ===")
print(out)

client.close()
