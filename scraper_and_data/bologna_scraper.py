"""
ACU Chatbot - Bologna OBS Selenium Scraper
=================================================================
Structure:
  1. pull unitSelection data
  2. For every program open index.aspx?curOp=showPac...
     → IFRAME1 otomaticly loads progAbout.aspx?curSunit=XXX
  3. Does direkt fetch to all Programs:
       progAbout.aspx      → Program Hakkında
       progProfile.aspx    → Program Profili  
       progCourses.aspx    → Dersler (ders listesi)
       progOutcomes.aspx   → Program Yeterlikleri
       progAdmission.aspx  → Kabul Koşulları
       ... and so on

Setup:
  pip install selenium beautifulsoup4 lxml webdriver-manager

Usage:
  python bologna_scraper.py
"""

import json
import time
import random
import logging
import re
import sys
from datetime import datetime, timezone
from urllib.parse import urljoin, urlparse, parse_qs

from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.common.exceptions import WebDriverException, TimeoutException

try:
    from webdriver_manager.chrome import ChromeDriverManager
    from selenium.webdriver.chrome.service import Service
    USE_WDM = True
except ImportError:
    USE_WDM = False

# ─── CONFIG ───────────────────────────────────────────────────────────────────

HEADLESS         = True
DELAY_MIN        = 1.0
DELAY_MAX        = 2.0
SELENIUM_WAIT    = 4       # for JS render stall
SELENIUM_TIMEOUT = 15
OUTPUT_FILE      = "bologna_data.json"

BASE_URL  = "https://obs.acibadem.edu.tr/oibs/bologna/"
START_URL = "https://obs.acibadem.edu.tr/oibs/bologna/index.aspx?lang=tr"

# All subpage schemes
# Will load as {sunit} → curSunit
PROGRAM_SUBPAGES = [
    ("progAbout.aspx?lang=tr&curSunit={sunit}",      "Program Hakkında"),
    ("progProfile.aspx?lang=tr&curSunit={sunit}",    "Program Profili"),
    ("progAuthority.aspx?lang=tr&curSunit={sunit}",  "Program Yetkilileri"),
    ("progDegree.aspx?lang=tr&curSunit={sunit}",     "Alınacak Derece"),
    ("progAdmission.aspx?lang=tr&curSunit={sunit}",  "Kabul Koşulları"),
    ("progTransition.aspx?lang=tr&curSunit={sunit}", "Üst Kademeye Geçiş"),
    ("progGraduation.aspx?lang=tr&curSunit={sunit}", "Mezuniyet Koşulları"),
    ("progRecognition.aspx?lang=tr&curSunit={sunit}","Önceki Öğrenmenin Tanınması"),
    ("progQualification.aspx?lang=tr&curSunit={sunit}", "Yeterlilik Koşulları"),
    ("progEmployment.aspx?lang=tr&curSunit={sunit}", "İstihdam Olanakları"),
    ("progOutcomes.aspx?lang=tr&curSunit={sunit}",   "Program Yeterlikleri"),
    ("progCourses.aspx?lang=tr&curSunit={sunit}",    "Dersler"),
]

# ─── LOGGING ──────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("bologna_scraper.log", encoding="utf-8"),
    ],
)
log = logging.getLogger(__name__)

# ─── DRIVER ───────────────────────────────────────────────────────────────────

def get_driver():
    options = Options()
    if HEADLESS:
        options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument(
        "user-agent=Mozilla/5.0 (compatible; ACU-Chatbot-Scraper/1.0; CSE322)"
    )
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)

    if USE_WDM:
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
    else:
        driver = webdriver.Chrome(options=options)

    driver.execute_script(
        "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
    )
    return driver

# ─── PAGE FETCHER ─────────────────────────────────────────────────────────────

def fetch_direct(driver, url: str, wait: float = None) -> str | None:

    try:
        driver.get(url)
        time.sleep(wait or SELENIUM_WAIT)
        try:
            WebDriverWait(driver, SELENIUM_TIMEOUT).until(
                lambda d: d.execute_script("return document.readyState") == "complete"
            )
        except TimeoutException:
            log.warning("readyState timeout: %s", url)
        return driver.page_source
    except WebDriverException as e:
        log.warning("Fetch error %s: %s", url, str(e).splitlines()[0])
        return None


def fetch_iframe1_src(driver) -> str | None:

    try:
        iframe = driver.find_element("id", "IFRAME1")
        src = iframe.get_attribute("src")
        return src if src else None
    except Exception:
        return None

# ─── PARSING ──────────────────────────────────────────────────────────────────

