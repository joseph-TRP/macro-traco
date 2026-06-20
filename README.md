# Macro Traco 🥩

A cloud-only, mobile-first grocery logger that ranks foods by **$ / 30g protein** —
how cheaply each food delivers 30 grams of protein. The Google Sheet is the live
database; the app reads and writes it directly. No local storage.

- **Backend:** FastAPI + gspread (Google Sheets API)
- **Frontend:** vanilla HTML/CSS/JS, responsive (two tabs: New Entry + Dashboard)
- **Hosting:** Render
- **Database:** [Google Sheet](https://docs.google.com/spreadsheets/d/1ARYg5u5gVMbL1jeIotTJGcrWuZ1n4oRHgxBYVIyP2OQ/edit)

## How it works

| Column | Source | Formula |
|--------|--------|---------|
| `$ / 30g protein` | computed | `Price × ServingSize × 30 / (Size × Protein)` |
| `Calories / 30g` | computed | `Calories × 30 / Protein` |
| `Serving size / 30g` | computed | `ServingSize × 30 / Protein` |
| `Rank` | computed | `RANK($/30g, all, ascending)` |

New rows are appended with the four computed columns written as **live Sheet
formulas**, so the spreadsheet stays self-computing.

## Setup

### 1. Google service account (one-time)
The app authenticates to Google as a service account.

1. In Google Cloud, use (or create) a service account and download its JSON key.
   This project already has one: `jn-python@pragmatic-port-341721.iam.gserviceaccount.com`.
2. Enable the **Google Sheets API** and **Google Drive API** on that project.
3. **Share the Sheet and the Drive folder with the service account email as Editor.**

### 2. Local dev
```bash
python -m venv .venv && . .venv/Scripts/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                                # fill in values
# put the service account key at ./service_account.json  (gitignored)
uvicorn app.main:app --reload
```
Open http://localhost:8000

### 3. Deploy to Render
- Connect this repo; Render reads `render.yaml`.
- Set the secret env vars: `GOOGLE_SERVICE_ACCOUNT_JSON` (paste the key JSON),
  `WORKSHEET_NAME`, and optionally `DEPLOY_NOTE`.

## Version counter
A `version.txt` file in the Drive folder holds `vX.Y.Z | note`. On each deploy
(`BUMP_VERSION_ON_START=true`) the patch number ticks up. Shown in grey at the
bottom of the app. Purely cosmetic.

## Environment variables
See [`.env.example`](.env.example).
