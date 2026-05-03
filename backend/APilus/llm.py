import hashlib
import json
import logging
import os
import shutil
from pathlib import Path
import httpx
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS

# Optional: Set up logging for error handling
logger = logging.getLogger(__name__)

RAG_SCORE_THRESHOLD = float(os.environ.get("RAG_SCORE_THRESHOLD", "12.0"))

# Bumped whenever the embedded text shape OR Document.metadata schema
# changes in a way that makes the persisted FAISS index stale. This is
# concatenated with the data-file fingerprint and stored in
# faiss_index_store/version.txt; a mismatch triggers a rebuild.
_INDEX_SCHEMA_VERSION = "v3-desc+lang+subpage+menu_text+contenthash_dedup"

_CORPUS_KEYWORDS = {
    "bologna": ["ders", "müfredat", "akts", "ects", "kredi", "dönem", "yarıyıl",
                "curriculum", "course", "credit", "semester", "bologna", "program"],
    "acu":     ["rektör", "dekan", "duyuru", "kampüs", "iletişim", "adres",
                "tarih", "vakıf", "kuruluş", "rector", "campus", "contact"],
}

# Canonical -> distinguishing alias substrings. Aliases are matched after
# _normalize() (lowercased, ASCII-folded). The first match wins, so order
# matters when two canonicals share a root word: more specific (longer)
# names should come before their shorter cousins. Aliases are deliberately
# hand-curated rather than auto-derived from program_name to avoid
# silent collisions like "ingilizce" or "hemsirelik" mapping to many
# different programs. The post-retrieval reranker matches program_name as
# a substring, so listing one canonical (e.g. "Hemşirelik") still surfaces
# its tezli/tezsiz/doktora variants from the index.
_PROGRAM_ALIASES = {
    # --- Faculties / undergraduate programs (existing) ---
    "Tıp Fakültesi":                    ["tıp fakültesi", "tıp", "medicine", "medical faculty", "tip fakultesi"],
    "Hemşirelik":                       ["hemşirelik", "hemsirelik", "nursing"],
    "Fizyoterapi ve Rehabilitasyon":    ["fizyoterapi", "rehabilitasyon", "physiotherapy"],
    "Psikoloji":                        ["psikoloji", "psychology"],
    "Eczacılık Fakültesi (İngilizce)":  ["eczacılık", "eczacilik", "pharmacy"],
    "Beslenme ve Diyetetik":            ["beslenme", "diyetetik", "nutrition", "dietetics"],
    "Biyomedikal Mühendisliği (İngilizce)": ["biyomedikal", "biomedical"],
    "Bilgisayar Mühendisliği (İngilizce)":  ["bilgisayar mühendisliği", "computer engineering"],
    "Moleküler Biyoloji ve Genetik (İngilizce)": ["moleküler biyoloji", "genetik", "molecular biology", "genetics"],
    "Sağlık Yönetimi":                  ["sağlık yönetimi", "health management"],
    "Aşçılık":                          ["aşçılık", "gastronomi", "culinary", "mutfak"],
    "Anestezi":                         ["anestezi", "anesthesia"],
    "Diyaliz":                          ["diyaliz", "dialysis"],
    "Tıbbi Görüntüleme Teknikleri":     ["tıbbi görüntüleme", "radyoloji", "medical imaging"],
    "İlk ve Acil Yardım":               ["acil yardım", "ilk yardım", "emergency", "paramedic"],

    # --- Vocational / associate-degree programs ---
    "Ameliyathane Hizmetleri":          ["ameliyathane", "operating room"],
    "Ağız ve Diş Sağlığı":              ["ağız ve diş", "agiz ve dis", "diş sağlığı", "oral and dental", "dental health"],
    "Bilgisayar Programcılığı":         ["bilgisayar programcılığı", "computer programming"],
    "Biyomedikal Cihaz Teknolojisi":    ["biyomedikal cihaz", "biomedical device"],
    "Elektronörofizyoloji":             ["elektronörofizyoloji", "elektronorofizyoloji", "electroneurophysiology"],
    "Ergoterapi":                       ["ergoterapi", "occupational therapy"],
    "Odyometri":                        ["odyometri", "audiometry"],
    "Optisyenlik":                      ["optisyenlik", "optician", "optometry"],
    "Ortopedik Protez ve Ortez":        ["ortopedik protez", "ortez", "orthotic", "prosthetic"],
    "Patoloji Laboratuvar Teknikleri":  ["patoloji laboratuvar", "pathology lab"],
    "Podoloji":                         ["podoloji", "podiatry"],
    "Radyoterapi":                      ["radyoterapi", "radiotherapy"],
    "Tıbbi Dokümantasyon ve Sekreterlik": ["tıbbi dokümantasyon", "medical documentation", "medical secretary"],
    "Tıbbi Laboratuvar Teknikleri":     ["tıbbi laboratuvar", "medical laboratory"],
    "Tıbbi Veri İşleme Teknikerliği":   ["tıbbi veri işleme", "medical data processing"],

    # --- Graduate programs (only those whose root word doesn't already
    #     resolve to an existing canonical above; e.g. "hemsirelik" alone
    #     already covers nursing graduate variants via reranker substring). ---
    "Adli Bilimler Tezli Yüksek Lisans": ["adli bilimler", "forensic science"],
    "Anatomi (Tıp) Tezli Yüksek Lisans": ["anatomi", "anatomy"],
    "Bilişsel Nöropsikoloji Tezli Yüksek Lisans": ["bilişsel nöropsikoloji", "cognitive neuropsychology"],
    "Biyoetik Tezli Yüksek Lisans":     ["biyoetik", "bioethics"],
    "Biyofizik Doktora Programı (İngilizce)": ["biyofizik", "biophysics"],
    "Biyokimya (Tıp) Tezli Yüksek Lisans": ["biyokimya", "biochemistry"],
    "Dünya Siyaseti ve Uluslararası İlişkiler Tezli Yüksek Lisans": [
        "dünya siyaseti", "uluslararası ilişkiler", "world politics", "international relations"
    ],
    "Epidemiyoloji ve Biyoistatistik Tezli Yüksek Lisans": [
        "epidemiyoloji", "biyoistatistik", "epidemiology", "biostatistics"
    ],
    "Hukuk-Hakimlik Tezli Yüksek Lisans": ["hukuk", "hakimlik", "law", "judgeship"],
    "İş Sağlığı ve Güvenliği Tezli Yüksek Lisans": [
        "iş sağlığı", "iş güvenliği", "occupational health", "occupational safety"
    ],
    "Kimya (Tıp) Doktora Programı":     ["kimya (tıp)", "chemistry (medical)"],
    "Klinik Biyokimya Tezli Yüksek Lisans": ["klinik biyokimya", "clinical biochemistry"],
    "Klinik Mikrobiyoloji ve Enfeksiyon Hastalıkları Tezli Yüksek Lisans": [
        "klinik mikrobiyoloji", "enfeksiyon hastalıkları", "clinical microbiology", "infectious diseases"
    ],
    "Medikal Biyoloji ve Genetik Tezli Yüksek Lisans": [
        "medikal biyoloji", "medical biology"
    ],
    "Medikal Fizik Tezli Yüksek Lisans": ["medikal fizik", "medical physics"],
    "Nütrisyon ve Metabolizma Doktora": ["nütrisyon", "metabolizma", "nutrition and metabolism"],
    "Sağlık Bilişimi Tezli Yüksek Lisans": ["sağlık bilişimi", "health informatics"],
    "Sağlık Hukuku Tezli Yüksek Lisans": ["sağlık hukuku", "health law"],
    "Sosyal Hizmet Tezli Yüksek Lisans": ["sosyal hizmet", "social work"],
    "Temel Tıp Bilimleri Doktora":      ["temel tıp bilimleri", "basic medical sciences"],
    "Tıbbi Biyokimya Tezli Yüksek Lisans": ["tıbbi biyokimya", "medical biochemistry"],
    "Uygulamalı Etik Tezli Yüksek Lisans": ["uygulamalı etik", "applied ethics"],
    "Yönetim ve Organizasyon Doktora":  ["yönetim ve organizasyon", "management and organization"],
}

