# Cash Flow Early Warning System – Backend

FastAPI backend for the AI-based Cash Flow Early Warning System.

---

## Tech Stack

| Layer | Technology |
|---|---|
| API Framework | FastAPI 0.115 |
| Auth & Database | Supabase (PostgreSQL + RLS) |
| Data Processing | Pandas 2.2, NumPy 2.1 |
| Machine Learning | scikit-learn (Random Forest) |
| Model Storage | Joblib |
| Runtime | Python 3.11+ / Uvicorn |

---

## Project Structure

```
backend/
├── app/
│   ├── main.py               # FastAPI app + CORS + router registration
│   ├── config.py             # Pydantic Settings (env vars)
│   ├── supabase_client.py    # Anon, admin, and per-user Supabase clients
│   │
│   ├── routes/
│   │   ├── health.py         # GET /health
│   │   ├── datasets.py       # CRUD for uploaded datasets
│   │   ├── preprocessing.py  # Preprocessing pipeline management
│   │   ├── model.py          # Model training management (ML phase)
│   │   └── predictions.py    # Batch & single predictions (ML phase)
│   │
│   ├── services/
│   │   ├── dataset_service.py
│   │   ├── preprocessing_service.py
│   │   ├── feature_engineering_service.py  # (ML phase stub)
│   │   ├── training_service.py             # (ML phase stub)
│   │   └── prediction_service.py           # (ML phase stub)
│   │
│   ├── schemas/
│   │   ├── dataset.py        # DatasetMeta, PreprocessingResult, etc.
│   │   ├── prediction.py     # PredictionRequest / PredictionResult
│   │   └── model.py          # ModelInfo, TrainingStatus, ModelMetrics
│   │
│   └── utils/
│       └── __init__.py       # Shared helpers (utc_now, etc.)
│
├── ml_models/                # .joblib model files (git-ignored)
├── requirements.txt
├── .env.example
└── README.md
```

---

## Quick Start

### 1. Create a virtual environment

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure environment variables

```bash
cp .env.example .env
# Edit .env with your Supabase credentials
```

### 4. Run the development server

```bash
# From the backend/ directory
uvicorn app.main:app --reload --port 8000
```

The API will be available at **http://localhost:8000**.  
Interactive docs: **http://localhost:8000/docs**

---

## Environment Variables

| Variable | Description |
|---|---|
| `SUPABASE_URL` | Your Supabase project URL |
| `SUPABASE_ANON_KEY` | Public anon key (RLS enforced) |
| `SUPABASE_SERVICE_ROLE_KEY` | Service-role key (RLS bypassed – keep secret!) |
| `CORS_ORIGINS` | Comma-separated list of allowed frontend origins |
| `ML_MODELS_DIR` | Directory for persisted `.joblib` model files |

---

## API Endpoints

### Health

| Method | Path | Description |
|---|---|---|
| GET | `/health` | Application status check |

### Datasets

| Method | Path | Description |
|---|---|---|
| POST | `/api/datasets/upload` | Upload CSV / XLSX file |
| GET | `/api/datasets` | List datasets for current user |
| GET | `/api/datasets/{id}` | Get dataset metadata |
| DELETE | `/api/datasets/{id}` | Delete a dataset |

### Preprocessing

| Method | Path | Description |
|---|---|---|
| POST | `/api/preprocessing/run/{dataset_id}` | Start preprocessing |
| GET | `/api/preprocessing/status/{job_id}` | Check job status |
| GET | `/api/preprocessing/result/{dataset_id}` | Get result summary |

### Model *(ML phase – returns 501)*

| Method | Path | Description |
|---|---|---|
| POST | `/api/model/train/{dataset_id}` | Train Random Forest model |
| GET | `/api/model/status/{job_id}` | Training job status |
| GET | `/api/model/info` | List trained models |
| DELETE | `/api/model/{model_id}` | Delete a model |

### Predictions *(ML phase – returns 501)*

| Method | Path | Description |
|---|---|---|
| POST | `/api/predictions/predict` | Batch predictions |
| POST | `/api/predictions/predict-single` | Single invoice prediction |
| GET | `/api/predictions/history` | Prediction history |
| GET | `/api/predictions/{id}` | Specific prediction result |

---

## Authentication

All endpoints (except `/health`) require a Supabase JWT in the `Authorization` header:

```
Authorization: Bearer <supabase-access-token>
```

Row Level Security on all Supabase tables ensures users can only access their own data.

---

## Supabase Tables Required

Create these tables in your Supabase project:

```sql
-- Datasets
create table datasets (
  id uuid primary key default gen_random_uuid(),
  user_id uuid references auth.users(id) default auth.uid(),
  filename text not null,
  original_filename text not null,
  file_size_bytes integer not null,
  row_count integer,
  column_count integer,
  storage_path text not null,
  status text not null default 'uploaded',
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);
alter table datasets enable row level security;
create policy "Users see own datasets"
  on datasets for all using (auth.uid() = user_id);

-- Preprocessing jobs
create table preprocessing_jobs (
  id uuid primary key default gen_random_uuid(),
  dataset_id uuid references datasets(id) on delete cascade,
  user_id uuid references auth.users(id) default auth.uid(),
  status text not null default 'pending',
  message text,
  started_at timestamptz,
  completed_at timestamptz
);
alter table preprocessing_jobs enable row level security;
create policy "Users see own jobs"
  on preprocessing_jobs for all using (auth.uid() = user_id);
```

---

## Development Phases

- **Phase 1 (current):** Core API structure, Supabase integration, dataset CRUD, preprocessing pipeline skeleton.
- **Phase 2 (ML):** Feature engineering, Random Forest training, Joblib persistence, batch/single predictions, SHAP explanations.
