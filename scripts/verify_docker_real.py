"""Real-model Compose smoke test. WARNING: calls PAID cloud APIs.

Unlike verify_docker.py (offline demo, no keys), this uses the real
credentials in `.env` and exercises container-internal Embedding, Rerank
and LLM calls. It uses an isolated Compose project, port 18004 and
throwaway volumes, and removes its volumes at the end.

Cost is a handful of embeddings plus ~3 LLM completions (a few hundred
tokens). Prerequisites: Docker Desktop running; `.env` with MODEL_MODE=api
and valid LLM_/EMBEDDING_/RERANK_ keys (rerank assertions are skipped
automatically when RERANK is not configured).

    .\.venv\\Scripts\\python.exe scripts\\verify_docker_real.py
"""
import json
import os
import shutil
import subprocess
import time
import uuid
from pathlib import Path

import httpx

root = Path(__file__).resolve().parents[1]
os.chdir(root)
project = 'ragreal' + uuid.uuid4().hex[:8]
env = dict(os.environ, APP_PORT='18004')
base_url = 'http://127.0.0.1:18004'
command = ['docker', 'compose', '-p', project, '-f', 'compose.yaml']
report = {'status': 'running', 'mode': 'real-api', 'checks': []}
output = root / 'data' / 'docker-real-verification.json'
output.parent.mkdir(exist_ok=True)
started = False


def run(*args):
    subprocess.run(command + list(args), env=env, check=True)


def wait_ready(client):
    for _ in range(60):
        try:
            if client.get('/api/ready').status_code == 200:
                return
        except httpx.HTTPError:
            pass
        time.sleep(2)
    raise RuntimeError('container readiness timeout')


try:
    if not shutil.which('docker'):
        report['status'] = 'blocked'
        report['reason'] = 'Docker CLI is not installed or not on PATH'
        raise SystemExit(2)
    if not (root / '.env').exists():
        report['status'] = 'blocked'
        report['reason'] = '.env not found; copy .env.example and fill real keys'
        raise SystemExit(2)
    subprocess.run(['docker', 'info', '--format', '{{.ServerVersion}}'], check=True)
    run('config', '--quiet')  # Do not print expanded .env secrets.
    report['checks'].append('compose_config')

    started = True
    run('up', '--build', '-d')
    report['checks'].append('build_and_start')

    with httpx.Client(base_url=base_url, timeout=90, trust_env=False) as c:
        wait_ready(c)
        health = c.get('/api/health').json()
        report['health'] = health
        assert health['model_mode'] == 'api', 'container is not in api mode'
        assert health['storage_mode'] == 'server'
        report['checks'].append('health_api_mode')

        content = '知源真实联调说明：演示服务固定运行在 8080 端口，管理后台路径为 /admin。'
        r = c.post('/api/documents',
                   files={'file': ('real-check.md', content.encode('utf-8'), 'text/markdown')},
                   data={'version': 'v1'})
        r.raise_for_status()
        doc_id = r.json()['id']
        for _ in range(30):
            docs = [x for x in c.get('/api/documents').json() if x['id'] == doc_id]
            if docs and docs[0]['status'] == 'ready':
                break
            if docs and docs[0]['status'] == 'failed':
                raise RuntimeError('ingest failed')
            time.sleep(2)
        else:
            raise RuntimeError('ingest did not become ready')
        report['checks'].append('real_embedding_ingest')

        answer = c.post('/api/chat', json={'question': '演示服务运行在哪个端口？'}).json()
        assert not answer.get('refused') and '8080' in answer.get('answer', ''), answer
        report['checks'].append('real_llm_answer')

        if health.get('rerank_available'):
            ranked = c.post('/api/chat', json={'question': '管理后台路径是什么？', 'mode': 'rerank'}).json()
            assert not ranked.get('refused') and '/admin' in ranked.get('answer', ''), ranked
            report['checks'].append('real_rerank_answer')

        refused = c.post('/api/chat', json={'question': '公司内部数据库的管理员密码是多少？'}).json()
        assert refused.get('refused'), 'out-of-scope question should be refused'
        report['checks'].append('refuse_out_of_scope')

    report['status'] = 'passed'
except Exception as exc:
    report['status'] = 'failed'
    report['reason'] = type(exc).__name__
    raise
finally:
    report['compose_project'] = project
    if started:
        # Throwaway verification project: remove its volumes too.
        subprocess.run(command + ['down', '-v'], env=env, check=False)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False))
