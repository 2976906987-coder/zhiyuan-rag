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
