"""Font download helper for NotoSansKR (Korean font for thumbnail text overlay).

Downloads the NotoSansKR variable weight font from Google Fonts GitHub and saves it to
assets/fonts/NotoSansKR-Bold.ttf. Korean fonts are typically 3-10MB.

Usage:
    uv run python scripts/download_font.py
"""

import sys
from pathlib import Path

import httpx

FONT_URL = (
    "https://github.com/google/fonts/raw/main/ofl/notosanskr/NotoSansKR%5Bwght%5D.ttf"
)
FONT_OUTPUT_PATH = Path("assets/fonts/NotoSansKR-Bold.ttf")
MIN_FILE_SIZE_BYTES = 1 * 1024 * 1024  # 1MB minimum — Korean fonts are large


def download_font(url: str, output_path: Path) -> None:
    """Download font file from URL to output_path with progress indication."""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    print(f"Downloading NotoSansKR font from Google Fonts GitHub...")
    print(f"URL: {url}")
    print(f"Destination: {output_path}")

    with httpx.Client(follow_redirects=True, timeout=60.0) as client:
        response = client.get(url)
        response.raise_for_status()
        output_path.write_bytes(response.content)

    file_size = output_path.stat().st_size
    file_size_mb = file_size / (1024 * 1024)
    print(f"Downloaded {file_size_mb:.2f} MB to {output_path}")

    if file_size < MIN_FILE_SIZE_BYTES:
        output_path.unlink()
        print(
            f"ERROR: Downloaded file is only {file_size} bytes — expected > 1MB for a Korean font.",
            file=sys.stderr,
        )
        print("The download may have failed or returned an error page.", file=sys.stderr)
        sys.exit(1)

    print(f"Font verification passed: {file_size_mb:.2f} MB (> 1MB required)")
    print(f"NotoSansKR font saved to {output_path}")


def main() -> None:
    if FONT_OUTPUT_PATH.exists():
        file_size = FONT_OUTPUT_PATH.stat().st_size
        if file_size >= MIN_FILE_SIZE_BYTES:
            print(f"Font already exists at {FONT_OUTPUT_PATH} ({file_size / (1024*1024):.2f} MB). Skipping download.")
            return
        else:
            print(f"Existing font file is too small ({file_size} bytes). Re-downloading...")

    download_font(FONT_URL, FONT_OUTPUT_PATH)


if __name__ == "__main__":
    main()
