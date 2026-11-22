# Label Tracker — Product Label Detection & Expiry Tracking System

> Built with IBM Bob · IBM Bobathon

A full-stack web application that reads product labels using OCR, extracts manufacturing and expiry dates, flags ambiguous dates for human review, stores everything in SQLite, and displays a live expiry dashboard.

---

## Architecture

```
label-tracker/
├── backend/              # Python · FastAPI · SQLite
│   ├── app/
│   │   ├── main.py           ← FastAPI app + all API endpoints
│   │   ├── database.py       ← SQLAlchemy models + SQLite setup
│   │   ├── schemas.py        ← Pydantic request/response models
│   │   ├── ocr_service.py    ← EasyOCR (+ PIL fallback)
│   │   ├── date_extractor.py ← Date parsing + ambiguity detection
│   │   └── expiry.py         ← Expiry status helper
│   └── requirements.txt
└── frontend/             # React · Vite · TypeScript · Tailwind CSS
    └── src/
        ├── pages/
        │   ├── ScanPage.tsx        ← Upload + OCR + review form
        │   ├── LabelsPage.tsx      ← Filterable label list
        │   ├── LabelDetailPage.tsx ← Edit / confirm individual record
        │   └── DashboardPage.tsx   ← Stats + expiry bar chart
        ├── components/
        │   ├── Sidebar.tsx
        │   ├── LabelTable.tsx
        │   └── StatusBadge.tsx
        ├── api.ts   ← All API calls (axios)
        └── types.ts ← Shared TypeScript interfaces
```

---

## Database Schema

| Field               | Type    | Purpose                                  |
|---------------------|---------|------------------------------------------|
| id                  | integer | Primary key                              |
| product_name        | text    | Extracted or confirmed product name      |
| batch_number        | text    | Batch / lot number                       |
| manufacturing_date  | text    | ISO date YYYY-MM-DD (or empty)           |
| expiry_date         | text    | ISO date YYYY-MM-DD or YYYY-MM (or empty)|
| date_type           | text    | expiry · use-by · best-before · unknown  |
| label_image         | text    | Relative path to uploaded image          |
| raw_text            | text    | Full OCR output                          |
| review_status       | text    | confirmed · needs_review                 |
| ambiguity_notes     | text    | JSON array of ambiguity warning strings  |
| created_at          | datetime| When the label was scanned               |

---

## How It Works

1. **Upload** — drag-and-drop or click to upload a product label image (JPEG/PNG/WebP, ≤ 10 MB).
2. **OCR** — EasyOCR processes the image (falls back to PIL if unavailable). No data is saved yet.
3. **Extract** — the date extractor parses MFG / EXP / BEST BEFORE / USE BY lines and pulls out ISO dates.
4. **Ambiguity flag** — dates like `03/04/26` where day and month are both plausible are flagged with a warning and the record is marked `needs_review`.
5. **Review** — the user sees the extracted fields in an editable form. They correct any ambiguous or missing dates using native date pickers.
6. **Confirm** — clicking **Confirm & Save** persists the record with `review_status = confirmed`. Clicking **Save — Needs Review** saves it for later.
7. **Dashboard** — shows totals for expired, expiring soon (≤ 30 days), valid, and needs-review labels with a bar chart.

---

## Setup — Backend

### Prerequisites
- Python 3.10+ (Miniforge / conda recommended on Apple Silicon)
- pip

### Install

```bash
cd label-tracker/backend
pip3 install -r requirements.txt
```

### Install Tesseract OCR binary (required for text extraction)

**Option A — conda-forge (recommended, works on macOS 14 without Xcode CLT):**
```bash
conda install -c conda-forge tesseract -y
```

**Option B — Homebrew (requires up-to-date Command Line Tools):**
```bash
brew install tesseract
```

After installing, the backend auto-detects the tesseract binary — no extra config needed.

