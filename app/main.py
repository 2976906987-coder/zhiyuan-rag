from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal
import json
import logging
import asyncio

from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

from app.config import Settings
from app.engine import Engine
from app.upstream import ProviderError


class Question(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    mode: Literal['vector', 'bm25', 'hybrid', 'rerank'] = 'hybrid'
    version: str = Field(default='', max_length=100)
    top_k: int = Field(default=5, ge=1, le=10)


def create_app(settings=None):
    settings = settings or Settings()

    @asynccontextmanager
    async def lifespan(app):
        app.state.engine = Engine(settings)
        try:
            yield
        finally:
            app.state.engine.close()

    app = FastAPI(title='知源 · 可追溯 RAG 知识库', version='0.1.0', lifespan=lifespan)
    static = Path(__file__).parent / 'static'
    app.mount('/static', StaticFiles(directory=static), name='static')

    def perform(function, *args, **kwargs):
        try:
            return function(*args, **kwargs)
        except ProviderError as exc:
            raise HTTPException(exc.status, str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
        except KeyError as exc:
            raise HTTPException(404, '文档不存在') from exc
        except Exception as exc:
            logging.getLogger(__name__).error('Operation failed: %s', type(exc).__name__)
            raise HTTPException(502, '模型或存储服务调用失败，请检查配置与连接。') from exc

    @app.get('/')
    def home():
        return FileResponse(static / 'index.html')

    @app.get('/api/health')
    def health():
        return {'status': 'ok', 'model_mode': settings.model_mode, 'rerank_available': bool(settings.rerank_base_url), 'vector_database': 'Qdrant', 'storage_mode': 'server' if settings.qdrant_url else 'embedded'}

    @app.get('/api/ready')
    def ready():
        def check():
            with app.state.engine.lock:
                app.state.engine.db.execute('SELECT 1').fetchone()
                app.state.engine.q.get_collection(app.state.engine.collection)
            return {'status': 'ready'}
        return perform(check)

    @app.get('/api/documents')
    def documents():
        return app.state.engine.documents()

    @app.post('/api/documents', status_code=201)
    async def upload(file: UploadFile = File(...), version: str = Form('v1', min_length=1, max_length=100)):
        try:
            content = await file.read(10*1024*1024+1)
            if len(content) > 10*1024*1024:
                raise HTTPException(413, '文件不能超过 10 MB。')
            return await run_in_threadpool(perform, app.state.engine.ingest, file.filename or 'document.txt', version.strip() or 'v1', content)
        finally:
            await file.close()

    @app.delete('/api/documents/{document_id}')
    def delete(document_id: str):
        perform(app.state.engine.delete, document_id)
        return {'deleted': True}

    @app.post('/api/search')
    def search(body: Question):
        return perform(app.state.engine.search, **body.model_dump())

    @app.post('/api/chat')
    def chat(body: Question):
        return perform(app.state.engine.chat, **body.model_dump())

    @app.post('/api/chat/stream')
    async def stream(body: Question):
        async def events():
            queue = asyncio.Queue()
            loop = asyncio.get_running_loop()
            def token(value):
                loop.call_soon_threadsafe(queue.put_nowait, ('token', {'text': value}))
            async def work():
                try:
                    result = await run_in_threadpool(perform, app.state.engine.chat, **body.model_dump(), on_token=token)
                    await queue.put(('result', result))
                except HTTPException as exc:
                    await queue.put(('error', {'detail': exc.detail}))
            task = asyncio.create_task(work())
            try:
                yield 'event: status\ndata: {"text":"正在检索；生成中的文字尚未完成引用校验"}\n\n'
                while True:
                    try:
                        kind, payload = await asyncio.wait_for(queue.get(), timeout=15)
                    except asyncio.TimeoutError:
                        yield ': keepalive\n\n'
                        continue
                    yield f'event: {kind}\ndata: ' + json.dumps(payload, ensure_ascii=False) + '\n\n'
                    if kind in {'result', 'error'}:
                        break
            finally:
                # Thread's provider request has a bounded timeout; cancellation
                # cannot forcibly abort a synchronous network call already running.
                task.cancel()
        return StreamingResponse(events(), media_type='text/event-stream')

    return app


app = create_app()
