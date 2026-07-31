"""LLM 失败时的 PubType 启发式兜底规则。"""

from __future__ import annotations
import re

_TYPE_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("guideline", re.compile(r"(practice guideline|guideline|consensus)", re.I)),
    ("review", re.compile(r"(systematic review|meta-?analysis|narrative review|^review$)", re.I)),
    ("ai_ml", re.compile(r"(machine learning|neural network|artificial intelligence|deep learning)", re.I)),
]
_TYPE_PTYPE_HINTS: dict[str, tuple[str, ...]] = {
    "clinical": ("Clinical Trial", "Randomized Controlled Trial", "Multicenter Study", "Observational Study", "Cohort Study", "Case-Control Study", "Comparative Study", "Validation Study"),
    "basic_research": ("Animals", "Mice", "Rats", "Cell Line", "In Vitro", "Molecular", "Genetic", "Biochemical"),
    "review": ("Systematic Review", "Meta-Analysis", "Review", "Narrative Review"),
    "guideline": ("Practice Guideline", "Guideline", "Consensus Development Conference", "Clinical Conference"),
}


def fallback_type(publication_types: list[str], title: str, abstract: str) -> str:
    types_lower = {t.lower() for t in publication_types}
    text = f"{title} {abstract}".lower()
    if any(h.lower() in types_lower for h in _TYPE_PTYPE_HINTS["guideline"]) or _TYPE_PATTERNS[0][1].search(text): return "guideline"
    if any(h.lower() in types_lower for h in _TYPE_PTYPE_HINTS["review"]) or _TYPE_PATTERNS[1][1].search(text): return "review"
    if any(h.lower() in types_lower for h in _TYPE_PTYPE_HINTS.get("ai_ml", ())) or "machine learning" in types_lower or "neural networks, computer" in types_lower or _TYPE_PATTERNS[2][1].search(text): return "ai_ml"
    if any(h.lower() in types_lower for h in _TYPE_PTYPE_HINTS["clinical"]): return "clinical"
    if any(h.lower() in types_lower for h in _TYPE_PTYPE_HINTS["basic_research"]): return "basic_research"
    return "clinical"

_AI_ML_KEYWORDS = re.compile(r"\b(machine learning|deep learning|neural network[s]?, computer|artificial intelligence|LLM|ChatGPT|CNN|RNN|transformer)\b", re.I)

def looks_like_ai_ml(publication_types: list[str], title: str, abstract: str) -> bool:
    types_lower = " ".join(publication_types).lower()
    return "machine learning" in types_lower or "neural networks, computer" in types_lower or bool(_AI_ML_KEYWORDS.search(f"{title} {abstract}"))

def fallback_title_zh(title: str) -> str: return title.strip() if title else ""
def fallback_abstract_zh(abstract: str | None) -> str | None: return abstract.strip() if abstract else None
