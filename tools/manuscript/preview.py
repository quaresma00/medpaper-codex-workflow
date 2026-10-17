#!/usr/bin/env python3
"""Complete contact sheet from an already Word-exported PDF or rendered page PNGs."""
import argparse
import json
import re
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PIL import Image, ImageDraw, ImageOps


def contact(paths, output):
    if not paths: raise ValueError("no actual rendered pages")
    width, height, columns = 320, 480, 3
    canvas = Image.new("RGB", (columns*width, ((len(paths)+columns-1)//columns)*height), "#dddddd")
    draw = ImageDraw.Draw(canvas)
    for index, path in enumerate(paths):
        with Image.open(path) as page:
            thumbnail = ImageOps.contain(page.convert("RGB"), (width-16, height-32))
        x, y = index%columns*width, index//columns*height
        canvas.paste(thumbnail, (x+(width-thumbnail.width)//2, y+24)); draw.text((x+8, y+5), f"Page {index+1}", fill="black")
    output.parent.mkdir(parents=True, exist_ok=True); canvas.save(output)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--pdf", type=Path); group.add_argument("--png-dir", type=Path)
    parser.add_argument("--output", type=Path, required=True); parser.add_argument("--pdftoppm")
    args = parser.parse_args()
    try:
        with tempfile.TemporaryDirectory(prefix="medpaper-preview-") as folder:
            if args.pdf:
                binary = args.pdftoppm or shutil.which("pdftoppm")
                if not binary: raise ValueError("provide verified Poppler --pdftoppm; export DOCX with Microsoft Word, never LibreOffice")
                subprocess.run([binary, "-scale-to", "1200", "-png", str(args.pdf.resolve()), str(Path(folder)/"page")], check=True, timeout=180, capture_output=True)
                paths = sorted(Path(folder).glob("page-*.png"), key=lambda path: int(path.stem.rsplit("-",1)[1]))
            else: paths = sorted(args.png_dir.glob("*.png"), key=lambda path: [int(part) if part.isdigit() else part.casefold() for part in re.split(r"(\d+)",path.name)])
            contact(paths, args.output)
            print(json.dumps({"contact_sheet": str(args.output.resolve()), "pages": len(paths), "note": "overview only; inspect changed/critical original pages in detail"}))
        return 0
    except (OSError, ValueError, subprocess.SubprocessError) as exc: print(str(exc)); return 2


if __name__ == "__main__": raise SystemExit(main())
