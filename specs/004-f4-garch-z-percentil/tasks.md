# Tasks: F4 — GARCH + Z + percentil

**Input**: `specs/004-f4-garch-z-percentil/spec.md` + `plan.md`  
**Branch**: `004-f4-garch-z-percentil`  
**Locks**: lib `arch` · `percentileofscore` `mean` · σ≤0 → NEUTRO · `seed=42`  
**Depende de**: F3 PASS (`src/motor/regime/`) + série F1 (`X_t`, `r_t`, `μ_t`) em `main`

## Phase 1: Setup

- [ ] T001 Acrescentar dependência `arch` em `pyproject.toml`
- [ ] T002 Criar `src/motor/vol/__init__.py`

## Phase 2: Foundational

- [ ] T003 Criar esqueleto exportável de `src/motor/vol/garch.py`
- [ ] T004 [P] Criar esqueleto exportável de `src/motor/vol/zscore.py`
- [ ] T005 [P] Criar esqueleto exportável de `src/motor/vol/percentil.py`
- [ ] T006 [P] Criar esqueleto exportável de `src/motor/vol/pipeline.py`

## Phase 3: US1 — GARCH(1,1) + fallback (P1)

- [ ] T007 [US1] Implementar GARCH(1,1) via `arch` em `r_{t-199:t}` (`α+β < 0.995`; não-convergência ou `α+β ≥ 0.995` → fallback `σ=√(∑r²/20)`; warm-up <200 → NEUTRO; σ≤0 → NEUTRO) em `src/motor/vol/garch.py`
- [ ] T008 [P] [US1] Adicionar fixtures convergente / α+β≥0.995 / fallback em `tests/fixtures/vol/garch.json`
- [ ] T009 [US1] Escrever Independent Test US1 (fonte `garch` vs `fallback`) em `tests/unit/test_vol_garch.py`

## Phase 4: US2 — Z-score condicional (P1)

- [ ] T010 [US2] Implementar `Z_t=(X_t−μ_t)/σ_t` com σ de garch ou fallback (σ≤0 → NEUTRO) em `src/motor/vol/zscore.py`
- [ ] T011 [P] [US2] Adicionar fixtures de referência μ/X/σ → Z em `tests/fixtures/vol/zscore.json`
- [ ] T012 [US2] Escrever Independent Test US2 (Z de referência; σ≤0 → NEUTRO) em `tests/unit/test_vol_zscore.py`

## Phase 5: US3 — Percentil |Z| (P1)

- [ ] T013 [US3] Implementar `P_t=percentileofscore(|Z|, 200, method='mean')` sem filtro de passagem por percentil em `src/motor/vol/percentil.py`
- [ ] T014 [P] [US3] Adicionar fixtures janela 200 de |Z| (incl. extremo >0.95) em `tests/fixtures/vol/percentil.json`
- [ ] T015 [US3] Escrever Independent Test US3 (P_t∈[0,1]; P_t alto não causa NEUTRO) em `tests/unit/test_vol_percentil.py`

## Phase 6: US4 — Pipeline sobre F3 PASS (P2)

- [ ] T016 [US4] Implementar orquestra GARCH→Z→percentil só após F3 PASS (sem F3 PASS → não promove; fallback com σ>0 pode PASS; saída in-memory σ/Z/P/fonte) em `src/motor/vol/pipeline.py`
- [ ] T017 [P] [US4] Adicionar fixtures F3 NEUTRO, garch PASS e fallback PASS em `tests/fixtures/vol/pipeline.json`
- [ ] T018 [US4] Escrever Independent Test US4 em `tests/unit/test_vol_pipeline.py`

## Phase 7: Polish

- [ ] T019 Exportar API pública de vol em `src/motor/vol/__init__.py`
- [ ] T020 [P] Reexportar `vol` em `src/motor/__init__.py`
- [ ] T021 Verificar SC-001–SC-004 (garch vs fallback, Z, P sem gate, escopo sem §3.9+/TA) via suite em `tests/unit/test_vol_*.py`