> **EasyOCR note:** EasyOCR is installed by `requirements.txt` but is automatically
> disabled on conda/miniforge environments (macOS ARM64) due to a known OpenMP
> conflict with PyTorch that causes a segfault. Tesseract is used instead.
> To force EasyOCR on a venv without conda: `unset SKIP_EASYOCR` before starting.

### Run

```bash
cd label-tracker/backend
uvicorn app.main:app --reload --port 8000
```

API docs: http://localhost:8000/docs

> **Port already in use?** Run: `lsof -ti :8000 | xargs kill -9`

---

## Setup — Frontend

### Prerequisites
- Node.js 18+

### Install & run

```bash
cd label-tracker/frontend
npm install
npm run dev
```

App: http://localhost:5173

The Vite dev server proxies `/api` and `/uploads` to the backend at `http://localhost:8000`.

---

## API Endpoints

| Method | Path                    | Description                                    |
|--------|-------------------------|------------------------------------------------|
| POST   | `/api/scan`             | Upload image → OCR → extracted fields (not saved) |
| POST   | `/api/labels`           | Save a label record (form-encoded)             |
| GET    | `/api/labels`           | List all records (optional `?status_filter=`)  |
| GET    | `/api/labels/{id}`      | Single record                                  |
| PUT    | `/api/labels/{id}`      | Update / confirm a record (JSON body)          |
| DELETE | `/api/labels/{id}`      | Delete a record                                |
| GET    | `/api/dashboard`        | Aggregate stats                                |
| GET    | `/uploads/{path}`       | Serve uploaded label images                    |

### Example — scan a label

```bash
curl -X POST http://localhost:8000/api/scan \
  -F "file=@biscuit_packet.jpg"
```

**Response:**
```json
{
  "product_name": "Digestive Biscuits Classic 400g",
  "batch_number": "BATCH-2024-001",
  "manufacturing_date": "2024-03-15",
  "expiry_date": "2025-03-14",
  "date_type": "best-before",
  "raw_text": "...",
  "ambiguity_notes": [],
  "label_image": "uploads/abc123_biscuit_packet.jpg"
}
```

### Example — ambiguous date

Scanning a label with `Best Before: 03/04/26` returns:
```json
{
  "expiry_date": "2026-04-03",
  "ambiguity_notes": ["Short date 3/4/26 is ambiguous (DD/MM or MM/DD?)"],
  ...
}
```
The frontend shows a yellow warning and keeps the record as `needs_review` until the user confirms.

### Example — save confirmed label

```bash
curl -X POST http://localhost:8000/api/labels \
  -F "product_name=Digestive Biscuits Classic 400g" \
  -F "batch_number=BATCH-2024-001" \
  -F "manufacturing_date=2024-03-15" \
  -F "expiry_date=2025-03-14" \
  -F "date_type=best-before" \
  -F "review_status=confirmed"
```

---

## Supported Date Formats

| Format            | Example           | Notes                        |
|-------------------|-------------------|------------------------------|
| ISO               | `2025-03-14`      | Unambiguous                  |
| DD/MM/YYYY        | `14/03/2025`      | Ambiguous if day ≤ 12        |
| DD/MM/YY          | `14/03/25`        | Ambiguous if day ≤ 12        |
| DD Mon YYYY       | `14 Mar 2025`     | Unambiguous                  |
| Mon YYYY          | `Mar 2025`        | Month-precision              |
| MM/YYYY           | `03/2025`         | Unambiguous                  |
| MonYY             | `Mar25`           | Unambiguous                  |

---

## Expiry Status Logic

| Status         | Condition                              |
|----------------|----------------------------------------|
| `expired`      | Expiry date is before today            |
| `expiring_soon`| Expiry date is within 30 days          |
| `ok`           | Expiry date is more than 30 days away  |
| `unknown`      | Expiry date is missing or unparseable  |

---

## Production Build

```bash
cd label-tracker/frontend
npm run build
# Serve dist/ from FastAPI or any static host
```

---

## Repository

https://github.com/jasdiq/AMRAK_AI_IBMBOB
