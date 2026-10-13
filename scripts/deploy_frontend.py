"""部署前端到服务器：本地 build → scp 上传 → 验证"""
import subprocess, os, paramiko, sys

HOST = '110.40.143.164'
USER = 'ubuntu'
PASS = 'Hu@697758521'
LOCAL_DIST = os.path.join(os.path.dirname(__file__), '..', 'frontend', 'dist')

def run(ssh, cmd, timeout=60):
    print(f'> {cmd}')
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode().strip()
    err = stderr.read().decode().strip()
    rc = stdout.channel.recv_exit_status()
    if out: print(out[:2000])
    if err and rc != 0: print(f'ERR: {err[:500]}')
    print(f'  exit={rc}\n')
    return rc == 0, out

# Step 1: 本地构建
print('=== Step 1: 本部前端构建 ===')
r = subprocess.run('npx vite build', cwd=os.path.join(LOCAL_DIST, '..'),
                   shell=True, capture_output=True, text=True, timeout=300)
print(r.stdout[-500:] if r.stdout else '')
if r.returncode != 0:
    print(f'BUILD FAILED:\n{r.stderr[-1000:]}')
    sys.exit(1)
print('✅ 构建成功\n')

# Step 2: SSH 连接
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST, username=USER, password=PASS, timeout=10)

# Step 3: 检查服务器上前端位置
print('=== Step 2: 定位服务器前端目录 ===')
ok, nginx_out = run(ssh, 'grep -rh "root\\|proxy_pass" /etc/nginx/sites-enabled/ 2>/dev/null | head -10')

# 确定目标路径
remote_dir = '/var/www/qingnang'
run(ssh, f'ls -la {remote_dir}/ 2>/dev/null | head -5')
run(ssh, f'mkdir -p {remote_dir}')

# Step 4: 上传 dist 文件
print('=== Step 3: 上传 dist 文件 ===')
sftp = ssh.open_sftp()

def upload_dir(local_path, remote_path):
    count = 0
    for item in os.listdir(local_path):
        local_file = os.path.join(local_path, item)
        remote_file = remote_path + '/' + item
        if os.path.isfile(local_file):
            sftp.put(local_file, remote_file)
            count += 1
        elif os.path.isdir(local_file):
            try: sftp.mkdir(remote_file)
            except: pass
            count += upload_dir(local_file, remote_file)
    return count

n = upload_dir(LOCAL_DIST, remote_dir)
sftp.close()
print(f'✅ 上传 {n} 个文件\n')

# Step 5: 重载 nginx
print('=== Step 4: 重载 Nginx ===')
run(ssh, 'sudo nginx -t 2>&1')
run(ssh, 'sudo systemctl reload nginx')

# Step 6: 验证
print('=== Step 5: 验证 ===')
run(ssh, f'curl -s http://127.0.0.1/ | head -5')

ssh.close()
print('✅ 前端部署完成！')