# Subpage routing — when a query mentions courses/curriculum or graduation
# requirements, narrow Bologna retrieval to the matching subpage. Only
# applied when the source filter is already acibadem_obs_bologna (acu_data
# pages have subpage="" and would otherwise be excluded by the AND filter).
_SUBPAGE_KEYWORDS = {
    "Dersler": [
        "ders", "müfredat", "course", "courses", "curriculum", "syllabus",
        "akts", "ects", "kredi", "credit",
    ],
    "Mezuniyet Koşulları": [
        "mezuniyet", "graduation", "koşul", "kosul", "requirement", "requirements",
    ],
}

# --- 1. EFFICIENT VECTOR DATABASE SETUP ---

def _load_documents(json_path: str) -> list:
    with open(json_path, encoding="utf-8") as f:
        data = json.load(f)
    pages = data.get("pages", [])
    docs = []
    seen_urls = set()
    # Bologna OBS occasionally serves the same content body under multiple
    # URLs (different language toggles, archived paths). The URL-based
    # dedup above catches exact-URL collisions; this content-hash dedup
    # catches the ~145 cases where (program_name, subpage) and the body
    # text are identical but the URL differs. We key on body+program+
    # subpage rather than body alone so that genuinely separate programs
    # which happen to share boilerplate (e.g. empty "Üst Kademeye Geçiş"
    # filler) are not collapsed into one. Title/description are
    # intentionally excluded from the key because they are prepended later
    # and can vary harmlessly between duplicate scrapes.
    seen_content = set()
    for page in pages:
        url = page.get("url", "")
        if url in seen_urls:
            continue
        seen_urls.add(url)

        text = page.get("text", "").strip()

        # Serialize tables into readable text
        # tables is list[list[list]] — each table is a list of rows, first row is header
        for table in page.get("tables", []):
            if not table:
                continue
            for row in table:
                line = " | ".join(str(c) for c in row if str(c).strip())
                if line:
                    text += "\n" + line

        # Filter navigation-heavy and empty pages on the RAW body+tables
        # only. Description and title are prepended afterwards so they
        # cannot rescue nav pages by inflating length or diluting the
        # newline-density signal.
        word_count = len(text.split())
        newline_count = text.count("\n")
        if len(text) < 200:
            continue
        if word_count > 0 and newline_count / word_count > 0.5:
            continue

        # Drop exact-text duplicates that survived URL dedup (same
        # program + subpage + body, different URL). SHA-1 over the raw
        # body+tables text — cheap and collision-safe at this scale.
        content_key = (
            page.get("program_name", ""),
            page.get("subpage", ""),
            hashlib.sha1(text.encode("utf-8")).hexdigest(),
        )
        if content_key in seen_content:
            continue
        seen_content.add(content_key)

        # Prepend description (acu_data pages) as leading semantic signal
        # for the embedding model, but only when it adds new content. For
        # roughly 40% of pages the description is already a substring of
        # the body text; duplicating it would just bias the embedding.
        description = page.get("description", "").strip()
        if description and description not in text:
            text = description + "\n" + text

        title = page.get("title", "")
        if title:
            text = title + "\n" + text

        docs.append(Document(
            page_content=text,
            metadata={
                "url": url,
                "title": title,
                "source": page.get("source", ""),
                "category": page.get("category", ""),
                "program_name": page.get("program_name", ""),
                # Widened metadata for future filtering. lang lives on
                # acu_data pages; subpage and menu_text live on
                # bologna_data pages. Missing fields default to "".
                "lang": page.get("lang", ""),
                "subpage": page.get("subpage", ""),
                "menu_text": page.get("menu_text", ""),
            }
        ))
    return docs