def get_menu_items(driver) -> list:

    soup = BeautifulSoup(driver.page_source, "lxml")
    items = []
    pattern = re.compile(r"menu_close|myOnFrameClick", re.I)
    for el in soup.find_all(onclick=pattern):
        onclick = el.get("onclick", "")
        text = el.get_text(strip=True)
        match = re.search(r"menu_close\([^,]+,\s*['\"]([^'\"]+)['\"]", onclick)
        if not match:
            match = re.search(r"myOnFrameClick\(['\"]([^'\"]+)['\"]", onclick)
        if match:
            rel = match.group(1)
            items.append({"text": text, "url": urljoin(BASE_URL, rel)})
    log.info("From Menu %d item was found.", len(items))
    return items


def get_program_links(html: str, base: str) -> list:

    soup = BeautifulSoup(html, "lxml")
    programs = []
    seen = set()
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if not href:
            continue
        if "curOp=showPac" in href or "curOp=showProg" in href:
            abs_url = urljoin(base, href)
            if abs_url not in seen:
                seen.add(abs_url)
                # curSunit değerini çıkar
                qs = parse_qs(urlparse(abs_url).query)
                sunit = qs.get("curSunit", [None])[0]
                programs.append({
                    "text": a.get_text(strip=True),
                    "url": abs_url,
                    "sunit": sunit,
                })
    log.info("  %d program links has been found.", len(programs))
    return programs


def extract_program_menu_links(html: str, base: str) -> list:

    soup = BeautifulSoup(html, "lxml")
    links = []
    seen = set()
    pattern = re.compile(r"menu_close|myOnFrameClick|OnFrameClick", re.I)

    for el in soup.find_all(onclick=pattern):
        onclick = el.get("onclick", "")
        text = el.get_text(strip=True)
        match = re.search(r"menu_close\([^,]+,\s*['\"]([^'\"]+)['\"]", onclick)
        if not match:
            match = re.search(r"(?:myOnFrameClick|OnFrameClick)\(['\"]([^'\"]+)['\"]", onclick)
        if match:
            rel = match.group(1)
            abs_url = urljoin(base, rel)
            if abs_url not in seen:
                seen.add(abs_url)
                links.append({"text": text, "url": abs_url})

    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if re.search(r"prog[A-Z][a-z]+\.aspx", href):
            abs_url = urljoin(base, href)
            if abs_url not in seen:
                seen.add(abs_url)
                links.append({"text": a.get_text(strip=True), "url": abs_url})

    return links


def extract_text(html: str) -> str:
    soup = BeautifulSoup(html, "lxml")
    for tag in soup(["script", "style", "noscript", "iframe", "head"]):
        tag.decompose()
    main = (
        soup.find("main")
        or soup.find(id=re.compile(r"content|main|body", re.I))
        or soup.find(class_=re.compile(r"content|main|article", re.I))
        or soup.body
    )
    target = main if main else soup
    text = target.get_text(separator="\n", strip=True)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def extract_tables(html: str) -> list:
    soup = BeautifulSoup(html, "lxml")
    tables_data = []
    for table in soup.find_all("table"):
        rows = []
        for tr in table.find_all("tr"):
            cells = [td.get_text(strip=True) for td in tr.find_all(["td", "th"])]
            if any(cells):
                rows.append(cells)
        if len(rows) > 1:
            tables_data.append(rows)
    return tables_data


def extract_title(html: str) -> str:
    soup = BeautifulSoup(html, "lxml")
    for h in ["h1", "h2", "h3"]:
        tag = soup.find(h)
        if tag and tag.get_text(strip=True):
            return tag.get_text(strip=True)
    if soup.title and soup.title.string:
        return soup.title.string.strip()
    return ""


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def make_record(url, prog_name, menu_text, subpage_name, html, category) -> dict:
    return {
        "source": "acibadem_obs_bologna",
        "url": url,
        "category": category,
        "program_name": prog_name,
        "menu_text": menu_text,
        "subpage": subpage_name,
        "title": extract_title(html),
        "text": extract_text(html),
        "tables": extract_tables(html),
        "scraped_at": now_iso(),
    }

# ─── SCRAPER ──────────────────────────────────────────────────────────────────

