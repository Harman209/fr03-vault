#!/usr/bin/env python3
"""
sync_vault.py: Automated archival and sync engine for Aakash FR03.
- Mirrors Physics and Chemistry teacher folders server-side (zero network egress).
- Detects oversized Maths notes (>30 MB) and raster-compresses them at 150 DPI
  so Google Drive previews them natively on web and mobile.
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
PHYSICS_SRC = f"{REMOTE}FR03 (2026-27)"
CHEM_SRC = f"{REMOTE}FR-03"
MATHS_SRC = f"{REMOTE}FR03 Maths Notes 2026-28"

PHYSICS_DEST = f"{REMOTE}vault/notes/physics"
CHEM_DEST = f"{REMOTE}vault/notes/chemistry"
MATHS_DEST = f"{REMOTE}vault/notes/maths"

SIZE_THRESHOLD_BYTES = 30 * 1024 * 1024  # 30 MB

def run_cmd(cmd, check=True):
    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if check and res.returncode != 0:
        print(f"[vault] error: {res.stderr.strip()}", file=sys.stderr)
        res.check_returncode()
    return res

def sync_server_side(src, dest, label):
    print(f"[vault] syncing {label} (server-side)...")
    cmd = [
        "rclone", "copy", src, dest,
        "--drive-shared-with-me",
        "--drive-server-side-across-configs",
        "-q"
    ]
    res = run_cmd(cmd, check=False)
    if res.returncode == 0:
        print(f"[vault] {label}: sync complete.")
    else:
        print(f"[vault] {label}: sync warning: {res.stderr.strip()}", file=sys.stderr)

def get_remote_files(remote_path, shared_with_me=False):
    cmd = ["rclone", "lsjson", remote_path]
    if shared_with_me:
        cmd.append("--drive-shared-with-me")
    res = run_cmd(cmd, check=False)
    if res.returncode != 0:
        return []
    try:
        return json.loads(res.stdout)
    except Exception:
        return []

def compress_pdf(input_path, output_path, dpi=150, quality=82):
    with tempfile.TemporaryDirectory() as tmp_dir:
        ppm_cmd = ["pdftoppm", "-jpeg", "-r", str(dpi), str(input_path), os.path.join(tmp_dir, "page")]
        res = subprocess.run(ppm_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if res.returncode != 0:
            raise RuntimeError(f"pdftoppm failed: {res.stderr.decode('utf-8', errors='ignore')}")

        jpg_files = sorted([os.path.join(tmp_dir, f) for f in os.listdir(tmp_dir) if f.endswith(".jpg")])
        if not jpg_files:
            raise RuntimeError("no pages extracted from PDF")

        images = [Image.open(f).convert("RGB") for f in jpg_files]
        images[0].save(str(output_path), save_all=True, append_images=images[1:], quality=quality, optimize=True)
        for img in images:
            img.close()

def sync_maths():
    print("[vault] checking maths notes...")
    src_items = get_remote_files(MATHS_SRC, shared_with_me=True)
    dest_items = get_remote_files(MATHS_DEST)
    dest_map = {item["Name"]: item for item in dest_items}

    for item in src_items:
        name = item["Name"]
        is_dir = item.get("IsDir", False)
        size = item.get("Size", 0)

        if is_dir:
            sync_server_side(f"{MATHS_SRC}/{name}", f"{MATHS_DEST}/{name}", f"maths/{name}")
            continue

        if not name.lower().endswith(".pdf"):
            continue

        dest_file = dest_map.get(name)

        # Small files: copy server-side directly
        if size < SIZE_THRESHOLD_BYTES:
            if not dest_file:
                print(f"[vault] maths: copying {name} ({size // (1024*1024)} MB) server-side...")
                cmd = [
                    "rclone", "copyto", f"{MATHS_SRC}/{name}", f"{MATHS_DEST}/{name}",
                    "--drive-shared-with-me", "--drive-server-side-across-configs", "-q"
                ]
                run_cmd(cmd, check=False)
            continue

        # Large files (> 30 MB): needs compression
        if dest_file:
            dest_size = dest_file.get("Size", 0)
            if dest_size < size * 0.7:
                continue

        print(f"[vault] maths: compressing {name} ({size / (1024*1024):.1f} MB)...")
        with tempfile.TemporaryDirectory() as work_dir:
            local_raw = Path(work_dir) / "raw.pdf"
            local_compressed = Path(work_dir) / "compressed.pdf"

            # Download raw
            dl_cmd = ["rclone", "copyto", f"{MATHS_SRC}/{name}", str(local_raw), "--drive-shared-with-me", "-q"]
            run_cmd(dl_cmd)

            # Compress at 150 DPI
            compress_pdf(local_raw, local_compressed, dpi=150, quality=82)
            compressed_mb = local_compressed.stat().st_size / (1024 * 1024)
            print(f"[vault] maths: {name} compressed to {compressed_mb:.1f} MB. uploading...")

            # Upload
            ul_cmd = ["rclone", "copyto", str(local_compressed), f"{MATHS_DEST}/{name}", "-q"]
            run_cmd(ul_cmd)
            print(f"[vault] maths: {name} uploaded.")

    print("[vault] maths: sync complete.")

def main():
    parser = argparse.ArgumentParser(description="Aakash FR03 Vault Synchronizer")
    parser.add_argument("--subject", choices=["physics", "chemistry", "maths", "all"], default="all")
    args = parser.parse_args()

    if args.subject in ("all", "physics"):
        sync_server_side(PHYSICS_SRC, PHYSICS_DEST, "physics")
    if args.subject in ("all", "chemistry"):
        sync_server_side(CHEM_SRC, CHEM_DEST, "chemistry")
    if args.subject in ("all", "maths"):
        sync_maths()

    print("[vault] all tasks finished successfully.")

if __name__ == "__main__":
    main()
