.PHONY: help up down build logs pipeline-run pipeline-dry-run test-pipeline test-api \
        db-init db-shell minio-setup reset clean

## ──────────────────────────────────────────────────────────
## RootL Atlas — Makefile de desenvolvimento
## ──────────────────────────────────────────────────────────

help:  ## Exibe este menu
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
	  awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-22s\033[0m %s\n", $$1, $$2}'

# ─── Infraestrutura ──────────────────────────────────────────────────────────

up: ## Sobe todos os serviços (PostGIS, MinIO, API, Frontend, Prefect)
	docker compose up -d --build
	@echo ""
	@echo "  ----- RootL Atlas iniciado:"
	@echo "  Frontend: http://localhost:5173"
	@echo "  API:      http://localhost:8000/docs"
	@echo "  MinIO:    http://localhost:9001 (atlas_admin / atlas_minio_admin_password)"
	@echo "  Prefect:  http://localhost:4200"

down: ## Para todos os serviços
	docker compose down

build: ## Reconstrói as imagens sem cache
	docker compose build --no-cache

logs: ## Exibe logs de todos os serviços (Ctrl+C para sair)
	docker compose logs -f

logs-api: ## Logs apenas da API
	docker compose logs -f api

logs-pipeline: ## Logs apenas do pipeline
	docker compose logs -f pipeline

# ─── Banco de Dados ──────────────────────────────────────────────────────────

db-init: ## Executa scripts de inicialização do banco (init.sql + indexes.sql)
	docker compose exec postgis psql -U atlas -d rootl_atlas -f /docker-entrypoint-initdb.d/init.sql
	docker compose exec postgis psql -U atlas -d rootl_atlas -f /docker-entrypoint-initdb.d/indexes.sql

db-shell: ## Abre um shell psql no banco
	docker compose exec postgis psql -U atlas -d rootl_atlas

db-stats: ## Exibe contagem de registros nas tabelas principais
	docker compose exec postgis psql -U atlas -d rootl_atlas -c "\
		SELECT \
		  'setores_censitarios' AS tabela, COUNT(*) FROM atlas.setores_censitarios \
		UNION ALL \
		  SELECT 'escolas', COUNT(*) FROM atlas.escolas \
		UNION ALL \
		  SELECT 'municipios_mt', COUNT(*) FROM atlas.municipios_mt \
		UNION ALL \
		  SELECT 'acessibilidade_educacional', COUNT(*) FROM atlas.acessibilidade_educacional; \
	"

# ─── MinIO / Lakehouse ────────────────────────────────────────────────────────

minio-setup: ## Cria buckets no MinIO e configura política pública
	docker compose exec minio mc alias set local http://localhost:9000 atlas_admin atlas_minio_admin_password
	docker compose exec minio mc mb --ignore-existing local/rootl-atlas-bronze
	docker compose exec minio mc mb --ignore-existing local/rootl-atlas-silver
	docker compose exec minio mc mb --ignore-existing local/rootl-atlas-gold
	@echo "  Buckets criados: bronze, silver, gold"

# ─── Pipeline ────────────────────────────────────────────────────────────────

pipeline-dry-run: ## Valida catálogo e schemas sem baixar dados
	docker compose run --rm pipeline python flows/main_pipeline.py run --dry-run

pipeline-run: ## Executa o pipeline completo (download + transformações + carga)
	docker compose run --rm pipeline python flows/main_pipeline.py run

pipeline-run-no-ingest: ## Executa sem download (usa Bronze existente)
	docker compose run --rm pipeline python flows/main_pipeline.py run --skip-ingest

# ─── Testes ──────────────────────────────────────────────────────────────────

test-pipeline: ## Executa testes do pipeline
	docker compose run --rm pipeline python -m pytest tests/ -v --tb=short

test-api: ## Executa testes da API
	docker compose run --rm api python -m pytest tests/ -v --tb=short

test-all: test-pipeline test-api ## Executa todos os testes

# ─── Qualidade de Código ──────────────────────────────────────────────────────

lint-pipeline: ## Linting do pipeline (ruff)
	docker compose run --rm pipeline python -m ruff check . --fix

lint-frontend: ## Linting do frontend
	docker compose run --rm frontend npm run lint

# ─── Limpeza ─────────────────────────────────────────────────────────────────

clean-data: ## Remove dados locais do Lakehouse (CUIDADO!)
	@echo "⚠️  Isso irá remover TODOS os dados processados em ./data/"
	@read -p "Confirmar? (sim/nao): " CONFIRM && \
	  [ "$$CONFIRM" = "sim" ] && rm -rf ./data/bronze ./data/silver ./data/gold || echo "Cancelado."

reset: down ## Para tudo e remove volumes (banco + MinIO)
	docker compose down -v
	@echo "  Todos os volumes removidos. Dados persistentes apagados."

clean: down ## Para os containers (preserva volumes)
	@echo "  Containers parados. Dados preservados."
