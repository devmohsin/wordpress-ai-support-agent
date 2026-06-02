"""
Streamlit-compatible doc scraper.
Uses synchronous `requests` + threading instead of aiohttp,
so it works perfectly on Streamlit Cloud without any C-extensions.
"""

import re
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup


class StreamlitDocScraper:
    SKIP_EXTENSIONS = ('.pdf', '.zip', '.png', '.jpg', '.jpeg', '.gif', '.svg', '.ico', '.mp4')
    SKIP_TAGS       = ['nav', 'footer', 'header', 'script', 'style', 'aside', 'form', 'noscript']
    HEADERS         = {"User-Agent": "AISupportBot/1.0"}

    def __init__(self):
        self._visited: set  = set()
        self._lock          = threading.Lock()
        self._max_pages     = 20
        self._docs: List[Dict] = []

    def scrape(self, start_url: str, max_pages: int = 20) -> List[Dict]:
        """Crawl start_url and all same-domain links. Returns list of {url, title, content}."""
        self._visited    = set()
        self._docs       = []
        self._max_pages  = max_pages
        base_domain      = urlparse(start_url).netloc

        self._crawl(start_url, base_domain)
        return self._docs

    def _crawl(self, url: str, base_domain: str):
        with self._lock:
            if url in self._visited or len(self._visited) >= self._max_pages:
                return
            self._visited.add(url)

        try:
            resp = requests.get(url, timeout=10, headers=self.HEADERS)
            if resp.status_code != 200 or 'text/html' not in resp.headers.get('Content-Type', ''):
                return
            html = resp.text
        except Exception:
            return

        soup = BeautifulSoup(html, 'html.parser')
        for tag in soup(self.SKIP_TAGS):
            tag.decompose()

        content = re.sub(r'\s+', ' ', soup.get_text(separator=' ', strip=True)).strip()

        if len(content) > 150:
            title = soup.title.string.strip() if soup.title and soup.title.string else url
            with self._lock:
                self._docs.append({"url": url, "title": title, "content": content})

        # Gather child links on the same domain
        child_urls = []
        for link in soup.find_all('a', href=True):
            next_url = urljoin(url, link['href']).split('#')[0]
            parsed   = urlparse(next_url)
            with self._lock:
                already_seen = next_url in self._visited
            if (
                parsed.netloc == base_domain
                and parsed.scheme in ('http', 'https')
                and not already_seen
                and not any(next_url.endswith(ext) for ext in self.SKIP_EXTENSIONS)
            ):
                child_urls.append(next_url)

        # Crawl children concurrently (max 3 threads — be polite)
        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = [executor.submit(self._crawl, u, base_domain) for u in child_urls[:15]]
            for f in as_completed(futures):
                pass
