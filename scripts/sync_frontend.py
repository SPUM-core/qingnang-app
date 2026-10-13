"""重新同步前端到服务器"""
import paramiko

HOST = '110.40.143.164'
USER = 'ubuntu'
PASS = 'Hu@697758521'

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, username=USER, password=PASS, timeout=10)

sftp = client.open_sftp()
import os

local_dist = r'e:\工作\qingnang-APP\frontend\dist'
remote_www = '/var/www/qingnang'

# 先清空远程 www 目录
stdin, stdout, stderr = client.exec_command(f'echo "{PASS}" | sudo -S rm -rf {remote_www}/* && echo cleaned')
print(stdout.read().decode())

# 用 sftp 逐个文件上传
count = 0
for root, dirs, files in os.walk(local_dist):
    rel_root = os.path.relpath(root, local_dist).replace('\\', '/')
    remote_dir = f'{remote_www}/{rel_root}' if rel_root != '.' else remote_www
    stdin, stdout, stderr = client.exec_command(f'echo "{PASS}" | sudo -S mkdir -p "{remote_dir}"')
    for f in files:
        local_path = os.path.join(root, f)
        remote_path = f'{remote_dir}/{f}'
        # 先用 sftp 传到用户目录，再 sudo mv
        user_path = f'/tmp/qingnang_upload/{rel_root}/{f}' if rel_root != '.' else f'/tmp/qingnang_upload/{f}'
        stdin, stdout, stderr = client.exec_command(f'mkdir -p "$(dirname "{user_path}")"')
        try:
            sftp.put(local_path, user_path)
            stdin, stdout, stderr = client.exec_command(f'echo "{PASS}" | sudo -S mv "{user_path}" "{remote_path}"')
            count += 1
            if count % 20 == 0:
                print(f'  uploaded {count} files...')
        except Exception as e:
            print(f'  FAIL {local_path}: {e}')

print(f'Total: {count} files uploaded')

# 修复权限
stdin, stdout, stderr = client.exec_command(f'echo "{PASS}" | sudo -S chown -R www-data:www-data {remote_www}')
stdout.read()

# 重载 nginx
stdin, stdout, stderr = client.exec_command(f'echo "{PASS}" | sudo -S nginx -t && echo "{PASS}" | sudo -S systemctl reload nginx')
print(stdout.read().decode())

sftp.close()
client.close()
print('DONE')
