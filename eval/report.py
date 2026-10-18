"""Render saved measurements without new model calls."""
import json
import hashlib
from pathlib import Path


def main():
    dataset_hash = hashlib.sha256(Path('eval/benchmark.jsonl').read_bytes()).hexdigest()
    lines = ['# RAG 实测报告', '', '数据集：FastAPI 0.115.0 官方中文文档，16 篇。问题集共 80 题：64 道可回答题、16 道资料外问题。按整篇文档分为 dev/test，各 40 题。', '',
             '**证据锚点已于 2026-10-18 完成精修并逐题核对原文（v2，见 `eval/refine_anchors.py` 与 `audit_labels.py`）：64 个锚点均能在指定文档定位，跨文档锚点为 0；但仍为单轮 AI 辅助复核、非独立多人金标准，指标不能等同于真实用户问题的答案准确率。**', '',
             '证据命中要求检索片段来自指定文档且包含标注锚点；锚点是定位答案的连续原文片段，少数代码锚点在不同语言示例标签页中重复（属于答案本身）。文档召回不等于召回完整回答依据。语料是固定历史版本，不代表当前 FastAPI 行为。', '']
    for split in ['dev','test']:
        path = Path(f'eval/results/{split}.json')
        if not path.exists():
            continue
        report = json.loads(path.read_text(encoding='utf-8'))
        if report.get('dataset_sha256') != dataset_hash:
            lines += [f'## {split}：待新版标签重测', '',
                      f'`eval/results/{split}.json` 的数据集 SHA256 与当前标签不一致，以下不展示其旧指标，避免混用实验版本。历史结果保留在原文件及 v1-draft 归档中。', '']
            continue
        lines += [f'## {split}：{report["status"]}', '',f'语料：{report.get("corpus_documents",0)} 篇 / {report.get("corpus_chunks",0)} 个分块；Embedding：`{report["embedding"]}`；重排：`{report["reranker"]}`；生成：`{report["llm"]}`。', '',
                  '| 检索方案 | 尝试/失败 | 文档 Recall@5 | 证据 Hit@5 | 证据 MRR@5 | 首位证据命中 | P50/P95 ms |', '|---|---:|---:|---:|---:|---:|---:|']
        for mode,row in report.get('summary',{}).items():
            if 'document_recall_at_5' not in row:
                continue
            lines.append(f'| {mode} | {row["attempts"]}/{row["errors"]} | {row["document_recall_at_5"]:.1%} | {row["evidence_hit_at_5"]:.1%} | {row["evidence_mrr_at_5"]:.3f} | {row["top1_evidence_hit"]:.1%} | {row["p50_ms"]:.0f}/{row["p95_ms"]:.0f} |')
        lines += ['', '延迟包含真实 Embedding 和可选重排网络调用，无查询缓存；每题轮换方案顺序，仅测一轮。失败单独计数，表中质量指标按成功请求统计。未计算人民币成本，因为供应商定价与计费 Token 记录尚不完整。', '', '### 检索失败案例', '']
        misses = [r for r in report['retrieval'] if r.get('evidence_hit_at_5')==0]
        for r in misses[:12]:
            names = ', '.join(dict.fromkeys(h['filename'] for h in r['hits']))
            lines.append(f'- {r["case_id"]} / {r["mode"]}：{r["question"]} → {names}')
        if not misses:
            lines.append('本次没有锚点漏召回记录；仍需更难的问题和独立标注验证。')
        lines += ['', '### 回答与拒答抽查（待人工评审）', '']
        for answer in report['answers']:
            result = answer.get('result')
            lines += [f'**{answer["case_id"]} · {answer["kind"]}：{answer["question"]}**', '']
            if not result:
                lines += ['调用失败：'+answer.get('error_type','unknown'),'']
                continue
            lines += [result['answer'], '', f'系统拒答标记：{result["refused"]}；引用编号有效：{result["citation_ids_valid"]}；耗时：{result["latency_ms"]} ms。', '',
                      '参考要点：'+answer['reference_answer'], '']
    lines += ['## 标注审核', '', 'v2 复核（2026-10-18）：64 个证据锚点全部精修为在指定文档唯一或仅在答案处出现的连续原文片段，跨文档锚点清零（质检 `eval/audit_labels.py` 通过）；q004 原题（“为什么不建议生产环境使用 --reload”）的参考答案超出固定版本原文，已改为询问 `--reload` 的作用与建议使用环境，详见 [LABEL_REVIEW.md](LABEL_REVIEW.md)。当前不报告答案准确率，检索指标仅反映锚点匹配。', '', '## 可复现方式','', '```powershell', r'.\.venv\Scripts\python.exe eval/build_dataset.py', r'.\.venv\Scripts\python.exe eval/benchmark.py --split dev --answers 8 --output eval/results/dev.json', r'.\.venv\Scripts\python.exe eval/benchmark.py --split test --answers 8 --output eval/results/test.json', r'.\.venv\Scripts\python.exe eval/report.py', '```', '',
              '运行 benchmark 会调用配置的真实服务并可能产生费用。评测库位于 data/benchmark-fastapi，独立于交互知识库。原始逐题结果、来源片段和回答保存在 eval/results。测试集在本轮不用于调参；未来若根据这些结果修改检索，应另建新保留集。']
    build_step = lines.index(r'.\.venv\Scripts\python.exe eval/build_dataset.py')
    lines[build_step+1:build_step+1] = [r'.\.venv\Scripts\python.exe eval/refine_anchors.py', r'.\.venv\Scripts\python.exe eval/audit_labels.py']
    lines += ['', '当前数据集 SHA256：`'+dataset_hash+'`。复现时如运行 build_dataset.py，必须接着运行 refine_anchors.py 和 audit_labels.py，再运行 benchmark；否则会恢复早期标签。']
    Path('eval/REPORT.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')


if __name__ == '__main__':
    main()
