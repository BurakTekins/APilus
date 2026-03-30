# scraper_and_data

**TR:** ACU Chatbot projesinin veri toplama modülü. Acıbadem Üniversitesi'nin iki farklı web sitesinden kamuya açık içerikleri otomatik olarak toplar ve JSON formatında kaydeder.

**EN:** Data collection module for the ACU Chatbot project. Automatically scrapes publicly available content from two different Acıbadem University websites and saves the output in JSON format.

---

## 📁 Files / Dosyalar

### 🐍 Python Scripts

#### `acu_scraper.py`
**TR:**
Ana üniversite sitesini (`www.acibadem.edu.tr`) tarayan scraper. JavaScript gerektirmeyen statik sayfalar için `requests` + `BeautifulSoup` kullanır. BFS (genişlik öncelikli arama) algoritmasıyla tüm linkleri takip eder ve sayfa içeriklerini metin olarak çıkarır.

**EN:**
Scraper that crawls the main university website (`www.acibadem.edu.tr`). Uses `requests` + `BeautifulSoup` for static pages that do not require JavaScript. Follows all links using a BFS (breadth-first search) algorithm and extracts page content as plain text.

- **Method / Yöntem:** `requests` + `BeautifulSoup`
- **Target / Hedef:** `https://www.acibadem.edu.tr`
- **Output / Çıktı:** `acu_data.json`
- **Log:** `acu_scraper.log`

---

#### `bologna_scraper.py`
**TR:**
Bologna Bilgi Sistemi'ni (`obs.acibadem.edu.tr`) tarayan Selenium tabanlı scraper. Site JavaScript ve IFRAME mimarisi kullandığından `requests` ile erişilemez; gerçek bir Chrome tarayıcısı headless modda çalıştırılır. Her akademik program için 12 farklı alt sayfa (program hakkında, ders listesi, kabul koşulları, istihdam olanakları vb.) ayrı ayrı çekilir.

**EN:**
Selenium-based scraper that crawls the Bologna Information System (`obs.acibadem.edu.tr`). Since the site uses JavaScript and an IFRAME architecture, it cannot be accessed with `requests`; a real Chrome browser is run in headless mode. For each academic program, 12 different sub-pages (about the program, course list, admission requirements, employment opportunities, etc.) are fetched individually.

- **Method / Yöntem:** `Selenium` + `BeautifulSoup`
- **Target / Hedef:** `https://obs.acibadem.edu.tr`
- **Output / Çıktı:** `bologna_data.json`
- **Log:** `bologna_scraper.log`

---

### 📄 JSON Outputs

#### `acu_data.json`
**TR:**
`acu_scraper.py` tarafından üretilen veri dosyası. `www.acibadem.edu.tr` sitesindeki tüm genel sayfalara ait içerikleri barındırır: fakülteler, bölümler, kampüs hayatı, duyurular, iletişim bilgileri vb.

**EN:**
Data file produced by `acu_scraper.py`. Contains content from all general pages on `www.acibadem.edu.tr`: faculties, departments, campus life, announcements, contact information, etc.

```json
{
  "scrape_info": {
    "created_at": "...",
    "finished_at": "...",
    "sites": { "acibadem_main": 950 },
    "total_pages": 950
  },
  "pages": [
    {
      "source": "acibadem_main",
      "url": "https://www.acibadem.edu.tr/...",
      "title": "...",
      "description": "...",
      "keywords": "...",
      "lang": "tr",
      "text": "...",
      "scraped_at": "2026-...",
      "depth": 1
    }
  ]
}
```

---

#### `bologna_data.json`
**TR:**
`bologna_scraper.py` tarafından üretilen veri dosyası. Tüm akademik programlara ait detaylı bilgileri içerir. Her kayıt hangi programa ve hangi alt sayfaya ait olduğunu belirtir: ders listeleri, program yeterlikleri, kabul koşulları, mezuniyet koşulları vb.

**EN:**
Data file produced by `bologna_scraper.py`. Contains detailed information about all academic programs. Each record specifies which program and which sub-page it belongs to: course lists, program competencies, admission requirements, graduation requirements, etc.

```json
{
  "scrape_info": {
    "created_at": "...",
    "finished_at": "...",
    "source": "obs.acibadem.edu.tr - Bologna",
    "total_records": 1200,
    "by_category": {
      "program_detay": 1100,
      "program_listesi": 4,
      "genel_bilgi": 15
    },
    "programs_scraped": 92
  },
  "pages": [
    {
      "source": "acibadem_obs_bologna",
      "url": "https://obs.acibadem.edu.tr/oibs/bologna/progCourses.aspx?...",
      "category": "program_detay",
      "program_name": "Bilgisayar Mühendisliği (İngilizce)",
      "menu_text": "Lisans",
      "subpage": "Dersler",
      "title": "...",
      "text": "...",
      "tables": [["Ders Kodu", "Ders Adı", "AKTS"], ["..."]],
      "scraped_at": "2026-..."
    }
  ]
}
```

---

### 📋 Log Files

#### `acu_scraper.log`
**TR:**
`acu_scraper.py` çalışırken üretilen log dosyası. Her ziyaret edilen URL, sayfa sayısı, derinlik bilgisi ve oluşan hatalar zaman damgasıyla birlikte kaydedilir.

**EN:**
Log file generated while `acu_scraper.py` runs. Every visited URL, page count, depth level, and any errors are recorded with timestamps.

```
2026-03-13 20:00:01 [INFO] SITE : acibadem.edu.tr (requests+BS4)
2026-03-13 20:00:02 [INFO] [main] (1/1000) depth=0  https://www.acibadem.edu.tr
2026-03-13 20:00:04 [WARNING] Request error https://...: ...
```

---

#### `bologna_scraper.log`
**TR:**
`bologna_scraper.py` çalışırken üretilen log dosyası. Her program, her alt sayfa ve Selenium tarayıcısının durumu zaman damgasıyla kaydedilir. Hata ayıklama ve scraping sürecini izleme için kullanılır.

**EN:**
Log file generated while `bologna_scraper.py` runs. Each program, each sub-page, and the status of the Selenium browser are recorded with timestamps. Used for debugging and monitoring the scraping process.

```
2026-03-13 21:00:01 [INFO] Bologna OBS Scraper is starting
2026-03-13 21:00:06 [INFO] [menü] 'Lisans' => unitSelection.aspx?type=lis&lang=tr
2026-03-13 21:00:10 [INFO]   [program] 'Bilgisayar Mühendisliği' sunit=6246
2026-03-13 21:00:12 [INFO]     ✓ Dersler (4821 character)
```

---

## ⚙️ Setup / Kurulum

```bash
# For acu_scraper.py
pip install requests beautifulsoup4 lxml

# For bologna_scraper.py
pip install selenium beautifulsoup4 lxml webdriver-manager
# Google Chrome must be installed / Google Chrome kurulu olmalı
```

## 🚀 Usage / Kullanım

```bash
python acu_scraper.py
python bologna_scraper.py
```

## ⚠️ Responsible Scraping / Sorumlu Scraping

**TR:** Her istek arasında 1–2.5 saniye bekleme uygulanır. Üniversitenin sunucularına aşırı yük bindirmemek için bu değerler düşürülmemelidir.

**EN:** A 1–2.5 second delay is applied between each request. These values should not be reduced to avoid overloading the university's servers.