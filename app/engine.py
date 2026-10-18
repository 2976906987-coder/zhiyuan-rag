import hashlib
import io
import json
import math
import re
import sqlite3
import threading
import time
import uuid
from collections import Counter
from pathlib import Path

from pypdf import PdfReader
from qdrant_client import QdrantClient, models
from app.models import Provider, tokens


class Engine:
    """Single-process MVP. SQLite gates visibility across the two stores."""
    def __init__(self, settings):
        self.s = settings
        self.provider = Provider(settings)
        self.lock = threading.RLock()
        root = Path(settings.data_dir)
        root.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(root / 'metadata.db', check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.db.executescript('''
            CREATE TABLE IF NOT EXISTS documents (
              id TEXT PRIMARY KEY, filename TEXT, version TEXT, digest TEXT,
              status TEXT, error TEXT DEFAULT '', created_at REAL,
              UNIQUE(filename, version));
            CREATE TABLE IF NOT EXISTS chunks (
              id TEXT PRIMARY KEY, document_id TEXT, text TEXT, page INTEGER);
            CREATE TABLE IF NOT EXISTS traces (
              id TEXT PRIMARY KEY, created_at REAL, payload TEXT);
        ''')
        self.q = QdrantClient(url=settings.qdrant_url) if settings.qdrant_url else QdrantClient(path=str(root / 'vectors'))
        identity = f'{settings.model_mode}:{settings.embedding_base_url}:{settings.embedding_model}:{settings.embedding_dim}'
        self.collection = 'chunks_' + hashlib.sha256(identity.encode()).hexdigest()[:12]
        # Never silently switch embedding spaces with an existing corpus.
        config = root / 'embedding.json'
        if config.exists() and json.loads(config.read_text()) != identity:
            raise ValueError('Embedding 配置已变更，请使用新的 DATA_DIR 并重新导入文档。')
        config.write_text(json.dumps(identity))
        if not self.q.collection_exists(self.collection):
            self.q.create_collection(self.collection, vectors_config=models.VectorParams(size=settings.embedding_dim, distance=models.Distance.COSINE))
        self.db.execute("UPDATE documents SET status='failed', error='服务重启中断导入，请删除后重试' WHERE status='indexing'")
        self.db.commit()

    def close(self):
        self.q.close()
        self.db.close()

    def documents(self):
        with self.lock:
            return [dict(r) for r in self.db.execute('SELECT d.*, (SELECT COUNT(*) FROM chunks c WHERE c.document_id=d.id) AS chunks FROM documents d ORDER BY created_at DESC')]

    def ingest(self, filename, version, content):
        filename = Path(filename.replace('\\', '/')).name
        suffix = Path(filename).suffix.lower()
        if suffix not in {'.pdf', '.txt', '.md'}:
            raise ValueError('仅支持 PDF、TXT、Markdown 文件。')
        if suffix == '.pdf':
            pages = [(i+1, p.extract_text() or '') for i, p in enumerate(PdfReader(io.BytesIO(content)).pages)]
        else:
            pages = [(1, content.decode('utf-8-sig'))]
        segments = []
        for page, text in pages:
            text = text.replace('\x00', '').strip()
            for start in range(0, len(text), 650):
                part = text[start:start+800].strip()
                if part:
                    segments.append((page, part))
        if not segments:
            raise ValueError('未提取到文字。扫描件需先做 OCR。')
        if len(segments) > 3000:
            raise ValueError('单文档最多 3000 个分块，请拆分文件。')
        digest = hashlib.sha256(content).hexdigest()
        with self.lock:
            existing = self.db.execute('SELECT * FROM documents WHERE filename=? AND version=?', (filename, version)).fetchone()
            if existing:
                if existing['digest'] == digest and existing['status'] == 'ready':
                    return dict(existing, duplicate=True)
                raise ValueError('同名同版本文档已存在，请使用新版本，或删除原文档后重新导入。')
            doc_id = str(uuid.uuid4())
            self.db.execute('INSERT INTO documents(id,filename,version,digest,status,created_at) VALUES(?,?,?,?,?,?)', (doc_id, filename, version, digest, 'indexing', time.time()))
            self.db.commit()
        try:
            vectors = self.provider.embed([text for _, text in segments])
            points = [models.PointStruct(id=str(uuid.uuid4()), vector=vector, payload={'document_id': doc_id}) for vector in vectors]
            with self.lock:
                for start in range(0, len(points), 64):
                    self.q.upsert(self.collection, points[start:start+64], wait=True)
                self.db.executemany('INSERT INTO chunks VALUES(?,?,?,?)', [(p.id, doc_id, text, page) for p, (page, text) in zip(points, segments)])
                self.db.execute("UPDATE documents SET status='ready' WHERE id=?", (doc_id,))
                self.db.commit()
            return {'id': doc_id, 'filename': filename, 'version': version, 'status': 'ready', 'chunks': len(points), 'duplicate': False}
        except Exception:
            with self.lock:
                self.db.rollback()
                self.db.execute("UPDATE documents SET status='failed',error='导入失败，请检查模型配置或服务连接，删除后重试' WHERE id=?", (doc_id,))
                self.db.commit()
            # Invisible failed records can be cleaned through the delete API.
            raise

    def delete(self, doc_id):
        with self.lock:
            row = self.db.execute('SELECT status FROM documents WHERE id=?', (doc_id,)).fetchone()
            if not row:
                raise KeyError(doc_id)
            if row['status'] == 'indexing':
                raise ValueError('文档正在索引，请完成后再删除。')
            self.db.execute("UPDATE documents SET status='deleting' WHERE id=?", (doc_id,))
            self.db.commit()
            self.q.delete(self.collection, models.FilterSelector(filter=models.Filter(must=[models.FieldCondition(key='document_id', match=models.MatchValue(value=doc_id))])), wait=True)
            self.db.execute('DELETE FROM chunks WHERE document_id=?', (doc_id,))
            self.db.execute('DELETE FROM documents WHERE id=?', (doc_id,))
            self.db.commit()

    def search(self, question, mode='hybrid', version='', top_k=5):
        vector = self.provider.embed([question])[0] if mode != 'bm25' else None
        with self.lock:
            rows = [dict(r) for r in self.db.execute("SELECT c.*,d.filename,d.version FROM chunks c JOIN documents d ON c.document_id=d.id WHERE d.status='ready' AND (?='' OR d.version=?)", (version, version))]
            if not rows:
                return []
            by_id = {r['id']: r for r in rows}
            dense = []
            if vector is not None:
                allowed = list({r['document_id'] for r in rows})
                result = self.q.query_points(self.collection, query=vector, query_filter=models.Filter(must=[models.FieldCondition(key='document_id', match=models.MatchAny(any=allowed))]), limit=20).points
                dense = [(str(r.id), r.score) for r in result if str(r.id) in by_id]
            counts = [Counter(tokens(r['text'])) for r in rows]
            avg = sum(sum(c.values()) for c in counts) / len(counts) or 1
            query = set(tokens(question))
            df = {t: sum(t in c for c in counts) for t in query}
            sparse = []
            for row, count in zip(rows, counts):
                length = sum(count.values())
                score = sum(math.log(1+(len(rows)-df[t]+0.5)/(df[t]+0.5)) * (count[t]*2.5)/(count[t]+1.5*(0.25+0.75*length/avg)) for t in query if count[t])
                if score > 0:
                    sparse.append((row['id'], score))
            sparse.sort(key=lambda x: x[1], reverse=True)
            scores = Counter()
            lists = [dense] if mode == 'vector' else [sparse[:20]] if mode == 'bm25' else [dense, sparse[:20]]
            for ranking in lists:
                for rank, (key, _) in enumerate(ranking, 1):
                    scores[key] += 1 / (60+rank)
            hits = [dict(by_id[key], score=score, vector_score=dict(dense).get(key), bm25_score=dict(sparse).get(key, 0)) for key, score in scores.most_common(20)]
        if mode == 'rerank' and hits:
            hits = self.provider.rerank(question, hits)
        return hits[:top_k]

    def chat(self, question, mode='hybrid', version='', top_k=5, on_token=None):
        started = time.perf_counter()
        hits = self.search(question, mode, version, top_k)
        # Conservative MVP gate, not a calibrated confidence probability.
        supported = any(h['bm25_score'] > 0 or (h['vector_score'] or 0) >= 0.45 for h in hits)
        usage = {}
        if not supported:
            answer = '现有资料不足以回答，请补充相关文档或调整问题。'
        else:
            answer, usage = self.provider.answer(question, hits, on_token=on_token) if on_token else self.provider.answer(question, hits)
        cited = {int(n) for n in re.findall(r'\[(\d+)\]', answer)}
        valid = all(1 <= n <= len(hits) for n in cited)
        refused = not supported or '现有资料不足以回答' in answer
        if not valid or (not refused and not cited):
            answer = '现有资料不足以回答：模型未提供有效引用，请尝试更具体的问题。'
            refused = True
            cited = set()
        # Recheck lifecycle after potentially slow model call.
        with self.lock:
            active = {r['id'] for r in self.db.execute("SELECT id FROM documents WHERE status='ready'")}
            if any(h['document_id'] not in active for h in hits):
                answer, hits, refused, cited = '资料在问答期间发生变更，请重新提问。', [], True, set()
            result = {'trace_id': str(uuid.uuid4()), 'answer': answer, 'refused': refused, 'sources': [dict(h, citation=i, cited=i in cited) for i, h in enumerate(hits, 1)], 'mode': mode, 'model_mode': self.s.model_mode, 'latency_ms': round((time.perf_counter()-started)*1000), 'usage': usage, 'citation_ids_valid': valid}
            self.db.execute('INSERT INTO traces VALUES(?,?,?)', (result['trace_id'], time.time(), json.dumps(dict(result, question=question), ensure_ascii=False)))
            self.db.commit()
        return result
