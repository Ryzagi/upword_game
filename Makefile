.PHONY: dev backend frontend install install-backend install-frontend test test-backend test-frontend lint lint-backend lint-frontend format clean help

PYTHON ?= python3
NPM ?= npm

help:
	@echo "Targets:"
	@echo "  make dev        Run backend (:8000) and frontend (:5173) concurrently."
	@echo "  make install    Install backend and frontend dependencies."
	@echo "  make test       Run all tests."
	@echo "  make lint       Run linters."
	@echo "  make format     Auto-format code."
	@echo "  make clean      Remove .venv and node_modules."

# Run both servers. Ctrl-C tears them down together.
dev: install
	@echo "→ backend on http://localhost:8000   frontend on http://localhost:5173"
	@trap 'kill 0' INT TERM; \
		( $(MAKE) -s backend ) & \
		( $(MAKE) -s frontend ) & \
		wait

backend: install-backend
	cd backend && .venv/bin/uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

frontend: install-frontend
	cd frontend && $(NPM) run dev

install: install-backend install-frontend

install-backend: backend/.venv/.installed

backend/.venv/.installed: backend/pyproject.toml
	cd backend && $(PYTHON) -m venv .venv
	cd backend && .venv/bin/pip install --upgrade pip
	cd backend && .venv/bin/pip install -e ".[dev]"
	@touch backend/.venv/.installed

install-frontend: frontend/node_modules/.installed

frontend/node_modules/.installed: frontend/package.json
	cd frontend && $(NPM) install
	@mkdir -p frontend/node_modules
	@touch frontend/node_modules/.installed

test: test-backend test-frontend

test-backend: install-backend
	cd backend && .venv/bin/pytest -q

test-frontend: install-frontend
	cd frontend && $(NPM) test -- --run

lint: lint-backend lint-frontend

lint-backend: install-backend
	cd backend && .venv/bin/ruff check .
	cd backend && .venv/bin/ruff format --check .

lint-frontend: install-frontend
	cd frontend && $(NPM) run lint
	cd frontend && $(NPM) run typecheck

format: install-backend install-frontend
	cd backend && .venv/bin/ruff check --fix .
	cd backend && .venv/bin/ruff format .
	cd frontend && $(NPM) run format

clean:
	rm -rf backend/.venv backend/.pytest_cache backend/.ruff_cache backend/.mypy_cache
	rm -rf frontend/node_modules frontend/dist
