# fr03-vault

automated synchronization and document optimization engine for academic class materials and handwritten tablet notes.

mirrors shared google drive resources server-side, crushes bloated vector lecture notes to enable instant in-browser preview, and maintains an organized cloud archive.

---

## architecture

```text
[coaching shared folders]
├── FR03 (2026-27)              (physics)
├── FR-03                       (chemistry)
└── FR03 Maths Notes 2026-28    (mathematics: bloated vector exports)
           │
           ▼
[fr03-vault engine]
├── physics / chemistry  -> server-side mirror (zero network egress)
└── oversized pdfs (>35MB)-> raster compression pipeline (150 dpi, ~90% reduction)
           │
           ▼
[personal drive archive: vault/] (pinned by root_folder_id)
├── notes/
│   ├── physics/         (all 11 chapters previewable without downloading)
│   ├── chemistry/       (100% drive-previewable)
│   └── maths/           (crushed vector strokes, sharp retina zoom)
├── recordings/          (master obs and teacher video library)
└── inbox/               (staged intake from contribution forms)
```

---

## the pdf preview problem

whiteboard and tablet note applications (such as goodnotes or quartz pdf on ipad) export handwritten notes as uncompressed vector stroke collections. a single 2-hour mathematics or physics lecture frequently reaches 100 to 320 mb.

google drive refuses to preview files over 50 mb, throwing errors and forcing students to download hundreds of megabytes on mobile networks just to reference a formula.

`fr03-vault` renders vector paths to clean 150 dpi raster frames and repacks them into optimized documents.

### real-world benchmarks

| chapter / file | raw teacher size | optimized size | reduction |
| :--- | :--- | :--- | :--- |
| **System of Particles & Rotational** | 180.4 mb | **15.5 mb** | -91.4% |
| **Motion in a Plane** | 175.4 mb | **15.9 mb** | -91.0% |
| **Straight Lines (Maths)** | 151.7 mb | **17.8 mb** | -88.2% |
| **Laws of Motion** | 139.4 mb | **11.6 mb** | -91.7% |
| **Work, Energy and Power** | 135.6 mb | **10.9 mb** | -92.0% |
| **Motion in a Straight Line** | 106.8 mb | **10.5 mb** | -90.1% |
| **Gravitation** | 77.7 mb | **6.0 mb** | -92.2% |
| **Units and Measurements** | 57.9 mb | **4.8 mb** | -91.7% |
| **Basic Mathematics** | 56.8 mb | **5.4 mb** | -90.4% |
| **Solids** | 40.4 mb | **3.1 mb** | -92.3% |
| **Total Physics Archive** | **1,048.9 mb** | **88.1 mb** | **-91.6%** |

handwritten stylus text remains crisp under 2x zoom on ipad retina screens while loading instantly in google drive.

---

## preventing google drive duplicate folders

in google drive, directory names are not unique paths; they are objects with IDs. running multiple sync or creation commands using string paths (e.g. `notes/maths`) causes google drive to spawn duplicate folder entities with the exact same name.

`fr03-vault` pins canonical google drive object IDs across the entire hierarchy:

```python
# root archive
VAULT_ID = "1ciGDAf-Lw8Ep8C4wXI9rXiW_a04tfGag"

# notes destinations
NOTES_DIRS = {
    "physics":   "1bAdpExhZ3-Ne_kBCmI2tJAouC-0IgBvB",
    "chemistry": "1NI9INBfOV5MRvjIfp-_au5DNFGMg28Oh",
    "maths":     "1IrFhswIBaxBjUeAjME-7WP6TfnNPe1pv",
}

# recordings destinations
RECORDING_DIRS = {
    "physics":   "1234nsnnGZstHG4-A5eaLzEDqKZ3JgSaq",
    "chemistry": "1iBz4hnVCgzxYs8COCHJy-SIMubY9-1Uj",
    "maths":     "1J2Kk4MB_7EnhIlWyDK85G7jXzERu3lSZ",
}

# coaching faculty sources
SOURCE_DIRS = {
    "physics":   "1sNOVT0wzzhw9gBEci5YVFM0HD6baiidN",     # FR03 (2026-27)
    "chemistry": "16NCL3mWf8ijTIeUyMplJDNfoewBEN4UP",     # FR-03
    "maths":     "1b-VLTIsb007w1RqU7diAH8rqapUty2WV",     # FR03 Maths Notes 2026-28
}
```

every rclone operation connects directly to `gdrive,root_folder_id=<ID>:`. this bypasses name resolution completely and instructs the google drive api to operate directly inside the target object, making folder duplicates impossible.

---

## requirements

- **python:** 3.10+
- **system dependencies:**
  - `rclone` (configured with remote named `gdrive:`)
  - `pdftoppm` (`poppler-utils`)
- **python packages:**
  ```bash
  pip install -r requirements.txt
  ```

---

## usage

### automated vault sync

mirrors class materials, auto-detects any pdf exceeding 35 mb across all subjects, compresses it at 150 dpi, and updates the drive:

```bash
python3 sync_vault.py
```

sync a specific subject:

```bash
python3 sync_vault.py --subject physics
python3 sync_vault.py --subject maths
python3 sync_vault.py --subject chemistry
```

### standalone pdf compression

compress any bloated note file on demand:

```bash
python3 compress_pdf.py lecture.pdf
```

options:

```bash
python3 compress_pdf.py lecture.pdf -o output.pdf --dpi 150 --quality 82
```

---

## automation (nightly sync)

### option a: systemd user timer (recommended for linux)

template unit files are provided in `systemd/`:

```bash
# install units to user directory
mkdir -p ~/.config/systemd/user
cp systemd/fr03-vault.service ~/.config/systemd/user/
cp systemd/fr03-vault.timer ~/.config/systemd/user/

# reload and enable timer
systemctl --user daemon-reload
systemctl --user enable --now fr03-vault.timer
```

check status anytime:

```bash
systemctl --user list-timers fr03-vault.timer
journalctl --user -u fr03-vault.service -n 50
```

### option b: cron job

append a cron job to trigger at 23:30 daily:

```bash
30 23 * * * /usr/bin/python3 /path/to/fr03-vault/sync_vault.py >> /path/to/fr03-vault/sync.log 2>&1
```

---

## license

mit
