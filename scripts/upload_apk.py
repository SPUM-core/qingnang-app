"""上传 APK 到服务器 + regenerate manifest"""
import paramiko
import sys

HOST = '110.40.143.164'
USER = 'ubuntu'
PASS = 'Hu@697758521'
LOCAL_APK = r'e:\工作\qingnang-APP\backend\updates\qingnang-v0.1.6.apk'
REMOTE_DIR = '/home/ubuntu/qingnang-APP/backend/updates/'

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, username=USER, password=PASS, timeout=10)
sftp = client.open_sftp()

try:
    # 1. 先看服务器当前 updates/ 状态
    stdin, stdout, stderr = client.exec_command(f'ls -la {REMOTE_DIR}')
    print('=== 服务器当前 updates/ ===')
    print(stdout.read().decode())

    # 2. 上传 APK
    remote_path = REMOTE_DIR + 'qingnang-v0.1.6.apk'
    local_size = sftp_stat_local = open(LOCAL_APK, 'rb').read().__len__()
    print(f'📤 上传 qingnang-v0.1.6.apk ({local_size / 1024 / 1024:.1f} MB)...')
    sftp.put(LOCAL_APK, remote_path)
    
    # 3. 确认上传
    file_attr = sftp.stat(remote_path)
    print(f'✅ 上传成功: {file_attr.st_size / 1024 / 1024:.1f} MB')

    # 4. 先备份旧 manifest.json 然后 regenerate
    cmd1 = f'echo "{PASS}" | sudo -S cp {REMOTE_DIR}manifest.json {REMOTE_DIR}manifest-v0.1.5.backup.json 2>/dev/null; echo done'
    client.exec_command(cmd1)[1].read()
    
    # 删除旧 manifest 让 regenerate 从头扫描（也可以直接调 regenerate，它会覆盖）
    # 5. regenerate manifest（调用后端 API）
    import urllib.request, json
    url = 'http://127.0.0.1:8767/api/v1/version/manifest/regenerate'
    req = urllib.request.Request(url, method='POST')
    try:
        r = urllib.request.urlopen(req, timeout=10)
        data = json.loads(r.read().decode())
        print(f'\n=== manifest regenerated ===')
        print(json.dumps(data, indent=2, ensure_ascii=False))
    except urllib.error.HTTPError as e:
        print(f'❌ regenerate failed: {e.code}')
        print(e.read().decode()[:500])
    except Exception as e:
        print(f'❌ regenerate error: {e}')

    # 6. 验证服务器目录
    stdin, stdout, stderr = client.exec_command(f'ls -la {REMOTE_DIR} && cat {REMOTE_DIR}manifest.json')
    print(f'\n=== 服务器最终状态 ===')
    print(stdout.read().decode())

finally:
    sftp.close()
    client.close()
