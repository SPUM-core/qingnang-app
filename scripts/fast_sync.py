"""快速同步前端 — 先全量 sftp 到 /tmp，再一次性 sudo cp"""
import paramiko, os, tarfile, io

HOST, USER, PASS = '110.40.143.164', 'ubuntu', 'Hu@697758521'
LOCAL_DIST = r'e:\工作\qingnang-APP\frontend\dist'

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST, username=USER, password=PASS, timeout=10)

# 打包本地 dist 为 tar
tar_buf = io.BytesIO()
with tarfile.open(fileobj=tar_buf, mode='w:gz') as tar:
    tar.add(LOCAL_DIST, arcname='dist')
tar_bytes = tar_buf.getvalue()
print(f'Local dist tar: {len(tar_bytes)/1024:.0f} KB')

# sftp 上传 tar
sftp = ssh.open_sftp()
remote_tar = '/tmp/qingnang_dist.tar.gz'
with sftp.file(remote_tar, 'wb') as f:
    f.write(tar_bytes)
sftp.close()
print('Uploaded tar')

# 远程解压 + 覆盖
stdin, stdout, stderr = ssh.exec_command(f"""
echo "{PASS}" | sudo -S rm -rf /var/www/qingnang/*
cd /tmp
tar xzf {remote_tar}
echo "{PASS}" | sudo -S cp -r dist/* /var/www/qingnang/
echo "{PASS}" | sudo -S chown -R www-data:www-data /var/www/qingnang
echo "{PASS}" | sudo -S systemctl reload nginx
rm -rf dist {remote_tar}
echo DONE
""", timeout=60)
print(stdout.read().decode())
err = stderr.read().decode()
if 'Warning' not in err: print(f'STDERR: {err[:300]}')

ssh.close()
print('FINISHED')
