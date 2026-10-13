"""部署脚本：拉代码 + 重启后端 + 同步前端"""
import paramiko
import sys

HOST = '110.40.143.164'
USER = 'ubuntu'
PASS = 'Hu@697758521'

def run(cmd, timeout=30):
    print(f'>>> {cmd}')
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode()
    err = stderr.read().decode()
    if out:
        print(out.rstrip())
    if err and 'Warning' not in err and 'warning' not in err:
        print(f'STDERR: {err.rstrip()}', file=sys.stderr)
    return out

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, username=USER, password=PASS, timeout=10)

try:
    # 1. 拉代码
    run('cd /home/ubuntu/qingnang-APP && git pull origin master')
    
    # 2. 重启后端（用 sudo + 密码）
    run(f'echo "{PASS}" | sudo -S systemctl restart qingnang-backend')
    run(f'echo "{PASS}" | sudo -S systemctl is-active qingnang-backend')
    
    # 3. 清缓存
    run('rm -rf ~/.qingmeng/cache/*_2026101[23]_* 2>/dev/null; echo cache-cleaned')
    
    # 4. 同步前端
    run(f'echo "{PASS}" | sudo -S rsync -a --delete /home/ubuntu/qingnang-APP/frontend/dist/ /var/www/qingnang/')
    run(f'echo "{PASS}" | sudo -S nginx -t')
    run(f'echo "{PASS}" | sudo -S systemctl reload nginx')
    
    # 5. 测试 API
    import urllib.request
    try:
        r = urllib.request.urlopen('http://127.0.0.1:8767/api/v1/spacetime/context', timeout=5)
        print(f'✅ spacetime/context: {r.status}')
        print(r.read().decode()[:300])
    except Exception as e:
        print(f'❌ spacetime/context failed: {e}')
    
    try:
        r = urllib.request.urlopen('http://127.0.0.1:8767/api/v1/version/manifest', timeout=5)
        print(f'✅ version/manifest: {r.status}')
    except Exception as e:
        print(f'❌ version/manifest failed: {e}')
    
    print('\n=== 部署完成 ===')
    
finally:
    client.close()
