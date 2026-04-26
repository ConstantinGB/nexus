from __future__ import annotations

CATALOG: list[dict] = [
    # ── Text / Chat ──────────────────────────────────────────────────────
    {"id": "llama3.2",          "display": "Llama 3.2",         "size": "3B",   "tags": ["chat", "text"],      "desc": "Meta's compact 3B chat model, fast on CPU"},
    {"id": "llama3.1",          "display": "Llama 3.1",         "size": "8B",   "tags": ["chat", "text"],      "desc": "Meta's 8B model with strong reasoning"},
    {"id": "mistral",           "display": "Mistral 7B",        "size": "7B",   "tags": ["chat", "text"],      "desc": "Fast 7B model with excellent instruction following"},
    {"id": "mistral-nemo",      "display": "Mistral Nemo",      "size": "12B",  "tags": ["chat", "text"],      "desc": "Mistral's 12B multilingual model"},
    {"id": "phi4",              "display": "Phi-4",             "size": "14B",  "tags": ["chat", "reasoning"], "desc": "Microsoft Phi-4: strong reasoning in a small footprint"},
    {"id": "phi3",              "display": "Phi-3 Mini",        "size": "3.8B", "tags": ["chat", "text"],      "desc": "Microsoft Phi-3 Mini: efficient small language model"},
    {"id": "gemma2",            "display": "Gemma 2",           "size": "9B",   "tags": ["chat", "text"],      "desc": "Google Gemma 2, well-balanced 9B model"},
    {"id": "qwen2.5",           "display": "Qwen 2.5",          "size": "7B",   "tags": ["chat", "text"],      "desc": "Alibaba Qwen 2.5: strong multilingual performance"},
    {"id": "deepseek-r1",       "display": "DeepSeek R1",       "size": "7B",   "tags": ["chat", "reasoning"], "desc": "DeepSeek R1 distill: chain-of-thought reasoning"},
    {"id": "dolphin-llama3",    "display": "Dolphin Llama3",    "size": "8B",   "tags": ["chat", "text"],      "desc": "Uncensored fine-tune of Llama 3 for creative tasks"},
    # ── Coding ───────────────────────────────────────────────────────────
    {"id": "codellama",         "display": "Code Llama",        "size": "7B",   "tags": ["coding"],            "desc": "Meta Code Llama: fine-tuned for code generation"},
    {"id": "qwen2.5-coder",     "display": "Qwen 2.5 Coder",   "size": "7B",   "tags": ["coding"],            "desc": "Alibaba's dedicated code model, strong on Python"},
    {"id": "starcoder2",        "display": "StarCoder2",        "size": "7B",   "tags": ["coding"],            "desc": "BigCode StarCoder2: 600+ programming languages"},
    {"id": "granite-code",      "display": "Granite Code",      "size": "8B",   "tags": ["coding"],            "desc": "IBM Granite Code: enterprise-focused code model"},
    # ── Vision ───────────────────────────────────────────────────────────
    {"id": "llava",             "display": "LLaVA",             "size": "7B",   "tags": ["vision", "chat"],    "desc": "Large Language and Vision Assistant"},
    {"id": "moondream",         "display": "Moondream 2",       "size": "1.8B", "tags": ["vision"],            "desc": "Tiny but capable vision model, runs on CPU"},
    {"id": "llava-llama3",      "display": "LLaVA Llama3",      "size": "8B",   "tags": ["vision", "chat"],    "desc": "LLaVA with Llama 3 backbone"},
    # ── Embedding ────────────────────────────────────────────────────────
    {"id": "nomic-embed-text",  "display": "Nomic Embed Text",  "size": "137M", "tags": ["embedding"],         "desc": "High-quality text embeddings, 8192 context window"},
    {"id": "mxbai-embed-large", "display": "MxBai Embed Large", "size": "335M", "tags": ["embedding"],         "desc": "MixedBread AI large embedding model"},
    {"id": "all-minilm",        "display": "All-MiniLM",        "size": "23M",  "tags": ["embedding"],         "desc": "Sentence-transformers MiniLM: fast lightweight embeddings"},
]


def get_by_id(model_id: str) -> dict | None:
    return next((m for m in CATALOG if m["id"] == model_id), None)


def search(query: str) -> list[dict]:
    if not query:
        return CATALOG
    q = query.lower()
    return [
        m for m in CATALOG
        if q in m["id"].lower()
        or q in m["display"].lower()
        or q in m["desc"].lower()
        or any(q in t for t in m["tags"])
    ]
