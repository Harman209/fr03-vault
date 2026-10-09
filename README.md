# fr03-vault

automated synchronization and document optimization engine for academic class materials and handwritten tablet notes.

mirrors shared google drive resources server-side, compresses bloated vector lecture notes to enable instant in-browser preview, and maintains an organized cloud archive.

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
└── mathematics          -> raster compression pipeline (150 dpi, ~85% reduction)
           │
           ▼
[personal drive archive: vault/]
├── notes/
│   ├── physics/
│   ├── chemistry/
│   └── maths/           (previewable in browser / mobile without downloading)
├── recordings/          (master video library)
└── inbox/               (staged intake from contribution forms)
```

---

## the pdf preview problem

whiteboard and tablet note applications (such as goodnotes or quartz pdf on ipad) export handwritten notes as uncompressed vector stroke collections. a single 2-hour mathematics lecture frequently reaches 150 to 320 mb.

google drive refuses to preview files over 50 mb, forcing students to download hundreds of megabytes on mobile networks just to reference a formula.

`fr03-vault` renders vector paths to clean 150 dpi raster frames and repacks them into optimized documents:
- **before:** 152 mb (preview fails, forced download)
- **after:** 24 mb (sharp algebraic subscripts, instant preview on web and mobile)

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

mirrors physics and chemistry server-side, detects oversized mathematics notes, compresses them, and uploads:

```bash
python3 sync_vault.py
```

sync a specific subject:

```bash
python3 sync_vault.py --subject physics
python3 sync_vault.py --subject maths
```

### standalone pdf compression

compress any bloated note file on demand:

```bash
python3 compress_pdf.py lecture.pdf
```

options:

```bash
python3 compress_pdf.py lecture.pdf -o output.pdf --dpi 150 --quality 85
```

---

## automation (nightly cron)

to keep the archive synchronized automatically, append a cron job to run at 23:30 daily:

```bash
30 23 * * * /usr/bin/python3 /path/to/fr03-vault/sync_vault.py >> /path/to/fr03-vault/sync.log 2>&1
```

---

## license

mit
