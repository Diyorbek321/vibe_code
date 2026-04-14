# FinanceBot — AI-powered Finance Tracker

> Telegram orqali moliyaviy hisobotlarni ovoz va matn yordamida yuritish platformasi.  
> An AI-powered finance management platform — log income & expenses via Telegram voice/text, track everything on a real-time web dashboard.

---

## What it does

- **Telegram bot** — send a voice message or text like _"bugun 500,000 so'm savdo tushdi"_ and the bot extracts the amount, category, and date automatically using an LLM (Groq).
- **Receipt OCR** — send a photo of a receipt; the bot reads and records it automatically.
- **Real-time dashboard** — every transaction syncs to the web dashboard instantly via Server-Sent Events (no polling).
- **Analytics** — income vs. expense charts, category breakdowns, budget alerts.
- **Scheduled reports** — automatic daily / weekly / monthly summaries sent to your Telegram.
- **CSV & Excel export** — download your transactions with one click, filtered by date range and type.

---

## Tech stack

| Layer | Technology |
|---|---|
| Backend API | FastAPI 0.115, SQLAlchemy 2.0 async, Alembic, asyncpg |
| AI / NLP | Groq API (llama-3.3-70b-versatile) |
| Voice-to-text | Groq Whisper (whisper-large-v3) |
| Receipt OCR | Groq Vision (llama-4-scout-17b-16e-instruct) |
| Telegram bot | aiogram 3.x, FSM, inline keyboards |
| Frontend | React 18, Vite, TanStack Query, Zustand, Tailwind CSS |
| Database | PostgreSQL 16 |
| Real-time | Server-Sent Events (SSE) |
| Auth | JWT HS256 |
| Exports | CSV (built-in), Excel via openpyxl |

---

## Prerequisites

