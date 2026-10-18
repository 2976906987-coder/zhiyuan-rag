"""Isolated real-provider benchmark. No mutations to the interactive corpus."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import statistics
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.config import Settings
from app.engine import Engine


def score(hits, case):
    files = set(case['expected_files'])
    evidence = case['evidence']
    relevant = [any(h['filename']==e['file'] and e['anchor'] in h['text'] for e in evidence) for h in hits]
    return {
        'document_recall_at_5': len(files & {h['filename'] for h in hits}) / len(files),
        'evidence_hit_at_5': int(any(relevant)),
        'evidence_mrr_at_5': next((1/(i+1) for i,v in enumerate(relevant) if v),0),
        'top1_evidence_hit': int(bool(relevant and relevant[0]))}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--split', choices=['dev','test','all'], default='dev')
    parser.add_argument('--answers', type=int, default=0, help='Maximum LLM calls, balanced answerable/unanswerable')
    parser.add_argument('--output', default='eval/results/dev.json')
    args = parser.parse_args()
    settings = Settings()
    if settings.model_mode != 'api':
        raise ValueError('Real benchmark requires MODEL_MODE=api')
    settings.data_dir = 'data/benchmark-fastapi'
    settings.qdrant_url = ''
    # Same provider credentials, never output or serialize secrets.
    if not settings.rerank_base_url and settings.embedding_base_url == 'https://api.siliconflow.cn/v1':
        settings.rerank_base_url = settings.embedding_base_url
        settings.rerank_api_key = settings.embedding_api_key
        settings.rerank_model = 'BAAI/bge-reranker-v2-m3'
    cases = [json.loads(s) for s in Path('eval/benchmark.jsonl').read_text(encoding='utf-8').splitlines()]
    cases = [c for c in cases if args.split=='all' or c['split']==args.split]
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    manifest = json.loads(Path('eval/corpus/manifest.json').read_text(encoding='utf-8'))
    report = {'created_at':datetime.now(timezone.utc).isoformat(), 'split':args.split, 'status':'running',
              'corpus_commit':manifest['commit'], 'embedding':settings.embedding_model,
              'reranker':settings.rerank_model,'llm':settings.llm_model,
              'dataset_sha256':hashlib.sha256(Path('eval/benchmark.jsonl').read_bytes()).hexdigest(),
              'scope':'Draft agent-authored labels; anchor matching is a retrieval proxy, not semantic correctness. No human-reviewed answer accuracy. Latency includes live embedding calls; no cache.',
              'retrieval':[], 'answers':[]}
    def save():
        output.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    engine = Engine(settings)
    try:
        for source in manifest['sources']:
            path = Path('eval/corpus/fastapi') / source['file']
            if hashlib.sha256(path.read_bytes()).hexdigest()!=source['sha256']:
                raise ValueError('Corpus checksum mismatch')
            result = engine.ingest(path.name, manifest['commit'][:12], path.read_bytes())
            print('indexed', path.name, result.get('chunks','duplicate'), flush=True)
        report['corpus_documents'] = len(engine.documents())
        report['corpus_chunks'] = sum(d['chunks'] for d in engine.documents())
        # Integration probe runs before the paid full experiment.
        probe = engine.provider.rerank('FastAPI 上传大文件用什么？', [{'text':'UploadFile 支持磁盘缓冲。'}, {'text':'天气晴朗。'}])
        report['rerank_probe_ok'] = bool(probe)
        save()
        modes = ['vector','bm25','hybrid','rerank']
        for i, case in enumerate(c for c in cases if c['kind']=='answerable'):
            # Rotate order to reduce systematic network warm-up/order bias.
            for mode in modes[i%4:]+modes[:i%4]:
                start = time.perf_counter()
                record = {'case_id':case['id'],'question':case['question'],'mode':mode}
                try:
                    hits = engine.search(case['question'],mode=mode)
                    record.update(score(hits,case))
                    record['hits'] = [{'filename':h['filename'],'chunk_id':h['id'],'text':h['text'],'score':h['score'],'rerank_score':h.get('rerank_score')} for h in hits]
                except Exception as exc:
                    record['error_type'] = type(exc).__name__
                record['latency_ms'] = round((time.perf_counter()-start)*1000,2)
                report['retrieval'].append(record)
                save()
            print('retrieved',case['id'],flush=True)
        answerable = [c for c in cases if c['kind']=='answerable']
        negative = [c for c in cases if c['kind']=='unanswerable']
        # Spread answer checks across source topics before selecting a second
        # question from the same group.
        groups = list(dict.fromkeys(c['group'] for c in answerable))
        spread = [c for offset in range(4) for group in groups
                  for c in [([x for x in answerable if x['group']==group]+[None]*4)[offset]] if c]
        chosen = spread[:math.ceil(args.answers/2)] + negative[:args.answers//2]
        for case in chosen:
            record = {'case_id':case['id'],'kind':case['kind'],'question':case['question'],'reference_answer':case['reference_answer'],'human_review':'pending'}
            try:
                record['result'] = engine.chat(case['question'],mode='rerank')
            except Exception as exc:
                record['error_type'] = type(exc).__name__
            report['answers'].append(record)
            save()
            print('answered',case['id'],flush=True)
        summary = {}
        for mode in modes:
            rows = [r for r in report['retrieval'] if r['mode']==mode]
            good = [r for r in rows if 'error_type' not in r]
            summary[mode] = {'attempts':len(rows),'errors':len(rows)-len(good)}
            if good:
                summary[mode].update({key:statistics.mean(r[key] for r in good) for key in ['document_recall_at_5','evidence_hit_at_5','evidence_mrr_at_5','top1_evidence_hit']})
                timings = sorted(r['latency_ms'] for r in good)
                summary[mode]['p50_ms'] = statistics.median(timings)
                summary[mode]['p95_ms'] = timings[math.ceil(len(timings)*.95)-1]
        report['summary'] = summary
        report['status'] = 'complete'
        save()
        print(json.dumps(summary,ensure_ascii=False),flush=True)
    except Exception as exc:
        report['status']='failed'
        report['error_type']=type(exc).__name__
        save()
        raise
    finally:
        engine.close()


if __name__ == '__main__':
    main()
