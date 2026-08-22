from pathlib import Path

CONVERSION_MAP = {
    ".pdf": r"\\192.168.2.50\brain\conversion_station\PDF to Markdown\inbox",
    ".docx": r"\\192.168.2.50\brain\conversion_station\Documents to Markdown\inbox",
    ".html": r"\\192.168.2.50\brain\conversion_station\HTML to Markdown\inbox",
    ".png": r"\\192.168.2.50\brain\conversion_station\Images to Markdown\inbox",
    ".jpg": r"\\192.168.2.50\brain\conversion_station\Images to Markdown\inbox",
    ".jpeg": r"\\192.168.2.50\brain\conversion_station\Images to Markdown\inbox",
    ".mp4": r"\\192.168.2.50\brain\conversion_station\Audio Video to Markdown\inbox",
    ".m4a": r"\\192.168.2.50\brain\conversion_station\Audio Video to Markdown\inbox",
}


def dispatch(path, router, dry_run=True):
    source = Path(path); destination = CONVERSION_MAP.get(source.suffix.lower())
    if not destination: raise ValueError(f"Unsupported conversion format: {source.suffix}")
    return router.copy(source, destination, dry_run)
