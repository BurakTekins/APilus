"""
Prompt strings and message-list builders for the APilus LLM pipeline.

No retrieval logic here — just constants and formatters.
"""

# System prompt for the non-RAG (plain) path.
PLAIN_SYSTEM_PROMPT = (
    "IMPORTANT: Detect the language of the question. "
    "If Turkish, respond entirely in Turkish. "
    "If English, respond entirely in English. Never mix languages.\n\n"
    "You are a helpful assistant."
)

# System prompt for the RAG path — anti-hallucination rules + persona.
RAG_SYSTEM_PROMPT = (
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


def build_plain_messages(prompt: str, history: list[dict] | None = None) -> list[dict]:
    """Build the message list for a plain (non-RAG) Ollama call."""
    messages = [{"role": "system", "content": PLAIN_SYSTEM_PROMPT}]
    if history:
        messages.extend(history)
    messages.append({"role": "user", "content": prompt})
    return messages


def build_rag_messages(augmented_prompt: str, history: list[dict] | None = None) -> list[dict]:
    """Build the message list for a RAG-augmented Ollama call."""
    messages = [{"role": "system", "content": RAG_SYSTEM_PROMPT}]
    if history:
        messages.extend(history)
    messages.append({"role": "user", "content": augmented_prompt})
    return messages


def format_context(docs: list) -> str:
    """Render a list of LangChain Documents into a numbered context block."""
    blocks = []
    for i, doc in enumerate(docs, 1):
        m = doc.metadata
        header_parts = []
        if m.get("program_name"):
            header_parts.append(f"Program: {m['program_name']}")
        if m.get("title"):
            header_parts.append(f"Title: {m['title']}")
        if m.get("category"):
            header_parts.append(f"Category: {m['category']}")
        header = " | ".join(header_parts)
        blocks.append(f"[Source {i}] {header}\n{doc.page_content.strip()}")
    return "\n\n---\n\n".join(blocks)
