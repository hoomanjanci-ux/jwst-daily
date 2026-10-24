"""Post-deploy smoke check against the public site; never sends Telegram posts."""
import json
import os
from pathlib import Path
import time
import requests


def verify(base, content, get=requests.get):
    analyses = [a for a in content.get('analyses', [])
                if a.get('text_fa') or a.get('text_en')]
    paths = ['/'] + ['/post/' + a['slug'] for a in analyses[:4]]
    for path in paths:
        r = get(base.rstrip('/') + path, timeout=30)
        r.raise_for_status()
        if len(r.text) < 100:
            raise RuntimeError('Unexpected empty page: ' + path)
        print('site verified:', path, flush=True)
    sitemap = get(base.rstrip('/') + '/sitemap.xml', timeout=30)
    sitemap.raise_for_status()
    if analyses and '/post/' + analyses[0]['slug'] not in sitemap.text:
        raise RuntimeError('Latest published analysis missing from sitemap')


if __name__ == '__main__':
    content = json.loads((Path(__file__).resolve().parents[1] /
                          'site/data/content.json').read_text())
    base = os.environ.get('SITE_VERIFY_URL', 'https://nabzekeyhan.vercel.app')
    for attempt in range(3):
        try:
            verify(base, content)
            break
        except requests.RequestException:
            if attempt == 2:
                raise
            time.sleep(10)
