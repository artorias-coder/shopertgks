import os
import re
from pathlib import Path
from PIL import Image
import pytesseract

SCREENSHOTS_DIR = Path(__file__).resolve().parent.parent / "Скриншоты_из_видео"
OUTPUT_FILE = Path(__file__).resolve().parent.parent / "screenshots_text.txt"


def extract_text(image_path: Path) -> str:
    try:
        img = Image.open(image_path)
        text = pytesseract.image_to_string(img, lang="rus+eng")
        return text.strip()
    except Exception as e:
        return f"ERROR: {e}"


def main():
    images = sorted(SCREENSHOTS_DIR.glob("*.png"))
    lines = []
    for img in images:
        text = extract_text(img)
        lines.append(f"=== {img.name} ===")
        lines.append(text)
        lines.append("")
    OUTPUT_FILE.write_text("\n".join(lines), encoding="utf-8")
    print(f"Распознано {len(images)} скриншотов. Результат: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
