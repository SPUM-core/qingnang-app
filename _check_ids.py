import requests, json
base = 'http://110.40.143.164:8767'
tok = requests.post(base + '/api/v1/auth/login', json={'username':'admin','password':'admin123'}).json()['access_token']
d = requests.get(base + '/api/v1/cases/today-todos', headers={'Authorization':'Bearer '+tok}).json()
print('=== SERVER TODOS ===')
for i, t in enumerate(d.get('todos', [])):
    print(f"  [{i}] id={t.get('id')!r:20} type={t.get('source_type','?'):10} title={t.get('title','')[:15]}")
