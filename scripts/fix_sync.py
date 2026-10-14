"""青囊部署脚本 — 前端 dist + backend 上传到服务器

自动读取项目根目录 .env 文件的敏感变量（SERVER_HOST/USER/PASS 等）。
任何改动先改 .env，不要改这个文件。

完整部署流程见 .env 头部注释。
"""
import os, sys, io, tarfile
import paramiko

def load_env(path=None):
    """从 .env 文件加载环境变量（支持注释行和引号值）"""
    if path is None:
        path = os.path.join(os.path.dirname(__file__), '..', '.env')
    if not os.path.exists(path):
        return {}
    env = {}
    with open(path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue
            key, val = line.split('=', 1)
            val = val.strip().strip('"').strip("'")
            env[key.strip()] = val
    return env

ENV = load_env()
ENV.update(os.environ)   # 系统环境变量优先

HOST = ENV.get('SERVER_HOST', '')
USER = ENV.get('SERVER_USER', '')
PASS = ENV.get('SERVER_PASS', '')
LOCAL_DIST = ENV.get('LOCAL_DIST', r'e:\工作\qingnang-APP\frontend\dist')
REMOTE_DIR = ENV.get('SERVER_DEPLOY_DIR', '/var/www/qingnang')

if not all([HOST, USER, PASS]):
    print('❌ SERVER_HOST / SERVER_USER / SERVER_PASS 未配置（.env 缺失或不全）')
    sys.exit(1)

print(f'▶ 部署 {LOCAL_DIST} → {USER}@{HOST}:{REMOTE_DIR}')

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST, username=USER, password=PASS, timeout=10)

# 1) 打包前端 dist
tar_buf = io.BytesIO()
with tarfile.open(fileobj=tar_buf, mode='w:gz') as tar:
    tar.add(LOCAL_DIST, arcname='dist')
tar_bytes = tar_buf.getvalue()

sftp = ssh.open_sftp()
sftp.putfo(io.BytesIO(tar_bytes), '/tmp/qn_dist.tar.gz')
sftp.close()
print('✅ 上传 tar 完成')

# 2) 部署命令
cmds = [
    f'echo "{PASS}" | sudo -S rm -rf {REMOTE_DIR}/*',
    'cd /tmp && tar xzf qn_dist.tar.gz && ls dist/',
    f'echo "{PASS}" | sudo -S cp -r /tmp/dist/* {REMOTE_DIR}/',
    f'echo "{PASS}" | sudo -S chown -R www-data:www-data {REMOTE_DIR}',
    f'echo "{PASS}" | sudo -S systemctl reload nginx',
    'rm -rf /tmp/dist /tmp/qn_dist.tar.gz',
]
for c in cmds:
    stdin, stdout, stderr = ssh.exec_command(c, timeout=30)
    out = stdout.read().decode().strip()
    err = stderr.read().decode().strip()
    print(f'>>> {c[:70]}')
    if out:
        print(f'    {out[:300]}')
    if err and 'Warning' not in err:
        print(f'    ERR: {err[:200]}')

ssh.close()
print('🎉 DONE')
