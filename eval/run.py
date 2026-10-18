"""Document-level retrieval smoke benchmark, not an answer-quality benchmark."""
import argparse
import json
import statistics
import time
from pathlib import Path
import httpx


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--url', default='http://127.0.0.1:8000')
    parser.add_argument('--dataset', default='eval/questions.jsonl')
    parser.add_argument('--output', default='eval/report.json')
    parser.add_argument('--rerank', action='store_true')
    args = parser.parse_args()
    cases = [json.loads(line) for line in Path(args.dataset).read_text(encoding='utf-8').splitlines() if line.strip()]
    if not cases:
        raise ValueError('评测集不能为空')
    reports = {}
    with httpx.Client(base_url=args.url, timeout=120) as client:
        health = client.get('/api/health').json()
        for mode in ['vector', 'bm25', 'hybrid'] + (['rerank'] if args.rerank else []):
            recalls, reciprocal, latency = [], [], []
            for case in cases:
                start = time.perf_counter()
                response = client.post('/api/search', json={'question': case['question'], 'mode': mode, 'top_k': 5})
                response.raise_for_status()
                latency.append((time.perf_counter()-start)*1000)
                names = [h['filename'] for h in response.json()]
                expected = set(case['expected_files'])
                recalls.append(len(expected.intersection(names))/len(expected))
                reciprocal.append(next((1/(i+1) for i, n in enumerate(names) if n in expected), 0))
            reports[mode] = {'document_recall_at_5': statistics.mean(recalls), 'mrr_at_5': statistics.mean(reciprocal), 'mean_latency_ms': round(statistics.mean(latency), 2)}
    output = {'model_mode': health['model_mode'], 'cases': len(cases), 'scope': '文档级检索冒烟评测；非答案准确率；demo 模式不代表真实语义模型效果', 'results': reports}
    Path(args.output).write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
