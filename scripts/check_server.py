"""跑后端 health + 模拟 v3 数据返回检查"""
import paramiko

HOST = '110.40.143.164'
USER = 'ubuntu'
PASS = 'Hu@697758521'

def run(ssh, cmd, timeout=30):
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode().strip()
    err = stderr.read().decode().strip()
    rc = stdout.channel.recv_exit_status()
    if out: print(out[:2000])
    if err and rc != 0: print(f'⚠️ {err[:500]}')
    print(f'  → exit={rc}\n')
    return rc == 0, out, err

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST, username=USER, password=PASS, timeout=10)

print('=== 1. health ===')
run(ssh, 'curl -s http://127.0.0.1:8767/health')

print('=== 2. reasoning fallback 直接调用（检查 v3 数据结构）===')
run(ssh, '''cd /home/ubuntu/qingnang-APP/backend && .venv/bin/python -c "
import sys
sys.path.insert(0, '.')
from app.api.v1.assistant_modules.reasoning import _fallback_lifestyle
d = _fallback_lifestyle({'wood':30,'fire':60,'earth':45,'metal':35,'water':30}, {})
print('engine:', d['engine'])
print('timeline len:', len(d['timeline']))
print('timeline[0] keys:', list(d['timeline'][0].keys()))
print('timeline[0] personal:', d['timeline'][0].get('personal_type'), d['timeline'][0].get('personal_label'))
print('orientation:', d['orientation'])
print('swaps:', d['swaps'])
print('OK')
"''')

print('=== 3. 后端服务 status ===')
run(ssh, 'sudo systemctl is-active qingnang-backend && sudo journalctl -u qingnang-backend --since "1 min ago" --no-pager 2>&1 | tail -15')

ssh.close()
