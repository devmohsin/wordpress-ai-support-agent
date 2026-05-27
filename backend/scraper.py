import asyncio
import aiohttp
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from typing import List, Dict
import re


class DocScraper:
    """Crawls a documentation website and extracts clean text content."""

    SKIP_EXTENSIONS = ('.pdf', '.zip', '.png', '.jpg', '.jpeg', '.gif', '.svg', '.ico', '.mp4')
    SKIP_TAGS = ['nav', 'footer', 'header', 'script', 'style', 'aside', 'form', 'noscript']

    def __init__(self):
        self.visited: set = set()
        self.max_pages: int = 50

    async def scrape(self, start_url: str, max_pages: int = 50) -> List[Dict]:
        """Entry point: scrape all pages under start_url and return structured docs."""
        self.max_pages = max_pages
        self.visited = set()
        base_domain = urlparse(start_url).netloc
        docs: List[Dict] = []

        timeout = aiohttp.ClientTimeout(total=15)
        connector = aiohttp.TCPConnector(limit=5)  # Polite crawl limit

        async with aiohttp.ClientSession(timeout=timeout, connector=connector) as session:
            await self._crawl(session, start_url, base_domain, docs)

        return docs

    async def _crawl(self, session: aiohttp.ClientSession, url: str, base_domain: str, docs: List[Dict]):
        """Recursively crawl a page and follow same-domain links."""
        if url in self.visited or len(self.visited) >= self.max_pages:
            return

        self.visited.add(url)

        try:
            async with session.get(url, headers={"User-Agent": "DocBot/1.0"}) as resp:
                if resp.status != 200 or 'text/html' not in resp.content_type:
                    return
                html = await resp.text(errors='ignore')
        except Exception:
            return

        soup = BeautifulSoup(html, 'html.parser')

        # Strip non-content elements before text extraction
        for tag in soup(self.SKIP_TAGS):
            tag.decompose()

        content = soup.get_text(separator=' ', strip=True)
        content = re.sub(r'\s+', ' ', content).strip()

        if len(content) > 150:
            title = soup.title.string.strip() if soup.title and soup.title.string else url
            docs.append({"url": url, "title": title, "content": content})

        # Collect child links on same domain
        tasks = []
        for link in soup.find_all('a', href=True):
            next_url = urljoin(url, link['href']).split('#')[0]  # Strip anchors
            parsed = urlparse(next_url)

            if (
                parsed.netloc == base_domain
                and parsed.scheme in ('http', 'https')
                and next_url not in self.visited
                and not any(next_url.endswith(ext) for ext in self.SKIP_EXTENSIONS)
            ):
                tasks.append(self._crawl(session, next_url, base_domain, docs))

        # Run child crawls concurrently but in small batches
        for i in range(0, len(tasks), 5):
            await asyncio.gather(*tasks[i:i + 5])
