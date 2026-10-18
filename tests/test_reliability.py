import httpx
import pytest
from app.config import Settings
from app.upstream import Transport, ProviderError
from app.models import Provider


def transport(monkeypatch, handler):
    real_client = httpx.Client
    monkeypatch.setattr('app.upstream.httpx.Client', lambda **kw: real_client(transport=httpx.MockTransport(handler), **kw))
    monkeypatch.setattr('app.upstream.time.sleep', lambda _: None)
    return Transport(Settings(_env_file=None, model_retry_max_delay_seconds=1))


def test_rate_limit_then_recovery(monkeypatch):
    calls=[]
    def handle(request):
        calls.append(request)
        return httpx.Response(429,headers={'Retry-After':'0'}) if len(calls)==1 else httpx.Response(200,json={'ok':True})
    t=transport(monkeypatch,handle)
    assert t.post('https://example.test','secret','/embeddings',{})=={'ok':True}
    assert len(calls)==2


@pytest.mark.parametrize('code,status,count',[(401,502,1),(402,502,1),(404,502,1),(429,503,3),(503,502,3)])
def test_bounded_retries_and_safe_errors(monkeypatch,code,status,count):
    calls=[]
    def handle(request):
        calls.append(request)
        return httpx.Response(code,text='sensitive-key-and-private-text')
    t=transport(monkeypatch,handle)
    with pytest.raises(ProviderError) as exc:
        t.post('https://example.test','secret','/test',{})
    assert exc.value.status==status and 'sensitive' not in str(exc.value)
    assert len(calls)==count


def test_long_retry_after_not_retried_early(monkeypatch):
    calls=[]
    def handle(request):
        calls.append(request)
        return httpx.Response(429,headers={'Retry-After':'3600'})
    t=transport(monkeypatch,handle)
    with pytest.raises(ProviderError): t.post('https://example.test','secret','/test',{})
    assert len(calls)==1


def test_read_timeout_not_replayed(monkeypatch):
    calls=[]
    def handle(request):
        calls.append(request)
        raise httpx.ReadTimeout('private details')
    t=transport(monkeypatch,handle)
    with pytest.raises(ProviderError) as exc: t.post('https://example.test','secret','/test',{})
    assert exc.value.status==504 and len(calls)==1


def test_truncated_stream_is_failure(monkeypatch):
    calls=[]
    def handle(request):
        calls.append(request)
        return httpx.Response(200,text='data: {"choices":[{"delta":{"content":"partial"}}]}\n\n')
    t=transport(monkeypatch,handle)
    p=Provider(Settings(_env_file=None,llm_base_url='https://example.test',llm_api_key='test'))
    p.transport=t
    pieces=[]
    with pytest.raises(ProviderError): p.answer('q',[],on_token=pieces.append)
    assert pieces==['partial'] and len(calls)==1


def test_invalid_json(monkeypatch):
    t=transport(monkeypatch,lambda r:httpx.Response(200,text='not-json'))
    with pytest.raises(ProviderError): t.post('https://example.test','test','/test',{})


def test_malformed_embedding_not_document_404(monkeypatch):
    p=Provider(Settings(_env_file=None))
    monkeypatch.setattr(p,'post',lambda *args: {'error':'unexpected'})
    with pytest.raises(ProviderError) as exc: p.embed(['hello'])
    assert exc.value.status==502


def test_length_limited_stream_is_failure(monkeypatch):
    t=transport(monkeypatch,lambda r:httpx.Response(200,text='data: {"choices":[{"delta":{"content":"cut off"},"finish_reason":"length"}]}\n\ndata: [DONE]\n\n'))
    p=Provider(Settings(_env_file=None,llm_base_url='https://example.test',llm_api_key='test'))
    p.transport=t
    with pytest.raises(ProviderError): p.answer('q',[],on_token=lambda _:None)
