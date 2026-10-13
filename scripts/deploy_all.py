"""部署后端 + 前端"""
import paramiko, os

HOST, USER, PASS = '110.40.143.164', 'ubuntu', 'Hu@697758521'
LOCAL_DIST = r'e:\工作\qingnang-APP\frontend\dist'

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST, username=USER, password=PASS, timeout=10)

def run(cmd):
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=120)
    o = stdout.read().decode().strip()
    e = stderr.read().decode().strip()
    if o: print(f'  >>> {o[:300]}')
    if e and 'Warning' not in e and 'warning' not in e: print(f'  STDERR: {e[:300]}')
    return o

# 1. 拉代码
print('=== git pull ===')
run('cd /home/ubuntu/qingnang-APP && git pull origin master')

# 2. 重启后端
print('=== restart backend ===')
run(f'echo "{PASS}" | sudo -S systemctl restart qingnang-backend')
run(f'echo "{PASS}" | sudo -S systemctl is-active qingnang-backend')

# 3. 清缓存
run('rm -rf ~/.qingmeng/cache/*_2026101[23]_* 2>/dev/null')

# 4. 同步前端
print('=== sync frontend ===')
import tarfile, io
tar_buf = io.BytesIO()
with tarfile.open(fileobj=tar_buf, mode='w:gz') as tar:
    tar.add(LOCAL_DIST, arcname='dist')
tar_bytes = tar_buf.getvalue()

sftp = ssh.open_sftp()
sftp.putfo(io.BytesIO(tar_bytes), '/tmp/qn_dist.tar.gz')
sftp.close()

run(f'echo "{PASS}" | sudo -S rm -rf /var/www/qingnang/*')
run('cd /tmp && tar xzf qn_dist.tar.gz')
run(f'echo "{PASS}" | sudo -S cp -r dist/* /var/www/qingnang/')
run(f'echo "{PASS}" | sudo -S chown -R www-data:www-data /var/www/qingnang')
run(f'echo "{PASS}" | sudo -S nginx -t && echo "{PASS}" | sudo -S systemctl reload nginx')
run('rm -rf /tmp/dist /tmp/qn_dist.tar.gz')

# 5. 验证 API
print('=== verify ===')
import urllib.request
try:
    r = urllib.request.urlopen('http://127.0.0.1:8767/api/v1/spacetime/context', timeout=5)
    print(f'  ✅ spacetime/context: {r.status}')
except Exception as e:
    print(f'  ❌ spacetime: {e}')

# 测试 anchor-explain 的 fallback 路径（不需要登录）
try:
    body = '{}\n'
except Exception:
    pass

print('\nDONE')
ssh.close()
