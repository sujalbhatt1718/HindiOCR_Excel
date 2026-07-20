# HindiOCRExcel

Convert images and PDF documents containing **tabular data** into editable,
formatted **Excel (.xlsx)** files — with first-class support for **Hindi**,
**English**, **Devanagari & ASCII numerals** and **mixed-language** documents.

Built with **FastAPI + PaddleOCR + OpenCV**. No Tesseract.

---

## Features

- **Upload** JPG / JPEG / PNG / PDF (drag & drop, browse, preview, progress bar,
  size & type validation).
- **PaddleOCR** engine — auto-downloads models, auto CPU fallback, angle/
  orientation classification, confidence scores. Hindi + English + numerals.
- **Preprocessing pipeline** (OpenCV): resize, grayscale, denoise, Gaussian &
  median blur, CLAHE, adaptive threshold, morphology, sharpening, border &
  shadow removal, perspective correction, deskew.
- **Table detection** — detects horizontal/vertical lines, builds a cell grid
  and OCRs each cell individually; falls back to geometric layout clustering for
  line-less tables. Preserves blank cells and structure.
- **Multi-page PDF** — every page rendered, processed and merged in order.
- **Editable spreadsheet** — edit any cell, add/delete rows & columns, copy/
  paste (multi-cell), search, clear, undo/redo.
- **Excel export** — Unicode-safe, numeric coercion (ASCII only, Hindi numerals
  preserved), bold header, borders, wrapping, centre alignment, auto column
  width, frozen first row.
- **Production-ready** — typed, modular services, Pydantic models, Loguru
  logging, robust error handling, CORS, temp-file cleanup, Docker, tests.

## Tech stack

| Layer     | Technology                                             |
|-----------|--------------------------------------------------------|
| Backend   | Python 3.11, FastAPI, Uvicorn, Loguru, python-dotenv   |
| OCR / CV  | PaddleOCR, OpenCV, NumPy, Pillow                        |
| PDF       | PyMuPDF (fitz)                                          |
| Excel     | Pandas, OpenPyXL                                        |
| Frontend  | HTML5, CSS3, Bootstrap 5, Vanilla JS                    |

---

## Project structure

```
HindiOCRExcel/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI app, routes, static, error handlers
│   │   ├── config.py            # Pydantic settings (.env)
│   │   ├── dependencies.py      # DI providers
│   │   ├── api/                 # upload, process, export, health, files
│   │   ├── services/            # preprocessing, ocr, pdf, table, excel, document
│   │   ├── models/schemas.py    # Pydantic request/response models
│   │   └── utils/               # logger, helpers, exceptions
│   ├── uploads/  temp/  logs/   # runtime data (gitignored)
├── frontend/
│   ├── index.html  workspace.html  about.html  404.html
│   ├── css/style.css
│   └── js/  (theme, api, upload, table, export, app)
├── tests/                       # pytest suite
├── requirements.txt  requirements-dev.txt
├── Dockerfile  docker-compose.yml  docker-compose.dev.yml
├── pyproject.toml  .env.example
└── README.md
```

---

## Installation (local)

Requires **Python 3.11+**. On Debian/Ubuntu install the OpenCV/PDF system libs:

```bash
sudo apt-get update && sudo apt-get install -y \
  libgl1 libglib2.0-0 libgomp1 poppler-utils fonts-lohit-deva
```

Then:

```bash
git clone <your-repo-url> HindiOCRExcel
cd HindiOCRExcel

python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env              # optional: customise settings

cd backend
uvicorn app.main:app --reload
```

Open <http://localhost:8000>. Interactive API docs at
<http://localhost:8000/docs>.

> The first request downloads PaddleOCR models (~15 MB) and may take a minute.
> Models are cached in `~/.paddleocr` afterwards.

### Serving the frontend

The frontend is served automatically by FastAPI (`StaticFiles` + page routes),
so no separate server is needed. To run it independently, host the `frontend/`
directory on any static server and point the JS `BASE` (`frontend/js/api.js`) at
your API origin.

---

## Docker