_vector_db = None  # module-level singleton


def _index_fingerprint(json_files: list[str]) -> str:
    """Compose a fingerprint for the persisted FAISS index.

    Combines the schema version (bumped in code whenever the embedded
    text shape or metadata schema changes) with each data file's path,
    size, and mtime. Cheap to compute on every startup; reliably detects
    when the data has been re-scraped or the loader logic has been
    revised. We deliberately avoid SHA-256 of multi-MB JSONs to keep
    cold-start latency low.
    """
    parts = [_INDEX_SCHEMA_VERSION]
    for path in json_files:
        try:
            st = os.stat(path)
            parts.append(f"{path}:{st.st_size}:{int(st.st_mtime)}")
        except OSError:
            parts.append(f"{path}:missing")
    digest = hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()
    return f"{_INDEX_SCHEMA_VERSION}|{digest}"


def get_vector_db():
    global _vector_db
    if _vector_db is not None:
        return _vector_db

    # 1. Check if the index is already loaded in memory (Singleton)
    current_path = Path(__file__).resolve().parent

    BASE_DIR = None
    for path in [current_path] + list(current_path.parents):
        if (path / "scraper_and_data").exists():
            BASE_DIR = path
            break
    if BASE_DIR is None:
        raise RuntimeError("Could not find project root containing 'scraper_and_data' folder.")

    # Use the fast, small MiniLM model for CPU-efficient embeddings
    embeddings = HuggingFaceEmbeddings(
        model_name="paraphrase-multilingual-MiniLM-L12-v2",
        model_kwargs={'device': 'cpu'}
    )

    # Define where to store the database
    INDEX_PATH = BASE_DIR / "RAG" / "faiss_index_store"
    VERSION_FILE = INDEX_PATH / "version.txt"

    json_files = [
        str(BASE_DIR / "scraper_and_data" / "acu_data.json"),
        str(BASE_DIR / "scraper_and_data" / "bologna_data.json"),
    ]
    expected_fingerprint = _index_fingerprint(json_files)

    # 2. Decide whether the on-disk index is reusable.
    fresh = False
    if INDEX_PATH.exists() and (INDEX_PATH / "index.faiss").exists():
        on_disk_fingerprint = ""
        if VERSION_FILE.exists():
            try:
                on_disk_fingerprint = VERSION_FILE.read_text(encoding="utf-8").strip()
            except OSError:
                on_disk_fingerprint = ""
        fresh = (on_disk_fingerprint == expected_fingerprint)
        if not fresh:
            logger.info(
                "FAISS index fingerprint mismatch (disk=%r expected=%r); rebuilding.",
                on_disk_fingerprint, expected_fingerprint,
            )
            # Wipe the stale index so save_local can recreate it cleanly.
            shutil.rmtree(INDEX_PATH, ignore_errors=True)

    if fresh:
        print("Loading existing Vector DB from disk...")
        _vector_db = FAISS.load_local(
            str(INDEX_PATH),
            embeddings,
            allow_dangerous_deserialization=True  # Required for loading local FAISS files
        )
    else:
        # 3. Build (or rebuild) the index.
        docs = []
        for file in json_files:
            docs.extend(_load_documents(file))

        text_splitter = RecursiveCharacterTextSplitter(chunk_size=800, chunk_overlap=100)
        chunks = text_splitter.split_documents(docs)

        print(f"Building NEW Vector DB with {len(chunks)} chunks...")
        _vector_db = FAISS.from_documents(chunks, embeddings)
        _vector_db.save_local(str(INDEX_PATH))
        try:
            VERSION_FILE.write_text(expected_fingerprint, encoding="utf-8")
        except OSError as exc:
            logger.warning("Failed to write FAISS version sentinel: %s", exc)
        print(f"Vector DB saved to {INDEX_PATH}")

    return _vector_db

