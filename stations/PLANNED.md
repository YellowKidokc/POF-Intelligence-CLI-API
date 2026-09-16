# Planned stations

Create any entry with `python cli.py --station-new NAME --from stations/_TEMPLATE` and then tailor only its `station.json` and prompt.

- `02_duplicate_crosses_priority` — decide when duplicate content crosses priority boundaries.
- `03_live_file_in_backup` — identify material that is live but stored in a backup area.
- `04_finding_in_priority_place` — assess findings located in an unexpected priority location.
- `05_weak_page_load_bearing` — flag thin or weak pages on which important navigation depends.
- `06_orphan_good_page` — identify valuable pages with no useful inbound links.
- `07_thin_but_linked` — review thin pages that remain materially linked.
- `08_version_order_mismatch` — resolve version names or dates that disagree with their ordering.

`90_report` is the aggregate Markdown station to copy wherever a folder needs its own reporting station. `91_report_html` is its validated, offline HTML variant.
