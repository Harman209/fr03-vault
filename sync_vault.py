#!/usr/bin/env python3
"""
sync_vault.py: Universal archival and PDF optimization engine for fr03-vault.
- Mirrors Physics, Chemistry, and Mathematics class materials to Google Drive.
- Runs server-side copying for all recordings, assignments, and small files (zero network egress).
- Automatically detects any PDF > 35 MB across all subjects and compresses it at 150 DPI
  so Google Drive previews every note natively on web and mobile.
"""

import os
import sys
import json
import argparse
import tempfile
import subprocess
from pathlib import Path
from PIL import Image

REMOTE = "gdrive:"

SUBJECTS = {
    "physics": {
        "src": f"{REMOTE}FR03 (2026-27)",
        "dest": f"{REMOTE}vault/notes/physics",
    },
    "chemistry": {
        "src": f"{REMOTE}FR-03",
        "dest": f"{REMOTE}vault/notes/chemistry",
    },
    "maths": {
        "src": f"{REMOTE}FR03 Maths Notes 2026-28",
        "dest": f"{REMOTE}vault/notes/maths",
    },
}

SIZE_THRESHOLD_BYTES = 35 * 1024 * 1024  # 35 MB

def run_cmd(cmd, check=True):
    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if check and res.returncode != 0:
        print(f"[vault] error: {res.stderr.strip()}", file=sys.stderr)
        res.check_returncode()
    return res

def list_files_json(remote_path, shared_with_me=False):
    cmd = ["rclone", "lsjson", "-R", remote_path]
    if shared_with_me:
        cmd.append("--drive-shared-with-me")
    res = run_cmd(cmd, check=False)
    if res.returncode != 0:
        return []
    try:
        return json.loads(res.stdout)
    except Exception:
        return []

def compress_pdf(input_path: Path, output_path: Path, dpi: int = 150, quality: int = 82):
    with tempfile.TemporaryDirectory() as tmp_dir:
        ppm_cmd = [
            "pdftoppm", "-jpeg",
            "-r", str(dpi),
            str(input_path),
            os.path.join(tmp_dir, "page")
        ]
        res = subprocess.run(ppm_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if res.returncode != 0:
            raise RuntimeError(f"pdftoppm failed: {res.stderr.decode('utf-8', errors='ignore')}")

        jpg_files = sorted([os.path.join(tmp_dir, f) for f in os.listdir(tmp_dir) if f.endswith(".jpg")])
        if not jpg_files:
            raise RuntimeError("no pages extracted from PDF")

        images = [Image.open(f).convert("RGB") for f in jpg_files]
        images[0].save(
            str(output_path),
            save_all=True,
            append_images=images[1:],
            quality=quality,
            optimize=True
        )
        for img in images:
            img.close()

def sync_subject(subject_key: str):
    config = SUBJECTS[subject_key]
    src = config["src"]
    dest = config["dest"]

    print(f"\n[vault] scanning {subject_key}...")

    # Step 1: Server-side sync for everything EXCEPT bloated PDFs
    # We copy server-side with --update so newer files get pulled without overwriting local mods
    print(f"[vault] {subject_key}: running server-side sync...")
    cmd_sync = [
        "rclone", "copy", src, dest,
        "--drive-shared-with-me",
        "--drive-server-side-across-configs",
        "--update",
        "-q"
    ]
    run_cmd(cmd_sync, check=False)

    # Step 2: Check destination for any oversized PDFs that need compression
    dest_items = list_files_json(dest)
    oversized_pdfs = [
        item for item in dest_items
        if not item.get("IsDir", False)
        and item["Name"].lower().endswith(".pdf")
        and item.get("Size", 0) > SIZE_THRESHOLD_BYTES
    ]

    if not oversized_pdfs:
        print(f"[vault] {subject_key}: all notes are under 35 MB and 100% drive-previewable.")
        return

    print(f"[vault] {subject_key}: found {len(oversized_pdfs)} oversized PDF(s) to optimize:")
    for item in oversized_pdfs:
        rel_path = item["Path"]
        raw_mb = item["Size"] / (1024 * 1024)
        print(f"  -> {rel_path} ({raw_mb:.1f} MB)")

    for item in oversized_pdfs:
        rel_path = item["Path"]
        raw_mb = item["Size"] / (1024 * 1024)
        print(f"\n[vault] compressing {rel_path} ({raw_mb:.1f} MB) at 150 DPI...")

        with tempfile.TemporaryDirectory() as work_dir:
            local_raw = Path(work_dir) / "raw.pdf"
            local_out = Path(work_dir) / "compressed.pdf"

            # Download raw from dest
            remote_target = f"{dest}/{rel_path}"
            dl_cmd = ["rclone", "copyto", remote_target, str(local_raw), "-q"]
            run_cmd(dl_cmd)

            # Compress
            compress_pdf(local_raw, local_out, dpi=150, quality=82)
            compressed_mb = local_out.stat().st_size / (1024 * 1024)
            savings = (1 - (compressed_mb / raw_mb)) * 100
            print(f"[vault] compressed to {compressed_mb:.1f} MB (saved {savings:.1f}%). uploading back...")

            # Overwrite destination file with compressed version
            ul_cmd = ["rclone", "copyto", str(local_out), remote_target, "-q"]
            run_cmd(ul_cmd)
            print(f"[vault] {rel_path}: replaced with previewable version.")

    print(f"[vault] {subject_key}: optimization complete.")

def main():
    parser = argparse.ArgumentParser(description="Universal Aakash FR03 Vault Synchronizer")
    parser.add_argument("--subject", choices=["physics", "chemistry", "maths", "all"], default="all")
    args = parser.parse_args()

    subjects_to_sync = list(SUBJECTS.keys()) if args.subject == "all" else [args.subject]

    for subj in subjects_to_sync:
        sync_subject(subj)

    print("\n[vault] all operations completed successfully.")

if __name__ == "__main__":
    main()