# --- 2. INTENT CLASSIFIER ---

def _normalize(text: str) -> str:
    text = text.replace("İ", "i").replace("I", "ı")
    text = text.lower()
    return text.translate(str.maketrans("çğıöşü", "cgiosu"))


def _normalize_for_search(query: str) -> str:
    """Lowercase and strip Turkish diacritics for FAISS retrieval.

    The multilingual embedding model retrieves more reliably when
    diacritics are normalized. Use this for the FAISS query only;
    the original prompt should still be passed to the LLM.
    """
    return _normalize(query)


def is_university_query(text: str) -> bool:
    """Returns True if the question appears to be about Acıbadem University."""
    keywords = [
        # University/institution
        "acibadem", "universite", "university",
        "fakulte", "faculty", "bolum", "department",
        "program", "kampus", "campus",
        # People/roles
        "rektor", "rector", "dekan", "dean",
        # Academic process
        "kayit", "enrollment", "mezuniyet", "graduation",
        "ders", "course", "sinav", "exam",
        "ogrenci", "student", "hoca", "akademik", "academic",
        # Bologna/accreditation
        "bologna", "akreditasyon", "accreditation",
        "mufredat", "curriculum",
        "vakif", "kurulus",
    ]
    lowered = _normalize(text)
    return any(kw in lowered for kw in keywords)