Production:

```bash
docker compose up --build
# -> http://localhost:8000
```

Development (live reload, source mounted, debug logs):

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build
```

OCR models are cached in the `ocr_models` named volume so they persist across
restarts.

---

## API

Base path: `/api`. Full interactive schema at `/docs` and `/redoc`.

### `POST /api/upload`
Multipart form upload (`file`). Returns:
```json
{ "file_id": "…", "filename": "table.png", "kind": "image",
  "size_bytes": 22223, "pages": 1 }
```

### `POST /api/process`
```json
{ "file_id": "…", "lang": "hi" }
```
Returns the extracted table, per-page results, confidence and timing:
```json
{ "file_id": "…", "table": [["क्रम","नाम"],["1","राम"]],
  "n_rows": 2, "n_cols": 2, "confidence": 0.86,
  "processing_time": 0.65, "pages": [ … ] }
```

### `POST /api/export`
```json
{ "table": [["क्रम","नाम"],["1","राम"]],
  "filename": "export", "sheet_name": "Sheet1", "header": true }
```
Returns a streamed `.xlsx` attachment.

### `GET /api/health`
```json
{ "status": "ok", "version": "1.0.0",
  "ocr_loaded": true, "gpu_available": false }
```

### Preview helpers
- `GET /api/file/{file_id}` — original image (or PDF first page as PNG).
- `GET /api/preview/{file_id}/{page}` — a specific PDF page as PNG.

Errors return a consistent envelope: `{ "error": "code", "detail": "message" }`.

---

## Configuration

All settings are environment variables (see `.env.example`). Highlights:

| Variable              | Default | Description                              |
|-----------------------|---------|------------------------------------------|
| `OCR_LANG`            | `hi`    | PaddleOCR recognition language           |
| `OCR_USE_GPU`         | `false` | Use GPU if a CUDA paddle build is present |
| `MAX_UPLOAD_SIZE_MB`  | `25`    | Upload size limit                        |
| `PDF_RENDER_DPI`      | `200`   | PDF-to-image render DPI                   |
| `MAX_PDF_PAGES`       | `30`    | Max PDF pages processed                  |
| `FILE_RETENTION_MINUTES` | `120`| Age at which temp/upload files are purged |
| `CORS_ORIGINS`        | `["*"]` | Allowed CORS origins (JSON array)        |

---

## Testing

```bash
pip install -r requirements-dev.txt
pytest                       # unit + API tests (OCR mocked)
RUN_OCR_TESTS=1 pytest       # also runs the real PaddleOCR pipeline test
ruff check backend tests     # lint
mypy                         # type check
```

---

## Deployment

The app is a standard ASGI application (`app.main:app`). Deploy on **Render**,
**Railway**, **AWS**, **Azure** or any Linux host:

- **Docker**: use the provided `Dockerfile` (exposes `8000`, has a healthcheck).
- **Bare metal**: install the system libs above, `pip install -r requirements.txt`,
  then run behind a process manager:
  ```bash
  uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 2
  ```
- Put it behind Nginx/Caddy for TLS. Persist `~/.paddleocr` to avoid
  re-downloading models on every deploy.

Render/Railway: set the start command to
`cd backend && uvicorn app.main:app --host 0.0.0.0 --port $PORT`.

---

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| `ImportError: libGL.so.1` | Install `libgl1 libglib2.0-0` (see Installation). |
| First request very slow / hangs | Models are downloading; check network and `~/.paddleocr`. |
| `ocr_model_load_failed` | Network blocked model download — pre-download models or mount them. |
| Hindi text renders as boxes in the UI | Install a Devanagari font (`fonts-lohit-deva`) / use a modern browser. |
| Poor accuracy | Use a higher-resolution scan, ensure the table is upright and well-lit. |
| PDF fails to render | Ensure `poppler-utils` is installed; confirm the PDF isn't encrypted. |
| Out-of-memory on large PDFs | Lower `PDF_RENDER_DPI` or `MAX_PDF_PAGES`. |

---

## License

MIT — see `LICENSE`.
