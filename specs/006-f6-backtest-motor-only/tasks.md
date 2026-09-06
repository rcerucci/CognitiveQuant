# Tasks: F6 — Backtest motor-only

**Input**: `specs/006-f6-backtest-motor-only/spec.md` + `plan.md`  
**Branch**: `006-f6-backtest-motor-only`  
**Locks**: CSV/parquet real · PnL (a) mid→τ/sem flip · trigger ALTA|MÉDIA (≥0.60) · Sharpe diário Rf=0 ×√252 · gate ≥7/10 Sharpe>0.5 · `seed=42`  
**Depende de**: F5 em `main` (`src/motor/{ohlc,filters,regime,vol,signal}/`)

## Phase 1: Setup

- [ ] T001 Acrescentar dependências `pandas` e `pyarrow` em `pyproject.toml`
- [ ] T002 Criar `data/ohlc/.gitkeep` (path Setup; dataset 5 anos materializado fora do provider)
- [ ] T003 Criar `src/motor/backtest/__init__.py`

## Phase 2: Foundational

- [ ] T004 Criar esqueleto exportável de `src/motor/backtest/loader.py`
- [ ] T005 [P] Criar esqueleto exportável de `src/motor/backtest/runner.py`
- [ ] T006 [P] Criar esqueleto exportável de `src/motor/backtest/pnl.py`
- [ ] T007 [P] Criar esqueleto exportável de `src/motor/backtest/metrics.py`
- [ ] T008 [P] Criar esqueleto exportável de `src/motor/backtest/report.py`
- [ ] T009 [P] Criar esqueleto exportável de `src/motor/backtest/pipeline.py`

## Phase 3: US2 — Loader CSV/parquet (P1)

- [ ] T010 [US2] Implementar carga CSV/parquet → barras F1 para o universo §9.2 (EUR/USD, GBP/JPY, USD/CAD, AUD/NZD, US500, GER30, JP225, XAU/USD, USOIL, NAS100); sem SDK de provider em `src/motor/backtest/loader.py`
- [ ] T011 [P] [US2] Adicionar fixture pequena de barras em `tests/fixtures/backtest/sample_bars.parquet`
- [ ] T012 [US2] Escrever Independent Test US2 em `tests/unit/test_backtest_loader.py`

## Phase 4: US1 — Runner F1→F5 (P1)

- [ ] T013 [US1] Implementar runner barra-a-barra F1→F5 puro (sem TA/MCP; consumir APIs públicas) em `src/motor/backtest/runner.py`
- [ ] T014 [US1] Escrever Independent Test US1 em `tests/unit/test_backtest_runner.py`

## Phase 5: US3 — PnL motor-only (P1)

- [ ] T015 [US3] Implementar trades trigger ALTA|MÉDIA (força ≥0.60): entry mid-close `(bid+ask)/2`, exit mid-close em `validade_ate`/`meia_vida_barras`, sem flip, custo zero, truncamento fim-de-série + log em `src/motor/backtest/pnl.py`
- [ ] T016 [P] [US3] Adicionar fixtures de trades/equity em `tests/fixtures/backtest/equity_trades.json`
- [ ] T017 [US3] Escrever Independent Test US3 em `tests/unit/test_backtest_pnl.py`

## Phase 6: US4 — Métricas §10.1 (P1)

- [ ] T018 [US4] Implementar Sharpe (equity diária, Rf=0, ×√252), WR, PF, MaxDD, taxa triggers, mediana τ; zero triggers → sem Sharpe inventado em `src/motor/backtest/metrics.py`
- [ ] T019 [P] [US4] Adicionar fixtures de tabela Sharpe/métricas em `tests/fixtures/backtest/sharpe_table.json`
- [ ] T020 [US4] Escrever Independent Test US4 em `tests/unit/test_backtest_metrics.py`

## Phase 7: US5 — Gate 7/10 + relatório (P2)

- [ ] T021 [US5] Implementar gate `count(Sharpe>0.5)≥7` e relatório in-memory (alvos §10.1; só-ALTA só diagnóstico) em `src/motor/backtest/report.py`
- [ ] T022 [US5] Implementar orquestra loader→runner→pnl→metrics→report em `src/motor/backtest/pipeline.py`
- [ ] T023 [P] [US5] Escrever Independent Test US5 (gate/relatório) em `tests/unit/test_backtest_report.py`
- [ ] T024 [US5] Escrever Independent Test do pipeline em `tests/unit/test_backtest_pipeline.py`

## Phase 8: Polish

- [ ] T025 Exportar API pública de backtest em `src/motor/backtest/__init__.py`
- [ ] T026 [P] Reexportar `backtest` em `src/motor/__init__.py`
- [ ] T027 Verificar SC da spec F6 (loader, runner, PnL, métricas, gate 7/10, escopo sem TA/MCP/provider) via suite em `tests/unit/test_backtest_*.py`
