# Tasks: F2 — Filtros de qualidade

**Input**: `specs/002-f2-filtros-qualidade/spec.md` + `plan.md`  
**Branch**: `002-f2-filtros-qualidade`  
**Locks**: Parkinson clássica high/low · warm-up → NEUTRO · short-circuit no 1º filtro  
**Depende de**: F1 in-memory (`src/motor/ohlc/`)

## Phase 1: Setup

- [ ] T001 Acrescentar dependência `statsmodels` em `pyproject.toml`
- [ ] T002 Criar `src/motor/filters/__init__.py`

## Phase 2: Foundational

- [ ] T003 Criar esqueleto exportável de `src/motor/filters/spread.py`
- [ ] T004 [P] Criar esqueleto exportável de `src/motor/filters/adf.py`
- [ ] T005 [P] Criar esqueleto exportável de `src/motor/filters/tr.py`
- [ ] T006 [P] Criar esqueleto exportável de `src/motor/filters/parkinson.py`
- [ ] T007 [P] Criar esqueleto exportável de `src/motor/filters/pipeline.py`

## Phase 3: US1 — Spread anômalo (P1)

- [ ] T008 [US1] Implementar filtro Spread (`Ask_t - Bid_t ≤ 2 × média(20)`; warm-up <20 → NEUTRO; falha → NEUTRO) em `src/motor/filters/spread.py`
- [ ] T009 [P] [US1] Adicionar fixtures de spread normal vs spike em `tests/fixtures/filters/spread.json`
- [ ] T010 [US1] Escrever Independent Test US1 em `tests/unit/test_filter_spread.py`

## Phase 4: US2 — ADF estacionariedade (P1)

- [ ] T011 [US2] Implementar ADF em `X_{t-199:t}` com lags=5 e passagem `p < 0.05` (warm-up <200 → NEUTRO; falha → NEUTRO) em `src/motor/filters/adf.py`
- [ ] T012 [P] [US2] Adicionar fixtures estacionária vs não-estacionária em `tests/fixtures/filters/adf.json`
- [ ] T013 [US2] Escrever Independent Test US2 em `tests/unit/test_filter_adf.py`

## Phase 5: US3 — TR anômalo (P1)

- [ ] T014 [US3] Implementar TR (`max(H-L, |H-C_{t-1}|, |L-C_{t-1}|) ≤ 2.5 × média(20)`; weekend_fill não observado; warm-up <20 → NEUTRO) em `src/motor/filters/tr.py`
- [ ] T015 [P] [US3] Adicionar fixtures TR normal/spike e weekend_fill em `tests/fixtures/filters/tr.json`
- [ ] T016 [US3] Escrever Independent Test US3 em `tests/unit/test_filter_tr.py`

## Phase 6: US4 — Vol Parkinson (P1)

- [ ] T017 [US4] Implementar Parkinson clássica high/low (`σ_20/σ_60 ≤ 1.5`; warm-up <60 → NEUTRO; falha → NEUTRO temporário 1 barra + log `"volatility_spike_detected"`) em `src/motor/filters/parkinson.py`
- [ ] T018 [P] [US4] Adicionar fixtures razão ≤1.5 vs >1.5 em `tests/fixtures/filters/parkinson.json`
- [ ] T019 [US4] Escrever Independent Test US4 em `tests/unit/test_filter_parkinson.py`

## Phase 7: US5 — Pipeline ordem §5.1 (P2)

- [ ] T020 [US5] Implementar orquestra Spread→ADF→TR→Vol com short-circuit no 1º filtro; consumir API F1; `gap_dados`/NEUTRO F1 não promove PASS em `src/motor/filters/pipeline.py`
- [ ] T021 [P] [US5] Adicionar fixtures all-pass, falha ADF e só vol em `tests/fixtures/filters/pipeline.json`
- [ ] T022 [US5] Escrever Independent Test US5 (ordem + short-circuit + motivos) em `tests/unit/test_filter_pipeline.py`

## Phase 8: Polish

- [ ] T023 Exportar API pública dos filtros em `src/motor/filters/__init__.py`
- [ ] T024 [P] Reexportar `filters` em `src/motor/__init__.py`
- [ ] T025 Verificar SC-001–SC-004 (NEUTRO nos limiares, ordem §5.1, escopo sem §3.4+, weekend_fill sem TR) via suite em `tests/unit/test_filter_*.py`
## Phase hotfix: US2 — ADF em r_t (addendum)

- [ ] T026 [US2] Alterar ADF para série `r_{t-199:t}` (lags=5; p<0.05; sem retorno → NEUTRO/skip) em `src/motor/filters/adf.py`
- [ ] T027 [US2] Passar `r_t` (não `X_t`) ao ADF em `src/motor/filters/pipeline.py`
- [ ] T028 [P] [US2] Atualizar fixtures RW/log-preço I(1) vs retorno ~branco em `tests/fixtures/filters/adf.json`
- [ ] T029 [US2] Atualizar Independent Test US2 (ADF(X) falha / ADF(r) passa; seed=42) em `tests/unit/test_filter_adf.py`
