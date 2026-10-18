import pytest
from fastapi.testclient import TestClient
from app.config import Settings
from app.main import create_app


@pytest.fixture
def client(tmp_path):
    app = create_app(Settings(_env_file=None, model_mode='demo', embedding_dim=128, data_dir=str(tmp_path)))
    with TestClient(app) as c:
        yield c


def upload(c, text='服务默认端口为 8080。可以通过 PORT 环境变量修改端口。', version='v1'):
    return c.post('/api/documents', files={'file': ('guide.md', text.encode(), 'text/markdown')}, data={'version': version})


def test_lifecycle_and_citation(client):
    doc = upload(client).json()
    assert doc['status'] == 'ready'
    assert upload(client).json()['duplicate']
    result = client.post('/api/chat', json={'question': '默认端口是多少？'}).json()
    assert not result['refused']
    assert result['sources'][0]['document_id'] == doc['id']
    assert result['sources'][0]['cited']
    assert client.delete('/api/documents/'+doc['id']).status_code == 200
    assert client.post('/api/search', json={'question': '默认端口'}).json() == []
    assert client.post('/api/chat', json={'question': '默认端口'}).json()['refused']


def test_versions_and_conflict(client):
    upload(client)
    assert upload(client, '不同内容').status_code == 400
    upload(client, '服务默认端口为 9090。', 'v2')
    hits = client.post('/api/search', json={'question': '默认端口', 'version': 'v2'}).json()
    assert hits and all(h['version'] == 'v2' and '9090' in h['text'] for h in hits)


def test_invalid_inputs_and_unknown_question(client):
    assert client.post('/api/documents', files={'file': ('a.exe', b'hello')}).status_code == 400
    assert client.post('/api/documents', files={'file': ('a.md', b' ')}).status_code == 400
    assert client.post('/api/chat', json={'question': ''}).status_code == 422
    assert client.post('/api/chat', json={'question': 'x', 'top_k': 100}).status_code == 422
    upload(client)
    result = client.post('/api/chat', json={'question': 'quantum banana zebra'}).json()
    assert result['refused']


def test_bad_citations_fail_closed(client, monkeypatch):
    upload(client)
    monkeypatch.setattr(client.app.state.engine.provider, 'answer', lambda *args: ('错误引用 [99]', {}))
    result = client.post('/api/chat', json={'question': '默认端口'}).json()
    assert result['refused'] and not result['citation_ids_valid']
    monkeypatch.setattr(client.app.state.engine.provider, 'answer', lambda *args: ('没有引用的回答', {}))
    assert client.post('/api/chat', json={'question': '默认端口'}).json()['refused']


def test_failed_ingest_invisible_and_recoverable(client, monkeypatch):
    def fail(*args):
        raise RuntimeError('provider failed')
    monkeypatch.setattr(client.app.state.engine.provider, 'embed', fail)
    assert upload(client).status_code == 502
    docs = client.get('/api/documents').json()
    assert docs[0]['status'] == 'failed'
    assert client.post('/api/search', json={'question': '端口', 'mode': 'bm25'}).json() == []
    assert client.delete('/api/documents/'+docs[0]['id']).status_code == 200


def test_api_contract_and_rerank(client, monkeypatch):
    provider = client.app.state.engine.provider
    upload(client)
    provider.s.model_mode = 'api'
    provider.s.rerank_base_url = 'https://example.test/v1'
    def post(base, key, path, body):
        if path == '/embeddings':
            return {'data': [{'index': i, 'embedding': [1.0]+[0.0]*127} for i, _ in enumerate(body['input'])]}
        if path == '/rerank':
            return {'results': [{'index': 0, 'relevance_score': .9}]}
        return {'choices': [{'message': {'content': '默认端口为 8080。[1]'}}], 'usage': {'total_tokens': 25}}
    monkeypatch.setattr(provider, 'post', post)
    r = client.post('/api/chat', json={'question': '默认端口', 'mode': 'rerank'}).json()
    assert r['usage']['total_tokens'] == 25
    assert r['sources'][0]['rerank_score'] == .9


def test_restart_persists(tmp_path):
    settings = Settings(_env_file=None, model_mode='demo', embedding_dim=128, data_dir=str(tmp_path))
    with TestClient(create_app(settings)) as c:
        upload(c)
    with TestClient(create_app(settings)) as c:
        assert c.get('/api/documents').json()[0]['status'] == 'ready'
        assert c.post('/api/search', json={'question': '端口'}).json()


def test_page_and_stream(client):
    assert client.get('/').status_code == 200
    assert client.get('/static/app.js').status_code == 200
    r = client.post('/api/chat/stream', json={'question': '无资料'})
    assert r.status_code == 200 and 'event: result' in r.text


def test_stream_tokens_and_final_validation(client, monkeypatch):
    upload(client)
    def answer(question, hits, on_token=None):
        on_token('端口为 8080。')
        on_token('[99]')
        return '端口为 8080。[99]', {}
    monkeypatch.setattr(client.app.state.engine.provider, 'answer', answer)
    response = client.post('/api/chat/stream', json={'question': '默认端口'})
    assert 'event: token' in response.text
    assert 'event: result' in response.text
    assert '"refused": true' in response.text


def test_deletion_during_generation(client, monkeypatch):
    doc = upload(client).json()
    engine = client.app.state.engine
    def answer(*args):
        engine.delete(doc['id'])
        return '端口为 8080。[1]', {}
    monkeypatch.setattr(engine.provider, 'answer', answer)
    response = client.post('/api/chat', json={'question': '默认端口'}).json()
    assert response['refused'] and response['sources'] == []
