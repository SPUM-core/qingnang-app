"""修复前端同步"""
import paramiko, io, tarfile

HOST, USER, PASS = '110.40.143.164', 'ubuntu', 'Hu@697758521'
LOCAL_DIST = r'e:\工作\qingnang-APP\frontend\dist'

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST, username=USER, password=PASS, timeout=10)

tar_buf = io.BytesIO()
with tarfile.open(fileobj=tar_buf, mode='w:gz') as tar:
    tar.add(LOCAL_DIST, arcname='dist')
tar_bytes = tar_buf.getvalue()

sftp = ssh.open_sftp()
sftp.putfo(io.BytesIO(tar_bytes), '/tmp/qn_dist.tar.gz')
sftp.close()
print('Uploaded tar')

cmds = [
    f'echo "{PASS}" | sudo -S rm -rf /var/www/qingnang/*',
    'cd /tmp && tar xzf qn_dist.tar.gz && ls dist/',
    f'echo "{PASS}" | sudo -S cp -r /tmp/dist/* /var/www/qingnang/',
    f'echo "{PASS}" | sudo -S chown -R www-data:www-data /var/www/qingnang',
    f'echo "{PASS}" | sudo -S systemctl reload nginx',
    'rm -rf /tmp/dist /tmp/qn_dist.tar.gz',
]
for c in cmds:
    stdin, stdout, stderr = ssh.exec_command(c, timeout=30)
    print(f'>>> {c[:70]}')
    print(stdout.read().decode().strip()[:300])
    e = stderr.read().decode().strip()
    if e and 'Warning' not in e: print(f'  ERR: {e[:200]}')

ssh.close()
print('DONE')
