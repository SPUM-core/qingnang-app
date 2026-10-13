"""修复 APP_UPDATE_BASE_URL → 80 端口 + regenerate manifest"""
import paramiko

HOST = '110.40.143.164'
USER = 'ubuntu'
PASS = 'Hu@697758521'

def run(ssh, cmd, timeout=30):
    print(f'▶ {cmd}')
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode().strip()
    err = stderr.read().decode().strip()
    rc = stdout.channel.recv_exit_status()
    if out: print(out[:500])
    if err and rc != 0: print(f'⚠️ {err[:300]}')
    print(f'  → exit={rc}\n')
    return rc == 0

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST, username=USER, password=PASS, timeout=10)
print('✅ 已连接\n')

# 1. 把 systemd unit 里的 :8767 改成 80 端口
print('=== Step 1: 修改 systemd unit ===')
run(ssh, '''sudo sed -i 's|APP_UPDATE_BASE_URL=http://110.40.143.164:8767/updates|APP_UPDATE_BASE_URL=http://110.40.143.164/updates|g' /etc/systemd/system/qingnang-backend.service''')

# 2. 验证改对了
run(ssh, '''sudo cat /etc/systemd/system/qingnang-backend.service | grep Environment=''')

# 3. daemon-reload + restart
print('=== Step 2: systemd reload + restart ===')
run(ssh, 'sudo systemctl daemon-reload')
run(ssh, 'sudo systemctl restart qingnang-backend')
import time; time.sleep(2)
run(ssh, 'sudo systemctl is-active qingnang-backend')

# 4. regenerate manifest（这次后端用新的 APP_UPDATE_BASE_URL=http://110.40.143.164/updates）
print('=== Step 3: regenerate manifest ===')
run(ssh, 'curl -s -X POST http://127.0.0.1:8767/api/v1/version/manifest/regenerate | python3 -m json.tool')

# 5. 验证 manifest URL 已改
print('=== Step 4: 验证 manifest ===')
run(ssh, '''curl -s http://127.0.0.1:8767/api/v1/version/manifest | python3 -c "
import sys, json
m = json.load(sys.stdin)
url = m['platforms']['android']['url']
print(f'URL: {url}')
assert ':8767' not in url, '❌ 还有 8767 端口！'
print('✅ 8767 端口已移除')
"''')

# 6. 验证公网下载
print('=== Step 5: 公网下载测试（80端口）===')
run(ssh, 'curl -s -o /dev/null -w "HTTP %{http_code} %{size_download}B\\n" http://110.40.143.164/updates/qingnang-v0.1.5.apk')

ssh.close()
print('🎉 修复完成！')
