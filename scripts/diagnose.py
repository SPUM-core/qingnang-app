"""排查 APK 下载地址不通问题 + 修复"""
import paramiko

HOST = '110.40.143.164'
USER = 'ubuntu'
PASS = 'Hu@697758521'

def run(ssh, cmd, timeout=30):
    print(f'▶ {cmd}')
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode()
    err = stderr.read().decode()
    rc = stdout.channel.recv_exit_status()
    print(out.rstrip()[:500])
    return rc == 0, out, err

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST, username=USER, password=PASS, timeout=10)
print('✅ 已连接\n')

# ── 1. 检查 Nginx 是否反代了 /updates ──
print('=== 1. 检查 Nginx 配置 ===')
run(ssh, 'cat /etc/nginx/sites-enabled/* 2>/dev/null | grep -A5 "updates"')
run(ssh, 'cat /etc/nginx/nginx.conf 2>/dev/null | grep -A5 "updates"')
run(ssh, 'sudo nginx -t 2>&1 | tail -3')

# ── 2. 测试各端口 ──
print('\n=== 2. 测试不同端口的 APK 下载 ===')
run(ssh, 'curl -s -o /dev/null -w "8767后端直连: HTTP %{http_code} %{size_download}B\\n" http://127.0.0.1:8767/updates/qingnang-v0.1.5.apk')
run(ssh, 'curl -s -o /dev/null -w "80端口本机: HTTP %{http_code} %{size_download}B\\n" http://127.0.0.1/updates/qingnang-v0.1.5.apk')
run(ssh, 'curl -s -o /dev/null -w "80端口公网IP: HTTP %{http_code} %{size_download}B\\n" http://110.40.143.164/updates/qingnang-v0.1.5.apk')

# ── 3. 查 manifest 里当前 URL ──
print('\n=== 3. 当前 manifest ===')
run(ssh, 'curl -s http://127.0.0.1:8767/api/v1/version/manifest | python3 -m json.tool 2>/dev/null || curl -s http://127.0.0.1:8767/api/v1/version/manifest')

# ── 4. 改 systemd 环境变量（从 :8767 改成 80 端口）──
print('\n=== 4. 修复 systemd APP_UPDATE_BASE_URL ===')
run(ssh, 'sudo systemctl cat qingnang-backend 2>/dev/null | grep Environment=')

ssh.close()
