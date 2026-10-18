"""Read-only label quality audit for eval/benchmark.jsonl.

Hard failure (exit 1): an evidence anchor does not occur in any expected file,
or an expected file / benchmark line is malformed.

Reported but not fatal:
- cross-file anchors (the same string also appears in other corpus files);
- anchors that repeat within the expected file (code shown in multiple tabs is
  expected and is acceptable when it is the answer itself).

Run:  .\\.venv\\Scripts\\python.exe eval\\audit_labels.py
"""
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'eval' / 'benchmark.jsonl'
CORPUS = ROOT / 'eval' / 'corpus' / 'fastapi'


def main():
    docs = {p.name: p.read_text(encoding='utf-8') for p in sorted(CORPUS.glob('*.md'))}
    cases = [json.loads(line) for line in DATA.read_text(encoding='utf-8').splitlines()]
    answerable = [c for c in cases if c['kind'] == 'answerable']
    unanswerable = [c for c in cases if c['kind'] == 'unanswerable']

    print('cases=%d  answerable=%d  unanswerable=%d' % (len(cases), len(answerable), len(unanswerable)))
    print('split=%s' % dict(Counter(c['split'] for c in cases)))
    print('label_status=%s' % dict(Counter(c.get('label_status', '?') for c in cases)))

    missing, cross, repeated = [], [], []
    for c in answerable:
        for e in c.get('evidence', []):
            f, a = e['file'], e['anchor']
            if f not in docs:
                missing.append((c['id'], f, 'expected file absent'))
                continue
            n = docs[f].count(a)
            if n == 0:
                missing.append((c['id'], f, 'anchor not found: %r' % a))
                continue
            others = [g for g, t in docs.items() if g != f and a in t]
            if others:
                cross.append((c['id'], f, repr(a), others))
            if n > 1:
                repeated.append((c['id'], f, repr(a), n))

    print('\n[hard] anchors missing from expected files: %d' % len(missing))
    for row in missing:
        print('   FAIL', row)
    print('[warn] cross-file anchors: %d' % len(cross))
    for row in cross:
        print('   ', row)
    print('[info] anchors repeated within file (code tabs may be OK): %d' % len(repeated))
    for row in repeated:
        print('   ', row)

    print('\nunanswerable cases (verify each is truly out of corpus): %d' % len(unanswerable))
    for c in unanswerable:
        print('   %s  %s' % (c['id'], c['question']))

    if missing:
        print('\nRESULT: FAIL (%d hard problems)' % len(missing))
        sys.exit(1)
    print('\nRESULT: PASS (every anchor is present in its expected file; cross-file=%d)' % len(cross))


if __name__ == '__main__':
    main()
