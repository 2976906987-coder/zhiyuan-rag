"""Fetch a pinned, MIT-licensed FastAPI Chinese documentation snapshot."""
import hashlib
import json
from pathlib import Path
import re
import httpx

FILES = ['first-steps', 'path-params', 'query-params', 'body', 'request-files',
         'request-forms', 'handling-errors', 'response-model', 'response-status-code',
         'cors', 'middleware', 'background-tasks', 'testing', 'static-files',
         'body-updates', 'encoder']


def main():
    root = Path('eval/corpus/fastapi')
    root.mkdir(parents=True, exist_ok=True)
    manifest_path = root.parent / 'manifest.json'
    with httpx.Client(timeout=60, follow_redirects=True) as client:
        if manifest_path.exists():
            sha = json.loads(manifest_path.read_text(encoding='utf-8'))['commit']
        else:
            sha = '40e33e492dbf4af6172997f4e3238a32e56cbe26'  # FastAPI 0.115.0
        base = f'https://raw.githubusercontent.com/fastapi/fastapi/{sha}'
        license_response = client.get(base+'/LICENSE')
        license_response.raise_for_status()
        (root.parent / 'LICENSE-fastapi.txt').write_text(license_response.text, encoding='utf-8')
        sources = []
        for name in FILES:
            path = f'docs/zh/docs/tutorial/{name}.md'
            response = client.get(base+'/'+path)
            response.raise_for_status()
            text = response.text
            # Materialize code snippets referenced by the official Markdown.
            snippets = re.findall(r'(docs_src/[^\s}]+\.py)', text)
            for snippet in dict.fromkeys(snippets):
                code_response = client.get(base+'/'+snippet)
                code_response.raise_for_status()
                pattern = r'\{\*\s*'+re.escape(snippet)+r'\s*[^}]*\*\}'
                code = '\n```python\n'+code_response.text+'\n```\n'
                text = re.sub(pattern, lambda _: code, text)
                text = re.sub(r'\{!\s*(?:\.\./)*'+re.escape(snippet)+r'\s*!\}', lambda _: code_response.text, text)
            (root / f'{name}.md').write_text(text, encoding='utf-8')
            sources.append({'file': f'{name}.md', 'url': f'https://github.com/fastapi/fastapi/blob/{sha}/{path}', 'sha256': hashlib.sha256(text.encode()).hexdigest(), 'embedded_snippets': snippets})
            print('fetched', name, flush=True)
        manifest_path.write_text(json.dumps({'repository':'fastapi/fastapi','commit':sha,'license':'MIT','transformation':'official snippet directives expanded to full Python files; remaining Markdown preserved','sources':sources},ensure_ascii=False,indent=2),encoding='utf-8')


if __name__ == '__main__':
    main()
