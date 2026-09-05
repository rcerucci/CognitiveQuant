# Tasks: F3 — Regime + OU + bootstrap θ

**Input**: `specs/003-f3-regime-ou-bootstrap/spec.md` + `plan.md`  
**Branch**: `003-f3-regime-ou-bootstrap`  
**Locks**: pykalman OU discreto · bootstrap iid · μ_θ≈0 → NEUTRO · `seed=42`  
**Depende de**: F2 PASS (`src/motor/filters/`) + F1 (`src/motor/ohlc/`) em `main`

## Phase 1: Setup

- [ ] T001 Acrescentar dependência `pykalman` em `pyproject.toml`
- [ ] T002 Garantir `numpy` e `scipy` pinados em `pyproject.toml` se ainda faltarem
- [ ] T003 Criar `src/motor/regime/__init__.py`

## Phase 2: Foundational

- [ ] T004 Criar esqueleto exportável de `src/motor/regime/hurst.py`
- [ ] T005 [P] Criar esqueleto exportável de `src/motor/regime/ou.py`
- [ ] T006 [P] Criar esqueleto exportável de `src/motor/regime/bootstrap_theta.py`
- [ ] T007 [P] Criar esqueleto exportável de `src/motor/regime/pipeline.py`

## Phase 3: US1 — Regime Hurst R/S (P1)

- [ ] T008 [US1] Implementar Hurst R/S janela 200 (sub-tamanhos 8/16/32/64/128 + regressão log-log; H<0.45 REVERSÃO; 0.45≤H≤0.55 NEUTRO; H>0.55 NEUTRO; warm-up <200 → NEUTRO) em `src/motor/regime/hurst.py`
- [ ] T009 [P] [US1] Adicionar fixtures reversão / RW / tendência em `tests/fixtures/regime/hurst.json`
- [ ] T010 [US1] Escrever Independent Test US1 (limiares H e bordas 0.45/0.55) em `tests/unit/test_regime_hurst.py`

## Phase 4: US2 — OU Kalman + MLE + τ (P1)

- [ ] T011 [US2] Implementar OU via `pykalman` discreto padrão com fallback MLE janela 200 (θ<0/não-finito → MLE; θ≤0 → NEUTRO; θ>0 → τ=ln(2)/θ) em `src/motor/regime/ou.py`
- [ ] T012 [P] [US2] Adicionar fixtures OU sintético e caminho Kalman→MLE em `tests/fixtures/regime/ou.json`
- [ ] T013 [US2] Escrever Independent Test US2 (θ>0 + τ; θ≤0 → NEUTRO; fallback MLE) em `tests/unit/test_regime_ou.py`

## Phase 5: US3 — Bootstrap θ e CV (P1)

- [ ] T014 [US3] Implementar bootstrap iid 50 na janela 200 com `default_rng(42)` (CV=σ_θ/μ_θ; CV≤0.30 estável; CV>0.30 → flag `forca_penalty_cv` sem NEUTRO; μ_θ≈0 → NEUTRO) em `src/motor/regime/bootstrap_theta.py`
- [ ] T015 [P] [US3] Adicionar fixtures CV≤0.30 vs CV>0.30 e μ_θ≈0 em `tests/fixtures/regime/bootstrap.json`
- [ ] T016 [US3] Escrever Independent Test US3 (estável vs flag; seed=42 reproduzível; μ_θ≈0 → NEUTRO) em `tests/unit/test_regime_bootstrap.py`

## Phase 6: US4 — Pipeline sobre F2 PASS (P2)

- [ ] T017 [US4] Implementar orquestra Hurst→OU→bootstrap só após F2 PASS (sem F2 PASS / Hurst NEUTRO / θ≤0 → não promove PASS; saída in-memory H/μ/θ/τ/CV/flags) em `src/motor/regime/pipeline.py`
- [ ] T018 [P] [US4] Adicionar fixtures F2 NEUTRO, Hurst NEUTRO e PASS completo em `tests/fixtures/regime/pipeline.json`
- [ ] T019 [US4] Escrever Independent Test US4 (short-circuit + campos PASS) em `tests/unit/test_regime_pipeline.py`

## Phase 7: Polish

- [ ] T020 Exportar API pública do regime em `src/motor/regime/__init__.py`
- [ ] T021 [P] Reexportar `regime` em `src/motor/__init__.py`
- [ ] T022 Verificar SC-001–SC-004 (limiares H, τ, flag CV sem NEUTRO, escopo sem GARCH/payload/TA/CUSUM) via suite em `tests/unit/test_regime_*.py`