# --- 3. PLAIN OLLAMA (no RAG) ---

def ask_ollama_plain(prompt: str, history: list[dict] | None = None) -> str:
    """Calls Ollama directly without any RAG context, for non-university questions."""
    base_url = os.environ.get("OLLAMA_BASE_URL", "http://127.0.0.1:11434/v1")
    url = f"{base_url.rstrip('/')}/chat/completions"
    model = os.environ.get("OLLAMA_MODEL", "gemma3:4b")

    system_prompt = (
        "IMPORTANT: Detect the language of the question. "
        "If Turkish, respond entirely in Turkish. "
        "If English, respond entirely in English. Never mix languages.\n\n"
        "You are a helpful assistant."
    )

    messages = [{"role": "system", "content": system_prompt}]
    if history:
        messages.extend(history)
    messages.append({"role": "user", "content": prompt})

    payload = {
        "model": model,
        "messages": messages,
        "max_tokens": 512,
        "temperature": 0.5,
        "top_p": 0.95,
        "top_k": 50,
    }

    try:
        response = httpx.post(url, json=payload, timeout=120.0)
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"].strip()

    except httpx.HTTPStatusError as e:
        logger.exception("Ollama returned %s: %s", e.response.status_code, e.response.text)
        return "LLM service is currently unavailable. Please check if Ollama is running."
    except Exception:
        logger.exception("Ollama call failed")
        return "LLM service is currently unavailable."


# --- 4. ROUTER ---

def chat(prompt: str, history: list[dict] | None = None) -> str:
    """Routes to RAG pipeline for university questions, plain Ollama otherwise."""
    if is_university_query(prompt):
        return ask_acibadem_ollama(prompt, history=history)
    return ask_ollama_plain(prompt, history=history)


# --- 5. OLLAMA RAG GENERATION ---
def _pick_k(query: str) -> int:
    q = _normalize(query)
    # Keywords are normalized on the fly so the literal list stays
    # readable in Turkish orthography; without _normalize() here,
    # diacritic-bearing entries like "tüm", "müfredat", "dönem",
    # "yarıyıl" would never match the ASCII-folded query.
    broad_keywords = ["liste", "tüm", "all", "hangi", "müfredat",
                      "dönem", "semester", "yarıyıl", "curriculum"]
    if any(_normalize(w) in q for w in broad_keywords):
        return 10
    if len(q.split()) <= 5:
        return 3
    return 5


def _detect_subpage(q_normalized: str) -> str | None:
    """Pick a Bologna `subpage` value implied by the query, if any.

    `q_normalized` must already be passed through `_normalize`. Returns
    None when no subpage signal is present, or when the query implies
    multiple subpages (in which case routing back to the broader source
    is safer than guessing). Keywords are themselves normalized on the
    fly so the source dict stays readable in Turkish orthography.
    """
    matches = []
    for subpage, kws in _SUBPAGE_KEYWORDS.items():
        if any(_normalize(kw) in q_normalized for kw in kws):
            matches.append(subpage)
    if len(matches) == 1:
        return matches[0]
    return None


