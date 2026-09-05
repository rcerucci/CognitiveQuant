# Tasks: F1 — Validação OHLC + transform

**Input**: `specs/001-f1-validacao-ohlc-transform/spec.md` + `plan.md`  
**Branch**: `001-f1-validacao-ohlc-transform`  
**Locks**: UTC-only · saída in-memory · §9.2 depois · Setup `src/`/`tests/`

## Phase 1: Setup

- [ ] T001 Criar `pyproject.toml` com projeto Python e dependência `pytest`
- [ ] T002 [P] Criar `src/motor/__init__.py`
- [ ] T003 [P] Criar `src/motor/ohlc/__init__.py`

## Phase 2: Foundational

- [ ] T004 Criar esqueleto exportável de `src/motor/ohlc/validation.py`
- [ ] T005 [P] Criar esqueleto exportável de `src/motor/ohlc/sync.py`
- [ ] T006 [P] Criar esqueleto exportável de `src/motor/ohlc/transform.py`

## Phase 3: US1 — Formato e integridade (P1)

- [ ] T007 [US1] Implementar validação de formato JSON `[timestamp_UTC, open, high, low, close, bid, ask]`, UTC-only e integridade `high`/`low` com Abort imediato e logs literais (`format_invalido`, `integridade_preco_invalida`) em `src/motor/ohlc/validation.py`
- [ ] T008 [P] [US1] Adicionar fixtures de barras válidas e inválidas (formato, integridade, timezone) em `tests/fixtures/ohlc/format_integrity.json`
- [ ] T009 [US1] Escrever Independent Test US1 (válidas vs inválidas; assert Abort + código de log) em `tests/unit/test_ohlc_format_integrity.py`

## Phase 4: US2 — Ordem temporal e gaps (P1)

- [ ] T010 [US2] Implementar ordem temporal sem duplicatas, interpolação linear gap ≤ 4, `gap_dados`+NEUTRO se gap > 4, e weekend forward-fill de preços com flag (sem preencher TR) em `src/motor/ohlc/validation.py`
- [ ] T011 [P] [US2] Adicionar fixtures de duplicata, ordem invertida, gaps 1–4 / >4 e weekend em `tests/fixtures/ohlc/order_gaps.json`
- [ ] T012 [US2] Escrever Independent Test US2 (abort vs interpolação vs NEUTRO/`gap_dados` vs forward fill) em `tests/unit/test_ohlc_order_gaps.py`

## Phase 5: US4 — Transform mid → log → retorno (P1)

- [ ] T013 [US4] Implementar P_t=(Bid_t+Ask_t)/2, X_t=ln(P_t), r_t=X_t-X_{t-1} in-memory (sem r_t no primeiro índice; Abort se P_t≤0) em `src/motor/ohlc/transform.py`
- [ ] T014 [P] [US4] Adicionar fixtures de referência bid/ask → mid → ln → delta em `tests/fixtures/ohlc/transform_reference.json`
- [ ] T015 [US4] Escrever Independent Test US4 (valores de referência com tolerância numérica de teste) em `tests/unit/test_ohlc_transform.py`

## Phase 6: US3 — Sync multi-instrumento (P2)

- [ ] T016 [US3] Implementar alinhamento multi-instrumento por `timestamp_UTC` (merge outer + preenchimento linear; N genérico sem lista §9.2) em `src/motor/ohlc/sync.py`
- [ ] T017 [P] [US3] Adicionar fixtures de ≥2 séries com timestamps parcialmente sobrepostos em `tests/fixtures/ohlc/sync_multi.json`
- [ ] T018 [US3] Escrever Independent Test US3 (grade unificada + preenchimento linear) em `tests/unit/test_ohlc_sync.py`

## Phase 7: Polish

- [ ] T019 Exportar API pública (`validation`, `sync`, `transform`) em `src/motor/ohlc/__init__.py`
- [ ] T020 Verificar SC-001–SC-004 (aborts/logs, gaps, transformação, escopo sem §3.3+) via suite em `tests/unit/`
