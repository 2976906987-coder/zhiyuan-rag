"""Wait for the external vector store before starting the single API worker."""
import os
import time
import urllib.request
from urllib.error import URLError


def main():
    base = os.environ.get('QDRANT_URL', '')
    if base:
        deadline = time.monotonic()+60
        while True:
            try:
                with urllib.request.urlopen(base.rstrip('/')+'/readyz', timeout=3) as response:
                    if response.status == 200:
                        break
            except (URLError, TimeoutError, OSError):
                pass
            if time.monotonic() >= deadline:
                raise SystemExit('Qdrant did not become ready within 60 seconds.')
            time.sleep(2)
    os.execvp('uvicorn',['uvicorn','app.main:app','--host','0.0.0.0','--port','8000'])


if __name__ == '__main__':
    main()
