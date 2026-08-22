import requests

NLP_ROUTES = {name: f"http://localhost:8700/nlp/{name}" for name in ("contradiction", "similarity", "classify", "sentiment", "drift")}


def detect_route(text):
    lowered = text.lower()
    return next((name for name in NLP_ROUTES if name in lowered), "classify")


def route(kind, inputs, timeout=60):
    text = "\n\n".join(open(path, encoding="utf-8").read() for path in inputs)
    kind = detect_route(text) if kind == "auto" else kind
    if kind not in NLP_ROUTES: raise ValueError(f"Unknown NLP route: {kind}")
    response = requests.post(NLP_ROUTES[kind], json={"texts": [open(path, encoding="utf-8").read() for path in inputs]}, timeout=timeout)
    response.raise_for_status(); return response.json()