def _extract_filters(query: str) -> tuple[dict, str | None]:
    q = _normalize(query)
    # _PROGRAM_ALIASES is matched against the normalized (ASCII-folded)
    # query, so its aliases must be ASCII-folded too. We pre-normalize on
    # the fly here rather than at module load to keep the dict readable
    # in source.
    detected_program = None
    for canonical, aliases in _PROGRAM_ALIASES.items():
        if any(_normalize(alias) in q for alias in aliases):
            detected_program = canonical
            break
    filters: dict = {}
    if detected_program:
        filters["source"] = "acibadem_obs_bologna"
    # _CORPUS_KEYWORDS source dict keeps Turkish diacritics for
    # readability ("müfredat", "rektör", "kampüs", ...), but `q` has
    # already been ASCII-folded by _normalize(). Without this on-the-fly
    # normalization, every diacritic-bearing keyword is dead code — it
    # can never match. Match via `_normalize(kw) in q` to align both
    # sides.
    elif any(_normalize(kw) in q for kw in _CORPUS_KEYWORDS["bologna"]):
        filters["source"] = "acibadem_obs_bologna"
    elif any(_normalize(kw) in q for kw in _CORPUS_KEYWORDS["acu"]):
        filters["source"] = "acibadem_main"

    # Subpage routing is only safe when the source is already pinned to
    # Bologna; acu_data pages have subpage="" and an AND filter on
    # subpage would otherwise exclude them entirely. The FAISS retrieval
    # already falls back to the unfiltered query when the filtered call
    # returns nothing, so an over-narrow subpage filter degrades to the
    # source-only filter rather than to an empty result.
    if filters.get("source") == "acibadem_obs_bologna":
        subpage = _detect_subpage(q)
        if subpage:
            filters["subpage"] = subpage
    return filters, detected_program


def _format_context(docs: list) -> str:
    blocks = []
    for i, doc in enumerate(docs, 1):
        m = doc.metadata
        header_parts = []
        if m.get("program_name"): header_parts.append(f"Program: {m['program_name']}")
        if m.get("title"):        header_parts.append(f"Title: {m['title']}")
        if m.get("category"):     header_parts.append(f"Category: {m['category']}")
        header = " | ".join(header_parts)
        blocks.append(f"[Source {i}] {header}\n{doc.page_content.strip()}")
    return "\n\n---\n\n".join(blocks)


