import json
from pathlib import Path


def stage_proposal(source, destination, awaiting, classification="unclassified"):
    awaiting = Path(awaiting); awaiting.mkdir(parents=True, exist_ok=True)
    proposal = {"source": str(Path(source).resolve()), "destination": str(destination), "classification": classification, "approved": False}
    target = awaiting / f"{Path(source).stem}_routing_proposal.json"
    target.write_text(json.dumps(proposal, indent=2), encoding="utf-8")
    return target


def classify_prompt(text):
    """Deterministic fallback; API preflight can override this proposal."""
    lowered = text.lower()
    for category, words in {"NLP": ("sentiment", "similarity", "contradiction", "classify"), "DEEP_RESEARCH": ("research", "sources", "investigate"), "CODEX": ("code", "bug", "repository")}.items():
        if any(word in lowered for word in words): return category
    return "AWAITING_APPROVAL"
