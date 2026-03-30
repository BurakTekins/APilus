"""
ACU Chatbot - Web Scraper
===================================
Scrapes publicly available content from:
  1. https://www.acibadem.edu.tr         (requests+BS4)

Output: scraped_data.json

Setup:
  pip install  requests beautifulsoup4 lxml

Usage:
  python acu_scraper.py


HEADLESS      : If True you dont see browser
MAX_PAGES_*   : maximum pages to iterate
MAX_DEPTH_*   : maximum depth to go
DELAY_MIN/MAX : minimum or maximum delay time

"""

import json
import time
import random
import logging
import re
import sys
from datetime import datetime
from urllib.parse import urljoin, urlparse
from collections import deque

import requests
from bs4 import BeautifulSoup

# ─── CONFIG ───────────────────────────────────────────────────────────────────

HEADLESS = True

MAX_PAGES_MAIN = 1000
MAX_DEPTH_MAIN = 4

DELAY_MIN = 1.0
DELAY_MAX = 2.5

REQUEST_TIMEOUT   = 20   #seconds

OUTPUT_FILE = "acu_data.json" 

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; ACU-Chatbot-Scraper/1.0; "
        "CSE322 Academic Research Bot)"
    ),
    "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

# ─── LOGGING ──────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("acu_scraper.log", encoding="utf-8"),
    ],
)
log = logging.getLogger(__name__)

# ─── URL UTILS ────────────────────────────────────────────────────────────────

SKIP_EXTENSIONS = (
    ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
    ".zip", ".rar", ".tar", ".gz", ".7z",
    ".jpg", ".jpeg", ".png", ".gif", ".svg", ".webp", ".ico", ".bmp",
    ".mp4", ".mp3", ".avi", ".mov", ".wmv",
    ".css", ".js", ".json", ".xml", ".rss", ".atom",
)

def normalize_url(url: str) -> str:
    parsed = urlparse(url)
    clean = parsed._replace(fragment="")
    return clean.geturl().rstrip("/")

def is_same_domain(url: str, allowed_domain: str) -> bool:
    return urlparse(url).netloc == allowed_domain

def is_scrapable(url: str) -> bool:
    if not url.startswith("http"):
        return False
    path = urlparse(url).path.lower()
    return not any(path.endswith(ext) for ext in SKIP_EXTENSIONS)

def extract_links_from_soup(soup: BeautifulSoup, base_url: str) -> list:
    links = []
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if not href or href.startswith(("#", "mailto:", "tel:", "javascript:")):
            continue
        abs_url = urljoin(base_url, href)
        links.append(normalize_url(abs_url))
    return links

def extract_links_from_html(html: str, base_url: str) -> list:
    soup = BeautifulSoup(html, "lxml")
    return extract_links_from_soup(soup, base_url)

# ─── TEXT EXTRACTION ──────────────────────────────────────────────────────────

def extract_text_from_soup(soup: BeautifulSoup) -> str:
    for tag in soup(["script", "style", "noscript", "iframe", "svg", "head"]):
        tag.decompose()

    main = (
        soup.find("main")
        or soup.find(id=re.compile(r"content|main|body", re.I))
        or soup.find(class_=re.compile(r"content|main|article", re.I))
        or soup.body
    )
    target = main if main else soup
    text = target.get_text(separator="\n", strip=True)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()

def extract_text_from_html(html: str) -> str:
    soup = BeautifulSoup(html, "lxml")
    return extract_text_from_soup(soup)

def extract_metadata_from_soup(soup: BeautifulSoup, url: str) -> dict:
    title = soup.title.string.strip() if soup.title and soup.title.string else ""

    desc_tag = soup.find("meta", attrs={"name": re.compile(r"description", re.I)})
    description = desc_tag.get("content", "").strip() if desc_tag else ""

    kw_tag = soup.find("meta", attrs={"name": re.compile(r"keywords", re.I)})
    keywords = kw_tag.get("content", "").strip() if kw_tag else ""

    html_tag = soup.find("html")
    lang = html_tag.get("lang", "") if html_tag else ""

    return {
        "title": title,
        "description": description,
        "keywords": keywords,
        "lang": lang,
        "url": url,
    }

# ─── SITE : acibadem.edu.tr (requests + BeautifulSoup) ──────────────────────

def scrape_main_site() -> list:

    log.info("=" * 60)
    log.info("SITE : acibadem.edu.tr  (requests+BS4)")
    log.info("Max page: %d  |  Max depth: %d", MAX_PAGES_MAIN, MAX_DEPTH_MAIN)
    log.info("=" * 60)

    allowed_domain = "www.acibadem.edu.tr"
    start_url = normalize_url("https://www.acibadem.edu.tr")

    visited: set = set()
    queue: deque = deque([(start_url, 0)])
    results = []

    session = requests.Session()

    while queue and len(results) < MAX_PAGES_MAIN:
        url, depth = queue.popleft()

        if url in visited:
            continue
        if not is_same_domain(url, allowed_domain):
            continue
        if not is_scrapable(url):
            continue

        visited.add(url)
        log.info("[main] (%d/%d) depth=%d  %s", len(results)+1, MAX_PAGES_MAIN, depth, url)

        try:
            resp = session.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT, allow_redirects=True)
            resp.raise_for_status()

            content_type = resp.headers.get("Content-Type", "")
            if "text/html" not in content_type:
                time.sleep(random.uniform(DELAY_MIN, DELAY_MAX))
                continue

            soup = BeautifulSoup(resp.content, "lxml")
            final_url = resp.url

            meta = extract_metadata_from_soup(soup, final_url)
            text = extract_text_from_soup(soup)

            results.append({
                "source": "acibadem_main",
                "url": final_url,
                "title": meta["title"],
                "description": meta["description"],
                "keywords": meta["keywords"],
                "lang": meta["lang"],
                "text": text,
                "scraped_at": datetime.utcnow().isoformat() + "Z",
                "depth": depth,
            })

            if depth < MAX_DEPTH_MAIN:
                for link in extract_links_from_soup(soup, final_url):
                    if (
                        link not in visited
                        and is_same_domain(link, allowed_domain)
                        and is_scrapable(link)
                    ):
                        queue.append((link, depth + 1))

        except requests.exceptions.RequestException as e:
            log.warning("Request error %s: %s", url, e)

        time.sleep(random.uniform(DELAY_MIN, DELAY_MAX))

    log.info("SITE completed: %d page", len(results))
    return results

# ─── MAIN ─────────────────────────────────────────────────────────────────────

def main():
    log.info("ACU Chatbot Scraper starting...")
    log.info("Output: %s", OUTPUT_FILE)

    started_at = datetime.utcnow().isoformat() + "Z"
    all_pages = []

    main_pages = scrape_main_site()
    all_pages.extend(main_pages)

    output = {
        "scrape_info": {
            "created_at": started_at,
            "finished_at": datetime.utcnow().isoformat() + "Z",
            "sites": {
                "acibadem_main": len(main_pages),
            },
            "total_pages": len(all_pages),
        },
        "pages": all_pages,
    }

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    log.info("")
    log.info(" Completed!")
    log.info("   acibadem_main : %d page", len(main_pages))
    log.info("   TOTAL        : %d page", len(all_pages))
    log.info("   Output File : %s", OUTPUT_FILE)


if __name__ == "__main__":
    main()