def ask_acibadem_ollama(prompt: str, history: list[dict] | None = None) -> str:
    """
    Retrieves context from FAISS and queries Ollama,
    strictly preventing hallucination on unknown data.
    """
    vector_db = get_vector_db()
    k = _pick_k(prompt)
    filters, detected_program = _extract_filters(prompt)

    # Normalize the query for retrieval only; the LLM still receives the
    # original prompt so it can answer in the user's exact wording/language.
    search_query = _normalize_for_search(prompt)

    # Try MMR first to keep retrieved chunks diverse and avoid the
    # double similarity_search_with_score call when filters miss. We
    # progressively widen the filter set on misses: full filters ->
    # source-only -> no filter, so an over-narrow subpage filter falls
    # back to the source rather than going straight to the global pool.
    def _filter_ladder(active: dict) -> list[dict | None]:
        rungs: list[dict | None] = []
        if active:
            rungs.append(dict(active))
            if "subpage" in active:
                relaxed = {k_: v for k_, v in active.items() if k_ != "subpage"}
                if relaxed:
                    rungs.append(relaxed)
            rungs.append(None)
        else:
            rungs.append(None)
        return rungs

    scored: list = []
    try:
        query_vector = vector_db.embedding_function.embed_query(search_query)
        for flt in _filter_ladder(filters):
            scored = vector_db.max_marginal_relevance_search_with_score_by_vector(
                query_vector,
                k=k,
                fetch_k=max(k * 4, 20),
                lambda_mult=0.5,
                filter=flt,
            )
            if scored:
                break
    except (AttributeError, NotImplementedError) as exc:
        logger.warning("MMR retrieval unavailable, falling back to similarity search: %s", exc)
        for flt in _filter_ladder(filters):
            scored = vector_db.similarity_search_with_score(search_query, k=k, filter=flt)
            if scored:
                break

    retrieved_docs = [doc for doc, score in scored if score < RAG_SCORE_THRESHOLD]

    logger.debug("RAG: k=%d filters=%s program=%s docs_after_threshold=%d",
                 k, filters, detected_program, len(retrieved_docs))

    if detected_program:
        # Match on _normalize() output (ASCII-folded, lowercased) so
        # canonicals like "İlk ve Acil Yardım" or "Tıp Fakültesi"
        # actually align with the program_name strings. A naive
        # str.lower() drops "İ" but leaves "Ş", "Ç" intact and the
        # substring check fails on legitimate matches.
        prog_norm = _normalize(detected_program)
        matched = [d for d in retrieved_docs
                   if prog_norm in _normalize(d.metadata.get("program_name", ""))]
        others  = [d for d in retrieved_docs if d not in matched]
        retrieved_docs = matched + others

    if not retrieved_docs:
        return "I do not have enough information in my database to answer this."

    context = _format_context(retrieved_docs)
    augmented_prompt = f"Context:\n{context}\n\nQuestion: {prompt}"

    # System prompt: strict on specific facts, lenient on framing partial info.
    system_prompt = (
        "IMPORTANT: Detect the language of the question. "
        "If Turkish, respond entirely in Turkish. "
        "If English, respond entirely in English. Never mix languages.\n\n"
        "You are a helpful assistant for Acıbadem University. "
        "Your job is to give clear, accurate answers to students and visitors "
        "using the sources provided below.\n\n"
        "Rules:\n"
        "1. Base your answer primarily on the sources below. You may use light reasoning "
        "and general knowledge to frame, summarize, or connect what the sources say, "
        "as long as the core facts come from them.\n"
        "2. NEVER invent specific facts. Do not make up program names, course codes, dates, "
        "numbers, fees, deadlines, or names of people. If a specific detail is not in the "
        "sources, say you do not have that detail.\n"
        "3. When helpful, mention the program, faculty, or topic area your answer relates to "
        "(e.g., 'in the Faculty of Medicine'). Do not write citation tags like [Source 1].\n"
        "4. Do not include URLs, links, or web addresses.\n"
        "5. When the sources cover the topic only partially, give the most useful answer "
        "you can from what is available. Open with a phrase like \"Based on available "
        "information...\" (or in Turkish, \"Mevcut bilgilere göre...\") and clearly note "
        "which specific details are missing. Only reply \"I do not have enough information "
        "in my database to answer this.\" when nothing in the sources relates to the question.\n"
        "6. Be clear and helpful. Use bullet points for lists of 3 or more items. "
        "Otherwise keep answers to 2-4 sentences in English, "
        "and 3-5 sentences in Turkish for a natural tone."
    )

    messages = [{"role": "system", "content": system_prompt}]
    if history:
        messages.extend(history)
    messages.append({"role": "user", "content": augmented_prompt})

    # Ollama OpenAI-compatible endpoint settings
    base_url = os.environ.get("OLLAMA_BASE_URL", "http://127.0.0.1:11434/v1")
    url = f"{base_url.rstrip('/')}/chat/completions"
    model = os.environ.get("OLLAMA_MODEL", "gemma3:4b")
    payload = {
        "model": model,  # Ensure you have pulled this model in Ollama: `ollama run gemma3:4b`
        "messages": messages,
        "max_tokens": 1024,
        "temperature": 0.4,
        "top_p": 0.95,
        "top_k": 50,
    }

    try:
        # Use httpx for efficient HTTP requests with a timeout fallback
        response = httpx.post(url, json=payload, timeout=120.0)
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"].strip()

    except httpx.HTTPStatusError as e:
        logger.exception("Ollama returned %s: %s", e.response.status_code, e.response.text)
        return "LLM service is currently unavailable. Please check if Ollama is running."
    except Exception:
        logger.exception("Ollama call failed")
        return "LLM service is currently unavailable."