- Python 3.11+
- Node.js 18+
- PostgreSQL 16 (or Docker)
- [Groq API key](https://console.groq.com) — free tier is sufficient
- A Telegram bot token from [@BotFather](https://t.me/BotFather)

---

## Quick start — local development

### 1. Clone and configure

```bash
git clone <repo-url>
cd vibe_code_task
```

Copy the example env file and fill in your values:

```bash
cp .env.example .env
```

Edit `.env`:

```env
# Database
DB_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/financebot
DB_URL_SYNC=postgresql://postgres:postgres@localhost:5432/financebot

# Security — generate with: python3 -c "import secrets; print(secrets.token_hex(32))"
SECRET_KEY=your_32_char_secret_here

# Telegram
BOT_TOKEN=your_bot_token_from_botfather
WEBHOOK_URL=http://localhost:8000   # not used in dev (polling mode)

# Groq (replaces OpenAI)
OPENAI_API_KEY=your_groq_api_key
OPENAI_BASE_URL=https://api.groq.com/openai/v1
OPENAI_MODEL=llama-3.3-70b-versatile
WHISPER_MODEL=whisper-large-v3

# Environment
APP_ENV=development
```

### 2. Start PostgreSQL

Using Docker (easiest):

```bash
docker run -d \
  --name financebot-db \
  -e POSTGRES_USER=postgres \
  -e POSTGRES_PASSWORD=postgres \
  -e POSTGRES_DB=financebot \
  -p 5432:5432 \
  postgres:16-alpine
```

Or use your existing local PostgreSQL — just create the database:

```bash
createdb financebot
```

### 3. Backend setup

```bash
# Install dependencies
pip install -r requirements.txt

# Run database migrations
alembic upgrade head

# Start the API server
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload --loop asyncio
```

API is now running at `http://localhost:8000`.  
Interactive API docs: `http://localhost:8000/docs`

### 4. Telegram bot (polling mode)

Open a second terminal:

```bash
python3 run_bot_polling.py
```

The bot connects via long-polling — no public URL needed for local testing.

### 5. Frontend

Open a third terminal:

```bash
cd "finance(1)"
npm install
npm run dev
```

Dashboard is now at `http://localhost:5173`.

### 6. Create your first account

Either register through the web dashboard (`http://localhost:5173`) or send `/start` to the bot and follow the 4-step registration flow.

---

## Docker deployment (production)

```bash
# 1. Fill in .env (set APP_ENV=production and a real WEBHOOK_URL)
cp .env.example .env && nano .env

# 2. Build and start
docker compose up -d

# 3. Run migrations
docker compose exec app alembic upgrade head
```

The API runs on port `8000`. Put nginx or Caddy in front to:
- Terminate TLS
- Proxy `/api` → `localhost:8000`
- Serve the built frontend from `finance(1)/dist`

Build the frontend for production:

```bash
cd "finance(1)" && npm run build
```

---

## Makefile shortcuts

```bash
make dev          # Run API server with hot reload
make bot          # Run Telegram bot in polling mode
make migrate      # Run DB migrations (Docker)
make dev-migrate  # Run DB migrations (local)
make test         # Run the full pipeline test suite
make logs         # Follow Docker container logs
make help         # Show all commands
```

---

## Environment variables reference

| Variable | Required | Description |
|---|---|---|
| `DB_URL` | ✅ | Async PostgreSQL DSN (`postgresql+asyncpg://...`) |
| `DB_URL_SYNC` | ✅ | Sync DSN for Alembic migrations |
| `SECRET_KEY` | ✅ | JWT signing key, min 32 chars |
| `BOT_TOKEN` | ✅ | Telegram bot token from @BotFather |
| `WEBHOOK_URL` | ✅ | Public base URL (production only) |
| `OPENAI_API_KEY` | ✅ | Groq API key (or OpenAI) |
| `OPENAI_BASE_URL` | — | Set to `https://api.groq.com/openai/v1` for Groq |
| `OPENAI_MODEL` | — | Default: `gpt-4o-mini` |
| `WHISPER_MODEL` | — | STT model name, e.g. `whisper-large-v3` |
| `APP_ENV` | — | `development` or `production` (default: `production`) |
| `FRONTEND_URLS` | — | Comma-separated CORS origins |
| `REDIS_URL` | — | Redis DSN for persistent FSM state (optional, falls back to memory) |

---

## Bot commands

| Command | Description |
|---|---|
| `/start` | Register or view status |
| `/link` | Connect existing web account to Telegram |
| `/balance` | Current month balance |
| `/report` | Full current month report |
| `/help` | Show all commands |

**Natural language examples:**
- `"Bugun 500,000 so'm savdo tushdi"` → income, Savdo category
- `"Kecha 120,000 so'm kommunal to'lov"` → expense, Kommunal category
- `"Bu hafta qancha xarajat bo'ldi?"` → analytics query

**Media:**
- 🎤 Voice message → auto-transcribed then processed
- 🧾 Receipt photo → OCR extracts amount, category, date

---

## Project structure

```
vibe_code_task/
├── app/
│   ├── bot/            # Telegram bot (handlers, FSM, keyboards, OCR)
│   ├── core/           # Config, DB, auth dependencies, lifespan
│   ├── models/         # SQLAlchemy ORM models
│   ├── routers/        # FastAPI route handlers
│   ├── schemas/        # Pydantic request/response schemas
│   └── services/       # Business logic (NLP, STT, OCR, scheduler)
├── alembic/            # Database migrations
├── finance(1)/         # React frontend (Vite + Tailwind)
├── docker-compose.yml
├── Dockerfile
├── run_bot_polling.py  # Local dev bot runner
└── requirements.txt
```

---

## Design decisions

### What language does the bot respond in?

The bot responds exclusively in **Uzbek**. This is a deliberate, hard constraint — not a localisation option. The target user is a small business owner in Uzbekistan who sends voice messages in Uzbek; switching the interface language to English or Russian would break the natural feel of the product. Every confirmation message, error prompt, category label, and scheduled report is written in Uzbek. The LLM is also instructed in its system prompt to return category names and clarification questions in Uzbek, so even AI-generated text stays in the same language.

One practical side effect: `WHISPER_LANGUAGE=uz` is set by default in the config, which improves transcription accuracy for Uzbek speech rather than relying on auto-detection.

---

### What default categories make sense for a small Uzbek business?

Eight categories ship out of the box:

| Category | Uzbek | Typical use |
|---|---|---|
| Savdo | Sales | Daily revenue from goods sold |
| Logistika | Logistics | Delivery, transport, fuel |
| Ijara | Rent | Office, warehouse, shop space |
| Maosh | Payroll | Staff salaries and daily wages |
| Kommunal | Utilities | Electricity, water, internet |
| Marketing | Marketing | Advertising, promotion, SMM |
| Soliq | Tax | VAT, income tax, local levies |
| Boshqa | Other | Catch-all for everything else |

These eight cover roughly 90% of transactions for a typical Tashkent retail or wholesale business. They were chosen to match what a bookkeeper would write in a physical ledger, not accounting chart-of-accounts terminology. Users can create additional custom categories through the web dashboard. The LLM maps free-form input (e.g. _"reklama uchun 200,000 so'm"_) to the closest category name automatically.

---

### How do you handle currency?

**Everything is stored as UZS (Uzbek som) integers** — no multi-currency support, no conversion layer. This is intentional:

- The database `amount` column is `NUMERIC(18, 2)` — enough precision for UZS amounts up to 999 trillion, with two decimal places kept for completeness even though som amounts are always round.
- The LLM extraction prompt explicitly says _"faqat raqam, UZS da"_ (numbers only, in UZS), so the model does not invent exchange rates.
- The frontend formats amounts with `Intl.NumberFormat('uz-UZ', { currency: 'UZS' })`, which produces the correct Uzbek grouping style: `1 500 000 UZS`.
- The bot displays amounts as `1,500,000 so'm` (comma-grouped, with the word "so'm") because that is how Uzbek speakers write it in everyday text.

If a user types a dollar or euro amount, the LLM currently treats it as UZS. A future version would detect the currency symbol and ask for clarification before saving.

---

### How does the dashboard feel on first open — before any data exists?

The dashboard does not show empty charts or zeroed-out stat cards that feel broken. Instead:

- The three stat cards (Sof foyda, Daromad, Xarajat) render with `0 UZS` and no percentage badge — the badge only appears when there is a previous month to compare against, so a new user sees clean zeros rather than `+∞%` or `NaN%`.
- The recent-transactions panel shows an **EmptyState** component with the message _"Hali ma'lumot yo'q — Telegram botga yozing yoki shu yerdan qo'shing"_ and a direct "Yangi qo'shish" button. The message points the user immediately toward the two ways to enter data.
- The Analytics page is intentionally left empty on first load — no placeholder charts, no skeleton bars. An empty chart with fake axes looks like a bug; no chart at all with a clear call-to-action is honest.

The overall first-open experience is: stat cards with zeros, one actionable empty state, and a clear path to either open the bot or add a transaction from the web.

---

### What is your one extra feature, and why did you choose it?

**Receipt photo OCR** — send a photo of a cash register receipt or bank transfer screenshot and the bot automatically reads the amount, date, and category without any typing.

I chose this because it directly eliminates the biggest remaining friction point. After adding voice input, the next most common reason not to log a transaction is _"I have the receipt right here, I just don't want to type the number."_ With OCR the user takes a photo they were going to take anyway (for their own records) and the transaction is logged.

The implementation uses Groq's vision model (`llama-4-scout-17b-16e-instruct`) via the same OpenAI-compatible endpoint already in use for LLM and STT — no new API key, no new dependency except openpyxl (which was added for Excel export). The model returns a structured JSON with amount, type, category, date, description, and a confidence score. The bot shows a confidence indicator (🟢 high / 🟡 medium / 🔴 low) so the user knows whether to double-check before confirming. The same confirm/cancel flow used for text and voice entry applies here — nothing is saved without explicit user approval.

---

## Product brief

FinanceBot is built for small business owners in Uzbekistan who track income and expenses manually in notebooks or spreadsheets. It lets them log transactions by simply talking to a Telegram bot in Uzbek — no forms, no apps to learn. The platform solves the friction of real-time bookkeeping by making data entry as easy as sending a voice message. Version 2 would add multi-user company accounts with role-based access (accountant vs. owner views), integration with Uzbek payment systems (Payme, Click), and automated tax-period summaries formatted for local reporting requirements.

## What I'd add with 3 more days

With three more days I would focus on three things: first, a proper onboarding funnel — the current registration works but the web dashboard's first-use experience doesn't guide the user through creating categories and making their first transaction, so I'd add an interactive onboarding wizard. Second, I'd implement inline editing in the transactions table — the PATCH endpoint is already built but the UI only has delete; adding an edit modal would make the dashboard production-ready. Third, I'd add a budget planner page where owners set monthly spending limits per category and the system sends Telegram alerts when they're close to the limit — the budget model and alert logic already exist in the backend, they just need a proper UI surface.
