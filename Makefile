SHELL := /bin/bash

PYTHON ?= python3
VENV := backend/venv
VENV_PY := $(VENV)/bin/python
VENV_PIP := $(VENV)/bin/pip
UVICORN := $(VENV)/bin/uvicorn

.DEFAULT_GOAL := help
.PHONY: help env setup check-env seed calibrate-derived api web dev test

help:
	@printf '\nBaccarat Vector Match - available commands\n\n'
	@printf '  make setup             建立 .env、Python venv、安裝前後端依賴\n'
	@printf '  make check-env         檢查 Atlas 與 Voyage 設定\n'
	@printf '  make seed              使用 Voyage 重新產生並寫入預設 patterns (大路 + 下三路)\n'
	@printf '  make calibrate-derived 校準下三路第二組 vector search 的 DERIVED_PATTERN_MIN_SCORE\n'
	@printf '  make api               啟動 FastAPI 後端\n'
	@printf '  make web               啟動 Vite 前端\n'
	@printf '  make dev               同時啟動前後端\n'
	@printf '  make test              執行後端測試與前端 build 檢查\n\n'

env:
	@if [ ! -f .env ]; then \
		cp .env.example .env; \
		printf '已建立 .env，請填入 Atlas 與 Voyage 設定。\n'; \
	else \
		printf '.env 已存在，保留目前設定。\n'; \
	fi

setup: env
	$(PYTHON) -m venv $(VENV)
	$(VENV_PY) -m pip install -r backend/requirements.txt
	cd frontend && npm ci

check-env:
	@test -f .env || { printf '找不到 .env，請先執行 make setup。\n'; exit 1; }
	@cd backend && ../$(VENV_PY) -c 'from app.config import get_settings; s = get_settings(); assert s.mongo_uri.startswith("mongodb+srv://"), "MONGO_URI 請設定為 Atlas mongodb+srv URI"; assert s.voyage_api_key and s.voyage_api_key != "your_voyage_api_key_here", "請設定 VOYAGE_API_KEY"; assert not s.use_mock_embedder, "使用真實 Voyage 時請設定 USE_MOCK_EMBEDDER=false"; print("Atlas 與 Voyage 設定檢查通過。")'

seed: check-env
	cd backend && ../$(VENV_PY) -m app.seed.run_seed

calibrate-derived: check-env
	cd backend && ../$(VENV_PY) -m app.seed.calibrate_derived

api:
	@test -x $(UVICORN) || { printf '尚未安裝後端依賴，請先執行 make setup。\n'; exit 1; }
	cd backend && ../$(UVICORN) app.main:app --reload --port 8000

web:
	@test -d frontend/node_modules || { printf '尚未安裝前端依賴，請先執行 make setup。\n'; exit 1; }
	cd frontend && npm run dev -- --host 0.0.0.0

dev: check-env
	$(MAKE) -j2 api web

test:
	cd backend && ../$(VENV_PY) -m pytest tests/ -v
	cd frontend && npm run build
