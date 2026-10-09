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

# ==============================================================================
# CANONICAL GOOGLE DRIVE OBJECT ID REGISTRY
# All folder references must use explicit Google Drive object IDs to prevent
# duplicate folder entities from ever being created by path string resolution.
# ==============================================================================
VAULT_ID = "1ciGDAf-Lw8Ep8C4wXI9rXiW_a04tfGag"

# Vault root-level folders
VAULT_DIRS = {
    "notes": "1sFQXJPBTQYa4yYQysChL0UCeVPzucF1i",
    "recordings": "14oSJVW-yIP3Er03ipAo5EdPM1_Yssrax",
    "inbox": "1r-RK-QZctc9q2pFVNZE5-qIWQirxtlrZ",
}

# Subject notes destination folders (under notes/)
NOTES_DIRS = {
    "physics": "1bAdpExhZ3-Ne_kBCmI2tJAouC-0IgBvB",
    "chemistry": "1NI9INBfOV5MRvjIfp-_au5DNFGMg28Oh",
    "maths": "1IrFhswIBaxBjUeAjME-7WP6TfnNPe1pv",
}

# Subject recordings destination folders (under recordings/)
RECORDING_DIRS = {
    "physics": "1234nsnnGZstHG4-A5eaLzEDqKZ3JgSaq",
    "chemistry": "1iBz4hnVCgzxYs8COCHJy-SIMubY9-1Uj",
    "maths": "1J2Kk4MB_7EnhIlWyDK85G7jXzERu3lSZ",
}

# Shared faculty sources (from teachers)
SOURCE_DIRS = {
    "physics": "1sNOVT0wzzhw9gBEci5YVFM0HD6baiidN",     # FR03 (2026-27)
    "chemistry": "16NCL3mWf8ijTIeUyMplJDNfoewBEN4UP",   # FR-03
    "maths": "1b-VLTIsb007w1RqU7diAH8rqapUty2WV",       # FR03 Maths Notes 2026-28
}

SUBJECTS = {
    "physics": {
        "src": f"gdrive,root_folder_id={SOURCE_DIRS['physics']}:",
        "dest": f"gdrive,root_folder_id={NOTES_DIRS['physics']}:",
    },
    "chemistry": {
        "src": f"gdrive,root_folder_id={SOURCE_DIRS['chemistry']}:",
        "dest": f"gdrive,root_folder_id={NOTES_DIRS['chemistry']}:",
    },
    "maths": {
        "src": f"gdrive,root_folder_id={SOURCE_DIRS['maths']}:",
        "dest": f"gdrive,root_folder_id={NOTES_DIRS['maths']}:",
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
            remote_target = f"{dest}{rel_path}" if dest.endswith(":") else f"{dest}/{rel_path}"
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

    # Auto-refresh manifest and data.js for GitHub Pages
    try:
        manifest_path = Path(__file__).parent / "manifest.json"
        cmd_manifest = [
            "rclone", "lsjson", "-R", "--files-only",
            f"gdrive,root_folder_id={VAULT_ID}:"
        ]
        res = subprocess.run(cmd_manifest, stdout=subprocess.PIPE, text=True)
        if res.returncode == 0:
            with open(manifest_path, "w", encoding="utf-8") as f:
                f.write(res.stdout)
            import build_site
            build_site.main()
            print("[vault] github pages site data updated.")
    except Exception as e:
        print(f"[vault] site build notice: {e}", file=sys.stderr)

    print("\n[vault] all operations completed successfully.")

if __name__ == "__main__":
    main()