def scrape_program_subpages(driver, prog: dict, menu_text: str) -> list:

    prog_url  = prog["url"]
    prog_name = prog["text"]
    sunit     = prog["sunit"]
    results   = []

    log.info("  [program] %r  sunit=%s", prog_name, sunit)

    html = fetch_direct(driver, prog_url, wait=SELENIUM_WAIT)
    if not html:
        return results

    iframe_src = fetch_iframe1_src(driver)
    log.info("    IFRAME1 src: %s", iframe_src)

    if not sunit and iframe_src:
        qs = parse_qs(urlparse(iframe_src).query)
        sunit = qs.get("curSunit", [None])[0]
        log.info("    sunit has been taken from iframe: %s", sunit)

    if not sunit:
        log.warning("    sunit has not been found, skip.")
        return results

    extra_links = extract_program_menu_links(html, prog_url)
    log.info("    From Menu %d extra link.", len(extra_links))

    fetched_urls = set()

    subpage_urls = []
    for tmpl, spname in PROGRAM_SUBPAGES:
        sp_url = urljoin(BASE_URL, tmpl.format(sunit=sunit))
        subpage_urls.append((sp_url, spname))

    for el in extra_links:
        if el["url"] not in [u for u, _ in subpage_urls]:
            subpage_urls.append((el["url"], el["text"]))

    for sp_url, sp_name in subpage_urls:
        if sp_url in fetched_urls:
            continue
        fetched_urls.add(sp_url)

        log.info("    [sub] %s → %s", sp_name, sp_url)
        sp_html = fetch_direct(driver, sp_url, wait=2)

        if not sp_html:
            time.sleep(random.uniform(DELAY_MIN, DELAY_MAX))
            continue

        text = extract_text(sp_html)
        if len(text) < 30:
            log.debug("    Empty Page: %s", sp_url)
            time.sleep(random.uniform(DELAY_MIN, DELAY_MAX))
            continue

        results.append(make_record(
            url=sp_url,
            prog_name=prog_name,
            menu_text=menu_text,
            subpage_name=sp_name,
            html=sp_html,
            category="program_detay",
        ))
        log.info("    ✓ %s (%d character)", sp_name, len(text))
        time.sleep(random.uniform(DELAY_MIN, DELAY_MAX))

    return results


def scrape_bologna() -> list:
    log.info("=" * 60)
    log.info("Bologna OBS Scraper is starting")
    log.info("=" * 60)

    driver = get_driver()
    results = []
    visited_progs: set = set()

    try:
        log.info("Main page is loading: %s", START_URL)
        fetch_direct(driver, START_URL, wait=SELENIUM_WAIT + 1)
        log.info("Main page is ready.")
        menu_items = get_menu_items(driver)

        for item in menu_items:
            item_url  = item["url"]
            menu_text = item["text"]

            if "unitSelection" in item_url:
                log.info("[menü] %r => %s", menu_text, item_url)

                html = fetch_direct(driver, item_url, wait=SELENIUM_WAIT)
                if not html or len(extract_text(html)) < 10:
                    continue

                # Sayfayı kaydet
                results.append({
                    "source": "acibadem_obs_bologna",
                    "url": item_url,
                    "category": "program_listesi",
                    "program_name": "",
                    "menu_text": menu_text,
                    "subpage": "liste",
                    "title": menu_text,
                    "text": extract_text(html),
                    "tables": extract_tables(html),
                    "scraped_at": now_iso(),
                })

                programs = get_program_links(html, item_url)

                for prog in programs:
                    prog_url = prog["url"]
                    if prog_url in visited_progs:
                        continue
                    visited_progs.add(prog_url)

                    sub_results = scrape_program_subpages(driver, prog, menu_text)
                    results.extend(sub_results)
                    time.sleep(random.uniform(DELAY_MIN, DELAY_MAX))

            # Genel bilgi sayfaları (dynConPage)
            elif "dynConPage" in item_url:
                log.info("[menü] %r => %s", menu_text, item_url)
                html = fetch_direct(driver, item_url, wait=SELENIUM_WAIT)
                if not html or len(extract_text(html)) < 30:
                    continue

                results.append({
                    "source": "acibadem_obs_bologna",
                    "url": item_url,
                    "category": "genel_bilgi",
                    "program_name": "",
                    "menu_text": menu_text,
                    "subpage": "",
                    "title": menu_text,
                    "text": extract_text(html),
                    "tables": [],
                    "scraped_at": now_iso(),
                })
                time.sleep(random.uniform(DELAY_MIN, DELAY_MAX))

    finally:
        log.info("Chrome driver kapatılıyor...")
        driver.quit()

    log.info("Tamamlandı: %d kayıt", len(results))
    return results

# ─── MAIN ─────────────────────────────────────────────────────────────────────

def main():
    log.info("ACU Bologna Scraper v6 başlıyor...")
    started_at = now_iso()

    pages = scrape_bologna()

    cats: dict = {}
    progs: dict = {}
    for p in pages:
        c = p.get("category", "?")
        cats[c] = cats.get(c, 0) + 1
        pn = p.get("program_name", "")
        if pn:
            progs[pn] = progs.get(pn, 0) + 1

    output = {
        "scrape_info": {
            "created_at": started_at,
            "finished_at": now_iso(),
            "source": "obs.acibadem.edu.tr - Bologna",
            "total_records": len(pages),
            "by_category": cats,
            "programs_scraped": len(progs),
        },
        "pages": pages,
    }

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    log.info("")
    log.info("✅ Tamamlandı!")
    log.info("   Toplam kayıt      : %d", len(pages))
    log.info("   Program sayısı    : %d", len(progs))
    for cat, count in cats.items():
        log.info("   %-25s: %d", cat, count)
    log.info("   Çıktı             : %s", OUTPUT_FILE)


if __name__ == "__main__":
    main()