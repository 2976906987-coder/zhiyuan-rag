"""Isolated Compose smoke test. Keeps volumes; never calls paid APIs."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import uuid
import httpx

root = Path(__file__).resolve().parents[1]
os.chdir(root)
report = {'status':'running','checks':[]}
output = root / 'data/docker-verification.json'
output.parent.mkdir(exist_ok=True)
project = 'ragverify'+uuid.uuid4().hex[:8]
env = dict(os.environ, APP_PORT='18002')
command = ['docker','compose','-p',project,'-f','compose.yaml','-f','compose.verify.yaml']


def run(*args):
    subprocess.run(command+list(args), env=env, check=True)


def ready(client):
    for _ in range(60):
        try:
            if client.get('/api/ready').status_code == 200:
                return
        except httpx.HTTPError:
            pass
        time.sleep(2)
    raise RuntimeError('Container readiness timeout')


started = False
try:
    if not shutil.which('docker'):
        report['status']='blocked'
        report['reason']='Docker CLI is not installed or not on PATH'
        raise SystemExit(2)
    subprocess.run(['docker','info','--format','{{.ServerVersion}}'],check=True)
    run('config','--quiet')  # Do not print expanded .env secrets.
    report['checks'].append('compose_config')
    started=True
    run('up','--build','-d')
    report['checks'].append('build_and_start')
    with httpx.Client(base_url='http://127.0.0.1:18002',timeout=15,trust_env=False) as client:
        ready(client)
        health=client.get('/api/health').json()
        assert health['model_mode']=='demo' and health['storage_mode']=='server'
        response=client.post('/api/documents',files={'file':('docker-check.md',b'Docker verification port is 8080.')},data={'version':'smoke'})
        response.raise_for_status()
        doc=response.json()['id']
        answer=client.post('/api/chat',json={'question':'verification port'}).json()
        assert answer['sources'] and not answer['refused']
        report['checks'].append('upload_retrieve_answer')
        run('restart')
        ready(client)
        assert any(d['id']==doc for d in client.get('/api/documents').json())
        hits=client.post('/api/search',json={'question':'verification port'}).json()
        assert any(h['document_id']==doc for h in hits)
        report['checks'].append('restart_persistence')
        client.delete('/api/documents/'+doc).raise_for_status()
        assert client.post('/api/search',json={'question':'verification port'}).json()==[]
        report['checks'].append('delete_cleanup')
    report['status']='passed'
except Exception as exc:
    report['status']='failed'
    report['reason']=type(exc).__name__
    raise
finally:
    report['compose_project']=project
    if started:
        subprocess.run(command+['down'],env=env,check=False)
    output.write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report))
