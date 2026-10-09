#!/usr/bin/env python3
"""
compress_pdf.py: Fast raster-based PDF compression for handwritten tablet notes.
Converts oversized vector PDFs (100-350 MB) into lean, crisp files (15-25 MB)
that preview instantly in Google Drive and mobile viewers without lag.
"""

import os
import sys
import argparse
import tempfile
import subprocess
from pathlib import Path
from PIL import Image

def compress_pdf(input_file: Path, output_file: Path, dpi: int = 150, quality: int = 82):
    if not input_file.exists():
        print(f"error: input file not found: {input_file}", file=sys.stderr)
        sys.exit(1)

    orig_size_mb = input_file.stat().st_size / (1024 * 1024)
    print(f"compressing {input_file.name} ({orig_size_mb:.1f} MB) at {dpi} DPI...")

    with tempfile.TemporaryDirectory() as tmp_dir:
        # Step 1: Render pages using poppler pdftoppm
        ppm_cmd = [
            "pdftoppm", "-jpeg",
            "-r", str(dpi),
            str(input_file),
            os.path.join(tmp_dir, "page")
        ]
        res = subprocess.run(ppm_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if res.returncode != 0:
            print(f"error: pdftoppm failed: {res.stderr.decode('utf-8', errors='ignore')}", file=sys.stderr)
            sys.exit(1)

        jpg_files = sorted([os.path.join(tmp_dir, f) for f in os.listdir(tmp_dir) if f.endswith(".jpg")])
        if not jpg_files:
            print("error: no pages extracted", file=sys.stderr)
            sys.exit(1)

        print(f"rendered {len(jpg_files)} pages. packing into clean PDF...")

        # Step 2: Assemble lean PDF via Pillow
        images = [Image.open(f).convert("RGB") for f in jpg_files]
        images[0].save(
            str(output_file),
            save_all=True,
            append_images=images[1:],
            quality=quality,
            optimize=True
        )

        for img in images:
            img.close()

    new_size_mb = output_file.stat().st_size / (1024 * 1024)
    savings = (1 - (new_size_mb / orig_size_mb)) * 100
    print(f"done: {orig_size_mb:.1f} MB -> {new_size_mb:.1f} MB (saved {savings:.1f}%)")

def main():
    parser = argparse.ArgumentParser(description="compress tablet handwritten notes for instant cloud preview")
    parser.add_argument("input", type=Path, help="path to bloated input PDF")
    parser.add_argument("-o", "--output", type=Path, help="path for compressed output PDF (default: <name>_compressed.pdf)")
    parser.add_argument("--dpi", type=int, default=150, help="raster rendering DPI (default: 150)")
    parser.add_argument("--quality", type=int, default=82, help="jpeg compression quality 1-100 (default: 82)")
    args = parser.parse_args()

    out = args.output or args.input.with_stem(f"{args.input.stem}_compressed")
    compress_pdf(args.input, out, dpi=args.dpi, quality=args.quality)

if __name__ == "__main__":
    main()
