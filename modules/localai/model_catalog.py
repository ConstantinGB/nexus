from __future__ import annotations

CATALOG: list[dict] = [
    # ── Text / Chat ──────────────────────────────────────────────────────
    {"id": "llama3.2",          "display": "Llama 3.2",         "size": "3B",   "vram_min_gb": 2.0, "tags": ["chat", "text"],      "desc": "Meta's compact 3B chat model, fast on CPU"},
    {"id": "llama3.1",          "display": "Llama 3.1",         "size": "8B",   "vram_min_gb": 5.0, "tags": ["chat", "text"],      "desc": "Meta's 8B model with strong reasoning"},
    {"id": "mistral",           "display": "Mistral 7B",        "size": "7B",   "vram_min_gb": 4.5, "tags": ["chat", "text"],      "desc": "Fast 7B model with excellent instruction following"},
    {"id": "mistral-nemo",      "display": "Mistral Nemo",      "size": "12B",  "vram_min_gb": 7.5, "tags": ["chat", "text"],      "desc": "Mistral's 12B multilingual model"},
    {"id": "phi4",              "display": "Phi-4",             "size": "14B",  "vram_min_gb": 9.0, "tags": ["chat", "reasoning"], "desc": "Microsoft Phi-4: strong reasoning in a small footprint"},
    {"id": "phi3",              "display": "Phi-3 Mini",        "size": "3.8B", "vram_min_gb": 2.5, "tags": ["chat", "text"],      "desc": "Microsoft Phi-3 Mini: efficient small language model"},
    {"id": "gemma2",            "display": "Gemma 2",           "size": "9B",   "vram_min_gb": 5.5, "tags": ["chat", "text"],      "desc": "Google Gemma 2, well-balanced 9B model"},
    {"id": "qwen2.5",           "display": "Qwen 2.5",          "size": "7B",   "vram_min_gb": 4.5, "tags": ["chat", "text"],      "desc": "Alibaba Qwen 2.5: strong multilingual performance"},
    {"id": "deepseek-r1",       "display": "DeepSeek R1",       "size": "7B",   "vram_min_gb": 4.5, "tags": ["chat", "reasoning"], "desc": "DeepSeek R1 distill: chain-of-thought reasoning"},
    {"id": "dolphin-llama3",    "display": "Dolphin Llama3",    "size": "8B",   "vram_min_gb": 5.0, "tags": ["chat", "text"],      "desc": "Uncensored fine-tune of Llama 3 for creative tasks"},
    # ── Coding ───────────────────────────────────────────────────────────
    {"id": "codellama",         "display": "Code Llama",        "size": "7B",   "vram_min_gb": 4.5, "tags": ["coding"],            "desc": "Meta Code Llama: fine-tuned for code generation"},
    {"id": "qwen2.5-coder",     "display": "Qwen 2.5 Coder",   "size": "7B",   "vram_min_gb": 4.5, "tags": ["coding"],            "desc": "Alibaba's dedicated code model, strong on Python"},
    {"id": "starcoder2",        "display": "StarCoder2",        "size": "7B",   "vram_min_gb": 4.5, "tags": ["coding"],            "desc": "BigCode StarCoder2: 600+ programming languages"},
    {"id": "granite-code",      "display": "Granite Code",      "size": "8B",   "vram_min_gb": 5.0, "tags": ["coding"],            "desc": "IBM Granite Code: enterprise-focused code model"},
    # ── Vision ───────────────────────────────────────────────────────────
    {"id": "llava",             "display": "LLaVA",             "size": "7B",   "vram_min_gb": 4.5, "tags": ["vision", "chat"],    "desc": "Large Language and Vision Assistant"},
    {"id": "moondream",         "display": "Moondream 2",       "size": "1.8B", "vram_min_gb": 1.5, "tags": ["vision"],            "desc": "Tiny but capable vision model, runs on CPU"},
    {"id": "llava-llama3",      "display": "LLaVA Llama3",      "size": "8B",   "vram_min_gb": 5.0, "tags": ["vision", "chat"],    "desc": "LLaVA with Llama 3 backbone"},
    # ── Embedding ────────────────────────────────────────────────────────
    {"id": "nomic-embed-text",  "display": "Nomic Embed Text",  "size": "137M", "vram_min_gb": 0.5, "tags": ["embedding"],         "desc": "High-quality text embeddings, 8192 context window"},
    {"id": "mxbai-embed-large", "display": "MxBai Embed Large", "size": "335M", "vram_min_gb": 0.8, "tags": ["embedding"],         "desc": "MixedBread AI large embedding model"},
    {"id": "all-minilm",        "display": "All-MiniLM",        "size": "23M",  "vram_min_gb": 0.2, "tags": ["embedding"],              "desc": "Sentence-transformers MiniLM: fast lightweight embeddings"},
    # ── Large / Frontier ─────────────────────────────────────────────────
    {"id": "llama3.3",          "display": "Llama 3.3",         "size": "70B",  "vram_min_gb": 42.0, "tags": ["chat", "text"],          "desc": "Meta's flagship 70B model, state-of-the-art on benchmarks"},
    {"id": "llama3.1:70b",      "display": "Llama 3.1 70B",     "size": "70B",  "vram_min_gb": 42.0, "tags": ["chat", "text"],          "desc": "Meta Llama 3.1 70B — best open-weight reasoning"},
    {"id": "mixtral",           "display": "Mixtral 8x7B",      "size": "47B",  "vram_min_gb": 28.0, "tags": ["chat", "text"],          "desc": "Mistral sparse MoE: 47B params, 13B active — very fast"},
    {"id": "command-r",         "display": "Command R",         "size": "35B",  "vram_min_gb": 22.0, "tags": ["chat", "text"],          "desc": "Cohere Command R: optimised for RAG and tool use"},
    {"id": "command-r-plus",    "display": "Command R+",        "size": "104B", "vram_min_gb": 64.0, "tags": ["chat", "text"],          "desc": "Cohere Command R+ 104B — frontier-class open model"},
    # ── Reasoning ────────────────────────────────────────────────────────
    {"id": "deepseek-r1:14b",   "display": "DeepSeek R1 14B",   "size": "14B",  "vram_min_gb": 9.0,  "tags": ["chat", "reasoning"],     "desc": "DeepSeek R1 distill 14B: strong CoT on consumer GPU"},
    {"id": "deepseek-r1:32b",   "display": "DeepSeek R1 32B",   "size": "32B",  "vram_min_gb": 20.0, "tags": ["chat", "reasoning"],     "desc": "DeepSeek R1 distill 32B: near-frontier reasoning"},
    {"id": "qwq",               "display": "QwQ 32B",           "size": "32B",  "vram_min_gb": 20.0, "tags": ["chat", "reasoning"],     "desc": "Qwen reasoning model — strong math and logic"},
    {"id": "phi4-mini",         "display": "Phi-4 Mini",        "size": "3.8B", "vram_min_gb": 2.5,  "tags": ["chat", "reasoning"],     "desc": "Microsoft Phi-4 Mini: efficient reasoning, runs on CPU"},
    # ── More coding ──────────────────────────────────────────────────────
    {"id": "devstral",          "display": "Devstral",          "size": "22B",  "vram_min_gb": 14.0, "tags": ["coding"],                "desc": "Mistral coding model optimised for agentic tasks"},
    {"id": "deepseek-coder-v2", "display": "DeepSeek Coder V2", "size": "16B",  "vram_min_gb": 10.0, "tags": ["coding"],                "desc": "DeepSeek Coder V2: state-of-the-art open code model"},
    {"id": "codegemma",         "display": "CodeGemma",         "size": "7B",   "vram_min_gb": 4.5,  "tags": ["coding"],                "desc": "Google CodeGemma: code generation and completion"},
    {"id": "yi-coder",          "display": "Yi Coder",          "size": "9B",   "vram_min_gb": 5.5,  "tags": ["coding"],                "desc": "01.AI Yi Coder: strong multilingual code model"},
    # ── Multimodal ───────────────────────────────────────────────────────
    {"id": "gemma3",            "display": "Gemma 3",           "size": "12B",  "vram_min_gb": 7.5,  "tags": ["vision", "chat"],        "desc": "Google Gemma 3 multimodal: image + text, excellent quality"},
    {"id": "minicpm-v",         "display": "MiniCPM-V",         "size": "8B",   "vram_min_gb": 5.0,  "tags": ["vision", "chat"],        "desc": "Efficient vision-language model with OCR support"},
    {"id": "qwen2.5vl",         "display": "Qwen2.5-VL",        "size": "7B",   "vram_min_gb": 4.5,  "tags": ["vision", "chat"],        "desc": "Alibaba Qwen2.5 Vision-Language model"},
    # ── Specialised / Small ──────────────────────────────────────────────
    {"id": "aya",               "display": "Aya Expanse",       "size": "8B",   "vram_min_gb": 5.0,  "tags": ["chat", "multilingual"],  "desc": "Cohere Aya Expanse: 23-language multilingual assistant"},
    {"id": "smollm2",           "display": "SmolLM2",           "size": "1.7B", "vram_min_gb": 1.2,  "tags": ["chat", "text"],          "desc": "HuggingFace SmolLM2: tiny but capable, ideal for CPU"},
    {"id": "tinyllama",         "display": "TinyLlama",         "size": "1.1B", "vram_min_gb": 0.8,  "tags": ["chat", "text"],          "desc": "Tiny 1.1B Llama — runs anywhere, fast responses"},
    {"id": "falcon3",           "display": "Falcon3",           "size": "7B",   "vram_min_gb": 4.5,  "tags": ["chat", "text"],          "desc": "TII Falcon3: efficient instruct model"},
    {"id": "solar-pro",         "display": "Solar Pro",         "size": "22B",  "vram_min_gb": 14.0, "tags": ["chat", "text"],          "desc": "Upstage Solar Pro: strong instruction following"},
    {"id": "nemotron-mini",     "display": "Nemotron Mini",     "size": "4B",   "vram_min_gb": 3.0,  "tags": ["chat", "text"],          "desc": "NVIDIA Nemotron Mini 4B: efficient conversational model"},
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


def fit_rating(model: dict, hw: dict) -> str:
    """Return 'recommended' | 'fits' | 'cpu-only' | 'too-large' based on hardware."""
    vram_min = model.get("vram_min_gb", 0.0)
    vram_gb  = hw.get("vram_gb", 0.0)
    ram_gb   = hw.get("ram_gb", 0.0)

    if vram_gb > 0:
        if vram_min <= vram_gb * 0.7:
            return "recommended"
        if vram_min <= vram_gb:
            return "fits"
        if vram_min <= ram_gb * 0.5:
            return "cpu-only"
        return "too-large"

    # No dedicated GPU — evaluate against system RAM
    if vram_min <= 4.0 or (ram_gb > 0 and vram_min <= ram_gb * 0.5):
        return "cpu-only"
    return "too-large"
