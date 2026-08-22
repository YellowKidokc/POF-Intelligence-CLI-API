from pathlib import Path
from html.parser import HTMLParser


class _ActionParser(HTMLParser):
    def __init__(self):
        super().__init__(); self.actions = []; self.current = None; self.depth = 0

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if tag == "div" and "action-item" in values.get("class", "").split() and self.current is None:
            self.current = {"attrs": values, "text": []}; self.depth = 1
        elif self.current is not None: self.depth += 1

    def handle_endtag(self, tag):
        if self.current is not None:
            self.depth -= 1
            if self.depth == 0: self.actions.append(self.current); self.current = None

    def handle_data(self, data):
        if self.current is not None: self.current["text"].append(data)


def parse_actions(path):
    parser = _ActionParser(); parser.feed(Path(path).read_text(encoding="utf-8"))
    actions = []
    for index, node in enumerate(parser.actions, 1):
        attrs = node["attrs"]
        actions.append({"index": index, "operation": attrs.get("data-operation") or attrs.get("data-action"), "source": attrs.get("data-source"), "destination": attrs.get("data-destination") or attrs.get("data-dest"), "approved": attrs.get("data-approved", "false").lower() == "true", "text": " ".join("".join(node["text"]).split())})
    return actions


def execute_actions(path, router, execute=False):
    results = []
    for action in parse_actions(path):
        if not action["approved"] or action["operation"] not in {"move", "copy", "rename", "archive"}: continue
        method = getattr(router, action["operation"])
        args = [action["source"]] + ([] if action["operation"] == "archive" else [action["destination"]])
        results.append({"dry_run": method(*args, dry_run=True), "executed": method(*args, dry_run=False) if execute else None})
    return results
