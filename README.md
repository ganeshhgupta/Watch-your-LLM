# Watch your LLM

> Full visibility into every LLM call. Trace prompts, responses, tokens, latency, and cost — self-hosted, no vendor lock-in.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Your Application                         │
│                                                                 │
│   @trace(model="gemini-1.5-flash")                              │
│   def my_fn(prompt):                                            │
│       return llm.generate(prompt)   ◄── SDK wraps this         │
└──────────────────────┬──────────────────────────────────────────┘
                       │  HTTP POST /v1/traces (async, background)
                       ▼
┌──────────────────────────────────────┐
│         FastAPI Collector API        │  ← Deployed on Render
│  POST /v1/traces   (ingest)          │
│  GET  /v1/traces   (list + filter)   │
│  GET  /v1/stats/*  (aggregates)      │
└──────────────────────┬───────────────┘
                       │  asyncpg
                       ▼
┌──────────────────────────────────────┐
│           NeonDB (PostgreSQL)        │  ← Serverless Postgres
│  traces table: id, trace_id,         │
│  timestamp, model, tokens, cost,     │
│  latency_ms, error_class, tags…      │
└──────────────────────────────────────┘

┌──────────────────────────────────────┐
│    React Dashboard (Vercel)          │  ← Deployed on Vercel
│  /          → Landing page           │
│  /app        → Overview              │
│  /app/traces → Trace Explorer        │
│  /app/errors → Error Analysis        │
└──────────────────────────────────────┘
```

---

## Quick Start (local)

### 1. Prerequisites
- Python 3.11+
- Node.js 18+
- A [NeonDB](https://neon.tech) database (free tier)
- A [Gemini API key](https://aistudio.google.com) (free)

### 2. Set up environment variables

```bash
# API
cp api/.env.example api/.env
# Edit api/.env — paste your NeonDB DATABASE_URL

# Dashboard
cp dashboard/.env.example dashboard/.env
# VITE_API_URL=http://localhost:8000 (default, no change needed locally)

# Root (for test script)
cp .env.example .env
# Edit .env — paste your GEMINI_API_KEY
```

### 3. Start the API

```bash
cd api
pip install -r requirements.txt
uvicorn main:app --reload
# → http://localhost:8000
```

### 4. Start the dashboard

```bash
cd dashboard
npm install
npm run dev
# → http://localhost:5173
```

### 5. Install the SDK and run the test script

```bash
pip install -e sdk/
pip install google-generativeai python-dotenv

python test_live.py
# Makes real Gemini API calls and traces them to the dashboard
```

Open **http://localhost:5173** and explore your traces.

---

## SDK Usage

### Decorator

```python
from llmobs import trace
import google.generativeai as genai

genai.configure(api_key="...")
model = genai.GenerativeModel("gemini-1.5-flash")

@trace(model="gemini-1.5-flash", tags={"env": "prod", "feature": "summarizer"})
def summarize(text: str):
    # Return the full response object — SDK extracts tokens automatically
    return model.generate_content(f"Summarize: {text}")

result = summarize("Your text here...")
print(result.text)
```

### Context manager span

```python
import llmobs

with llmobs.span(model="gemini-1.5-flash", tags={"step": "rerank"}) as span:
    span.set_input("What is observability?")
    response = model.generate_content("What is observability?")
    span.set_output(response)
```

### What gets captured automatically

| Field | Source |
|---|---|
| `trace_id` | UUID generated per call |
| `timestamp` | UTC ISO 8601 |
| `function_name` | Decorated function name |
| `model` | Decorator arg or auto-detected from response |
| `input_preview` | First string arg or `prompt` kwarg (≤2000 chars) |
| `output_preview` | `response.text` / `.choices[0].message.content` (≤2000 chars) |
| `prompt_tokens` | `response.usage_metadata.prompt_token_count` |
| `completion_tokens` | `response.usage_metadata.candidates_token_count` |
| `latency_ms` | Wall-clock integer |
| `cost_usd` | Computed from static pricing table |
| `error_class` | Exception class name (if raised) |
| `tags` | Dict from decorator kwarg |

---

## Supported Models & Pricing

| Model | Input (/ 1M tokens) | Output (/ 1M tokens) |
|---|---|---|
| `gpt-4o` | $5.00 | $15.00 |
| `gpt-4o-mini` | $0.15 | $0.60 |
| `claude-3-5-sonnet` | $3.00 | $15.00 |
| `gemini-1.5-pro` | $1.25 | $5.00 |
| `gemini-1.5-flash` | $0.075 | $0.30 |
| `gemini-1.5-flash-8b` | $0.0375 | $0.15 |
| `gemini-2.0-flash` | $0.10 | $0.40 |

---

## Cloud Deployment

### API → Render

1. Push repo to GitHub
2. Create a new **Web Service** on [Render](https://render.com)
3. Connect your repo — Render auto-detects `render.yaml`
4. Set environment variables in Render dashboard:
   - `DATABASE_URL` → NeonDB connection string
   - `ALLOWED_ORIGINS` → your Vercel app URL

### Dashboard → Vercel

1. Import your GitHub repo on [Vercel](https://vercel.com)
2. Set **Root Directory** to `dashboard`
3. Add environment variable:
   - `VITE_API_URL` → your Render API URL (e.g. `https://watchyourllm-api.onrender.com`)
4. Deploy

### SDK → point at Render

```bash
export LLMOBS_COLLECTOR_URL=https://watchyourllm-api.onrender.com
```

---

## Dashboard Pages

**Landing** (`/`) — Clean hero page with feature overview and code snippet.

**Overview** (`/app`) — 4 stat cards (Total Traces, Error Rate, Avg Latency, Total Cost) + cost/traces area chart (last 7 days, hourly) + model breakdown table. Auto-refreshes every 30 s.

**Trace Explorer** (`/app/traces`) — Filterable table by model, tag (`key:value`), date range, errors-only. Click any row for a full slide-in detail drawer showing input/output, all metadata, and error stack.

**Error Analysis** (`/app/errors`) — Horizontal bar chart of top error types + recent errors table with input preview. Click a row for full trace detail.

---

## Extension Ideas

- **Alerting webhooks** — POST to Slack/PagerDuty when error rate spikes above threshold
- **Team sharing** — Add auth (Clerk/Auth.js) and per-project API keys
- **A/B prompt comparison** — Tag two prompt variants, compare cost and quality side-by-side
- **Hallucination scoring** — Attach an evaluation LLM call to score factual accuracy
- **Budget guardrails** — Hard-stop or alert when daily cost exceeds a configured limit
- **Streaming support** — Capture token-by-token streaming calls with time-to-first-token metric
