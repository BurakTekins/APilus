import hashlib
import json

from langchain_core.documents import Document


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
