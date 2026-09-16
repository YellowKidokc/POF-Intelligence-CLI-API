# Station input format

David-OS v3's `engine/aggregate_report.py` produces `bundle.json` and `anomalies.csv`. A future splitter can turn each anomaly row into one UTF-8 Markdown inbox file. The station system intentionally does not implement that splitter.

```markdown
---
kind: duplicate_live_copy
severity: high
path: docs/current/page.md
---

## Why
The anomaly's `why` text goes here.

## File content
The complete content of `docs/current/page.md` goes here.
```

`kind`, `severity`, and `path` are required frontmatter fields. Keep one anomaly per file, retain the report's explanation under **Why**, and include the affected file's own content so a station can decide without accessing the source tree.
