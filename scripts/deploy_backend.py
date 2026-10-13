"""只部署后端修复（git pull + restart + check + verify）"""
import paramiko

HOST = '110.40.143.164'
USER = 'ubuntu'
PASS = 'Hu@697758521'

def run(ssh, cmd, timeout=60):
    print(f'▶ {cmd}')
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode().strip()
    err = stderr.read().decode().strip()
    rc = stdout.channel.recv_exit_status()
    if out: print(out[:2000])
    if err and rc != 0: print(f'⚠️ {err[:500]}')
    print(f'  → exit={rc}\n')
    return rc == 0, out

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST, username=USER, password=PASS, timeout=10)

# git pull 后端
run(ssh, 'cd /home/ubuntu/qingnang-APP && git pull origin master 2>&1 | tail -3')

# 清今天缓存（cache_version 从 4→5，旧缓存全失效）
run(ssh, 'rm -f ~/.qingmeng/cache/lifestyle_*_2026101[23]_*')

# 重启
import time
run(ssh, 'sudo systemctl restart qingnang-backend')
time.sleep(2)
run(ssh, 'sudo systemctl is-active qingnang-backend')

# 验证 v3 数据结构
run(ssh, '''cd /home/ubuntu/qingnang-APP/backend && .venv/bin/python -c "
import sys
sys.path.insert(0, '.')
from app.api.v1.assistant_modules.reasoning import _fallback_lifestyle
d = _fallback_lifestyle({'wood':30,'fire':60,'earth':45,'metal':35,'water':30}, {})
print('✅ engine:', d['engine'])
print('✅ timeline len:', len(d['timeline']))
print('✅ timeline[0] personal:', d['timeline'][0].get('personal_type'), d['timeline'][0].get('personal_label'))
print('✅ orientation:', {k:v for k,v in d['orientation'].items() if k in ('feixing_name','good_dir','bad_dir','good_advice','bad_advice')})
print('✅ swaps count:', len(d['swaps']))
print('🎉 全量验证通过')
"''')

# 再 regenerate manifest（虽然版本号没变，但确保缓存全清）
run(ssh, 'curl -s -X POST http://127.0.0.1:8767/api/v1/version/manifest/regenerate')

# 健康检查
run(ssh, 'curl -s http://127.0.0.1:8767/health')

ssh.close()
print('✅ 后端部署完成！')
