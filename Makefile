PYTHON ?= python3
export PYTHONPATH := $(CURDIR)
export DATABASE_URL ?= postgresql://dexmart:dexmart@localhost:5432/warehouse

.PHONY: setup db wait-db pipeline test test-unit sql reset doctor

setup:
	$(PYTHON) -m pip install -r requirements.txt

db:
	docker compose up -d postgres

wait-db:
	$(PYTHON) scripts/wait_for_db.py

pipeline: ## extract → transform → load
	$(PYTHON) -m pipeline

test:
	$(PYTHON) -m pytest -q

test-unit:
	$(PYTHON) -m pytest -q -m "not integration"

sql:
	docker compose exec postgres psql -U dexmart -d warehouse

status:
	docker compose exec -T postgres psql -U dexmart -d warehouse -f /dev/stdin < sql/status.sql

reset:
	docker compose down -v
	rm -rf data/staging

doctor:
	@command -v $(PYTHON) >/dev/null && $(PYTHON) --version || echo "python missing"
	@command -v docker >/dev/null && docker --version || echo "docker missing (needed for Postgres)"
	@docker compose version >/dev/null 2>&1 && docker compose version || echo "docker compose missing"
	@$(PYTHON) -c "import pandas, psycopg2, pytest; print('python deps ok')" 2>/dev/null || echo "run: make setup"
	@$(PYTHON) scripts/wait_for_db.py --once >/dev/null 2>&1 && echo "postgres reachable" || echo "postgres not reachable — run: docker compose up -d"
