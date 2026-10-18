from eval.benchmark import score


def test_retrieval_metrics_require_evidence_in_correct_file():
    case = {'expected_files':['correct.md'], 'evidence':[{'file':'correct.md','anchor':'port=8080'}]}
    hits = [{'filename':'wrong.md','text':'port=8080'}, {'filename':'correct.md','text':'unrelated'}, {'filename':'correct.md','text':'Use port=8080'}]
    result = score(hits, case)
    assert result['document_recall_at_5'] == 1
    assert result['evidence_mrr_at_5'] == 1/3
    assert result['top1_evidence_hit'] == 0


def test_retrieval_miss_is_zero():
    case = {'expected_files':['correct.md'], 'evidence':[{'file':'correct.md','anchor':'port=8080'}]}
    result = score([], case)
    assert all(value == 0 for value in result.values())


def test_report_excludes_stale_dataset_results(tmp_path, monkeypatch):
    import json
    from eval.report import main
    monkeypatch.chdir(tmp_path)
    (tmp_path / 'eval/results').mkdir(parents=True)
    (tmp_path / 'eval/benchmark.jsonl').write_text('{}\n', encoding='utf-8')
    (tmp_path / 'eval/results/test.json').write_text(json.dumps({
        'dataset_sha256': 'old-dataset', 'status': 'complete',
        'llm': 'stale-model-do-not-display',
    }), encoding='utf-8')
    main()
    report = (tmp_path / 'eval/REPORT.md').read_text(encoding='utf-8')
    assert 'test：待新版标签重测' in report
    assert 'stale-model-do-not-display' not in report
