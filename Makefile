.PHONY: help build up down logs migrate shell test

help:  ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

build:  ## Build Docker images
	docker compose build

up:  ## Start all services (app + db) in detached mode
	docker compose up -d

down:  ## Stop and remove containers
	docker compose down

logs:  ## Follow application logs
	docker compose logs -f app

migrate:  ## Run Alembic migrations inside the app container
	docker compose exec app alembic upgrade head

migrate-create:  ## Create a new migration (usage: make migrate-create MSG="add column")
	docker compose exec app alembic revision --autogenerate -m "$(MSG)"

shell:  ## Open a Python shell inside the app container
	docker compose exec app python

dev:  ## Run locally (requires .env and running postgres)
	uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload --loop asyncio

dev-migrate:  ## Run Alembic migrations locally
	alembic upgrade head

install:  ## Install dependencies locally
	pip install -r requirements.txt

test:  ## Run the full pipeline test suite
	python3 test_bot_full.py

bot:  ## Run the Telegram bot in polling mode (local dev)
	python3 run_bot_polling.py

register:  ## Create test user (run once)
	python3 -c "\
import asyncio, os; os.chdir('$(shell pwd)'); \
from app.core.config import get_settings; get_settings.cache_clear(); \
from app.services.auth import register_user; \
from app.schemas.auth import UserCreate; \
from app.core.db import get_session_factory; \
async def run(): \
    async with get_session_factory()() as db: \
        user = await register_user(UserCreate(email='test@financebot.uz', password='secret123', full_name='Test User', company_name='Test Kompaniya'), db); \
        await db.commit(); print('Created:', user.email); \
asyncio.run(run())"

lint:  ## Run ruff linter
	ruff check app/ --fix

format:  ## Run black formatter
	black app/ test_bot_full.py run_bot_polling.py
