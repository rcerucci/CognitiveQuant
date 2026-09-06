# Tasks: F5 — Confirmação + força + payload

**Input**: `specs/005-f5-confirmacao-forca-payload/spec.md` + `plan.md`  
**Branch**: `005-f5-confirmacao-forca-payload`  
**Locks**: 8.1 soft · 8.2–8.5 hard-gate · 8.6 abort · limiares 0.75/0.60 · NEUTRO emite payload · fonte v1.2 · `seed=42`  
**Depende de**: F4 PASS (`src/motor/vol/`) + F3/F2/F1 em `main`

## Phase 1: Setup

- [ ] T001 Criar `src/motor/signal/__init__.py`

## Phase 2: Foundational

- [ ] T002 Criar esqueleto exportável de `src/motor/signal/confirmacao.py`
- [ ] T003 [P] Criar esqueleto exportável de `src/motor/signal/forca.py`
- [ ] T004 [P] Criar esqueleto exportável de `src/motor/signal/thresholds.py`
- [ ] T005 [P] Criar esqueleto exportável de `src/motor/signal/payload.py`
- [ ] T006 [P] Criar esqueleto exportável de `src/motor/signal/pipeline.py`

## Phase 3: US1 — Confirmações 8.1–8.6 (P1)

- [ ] T007 [US1] Implementar ACF(1) soft, Ljung-Box k=5, CLV/RB/US/LS (§1.5), hard-gates 8.2–8.5, abort 8.6 e High=Low → NEUTRO em `src/motor/signal/confirmacao.py`
- [ ] T008 [P] [US1] Adicionar fixtures ACF/LB/CLV/RB/shadow/skew e High=Low em `tests/fixtures/signal/confirmacao.json`
- [ ] T009 [US1] Escrever Independent Test US1 em `tests/unit/test_signal_confirmacao.py`

## Phase 4: US2 — Direção e força (P1)

- [ ] T010 [US2] Implementar direção LONG/SHORT/NEUTRO, força `0.35×P_t+0.25×max(ρ₁,0)+0.25×|CLV|+0.15×RB`, penalizações skew→CV_θ→ACF (piso 0.18, round 2 dp) em `src/motor/signal/forca.py`
- [ ] T011 [P] [US2] Adicionar fixtures de referência força/penalizações/piso em `tests/fixtures/signal/forca.json`
- [ ] T012 [US2] Escrever Independent Test US2 em `tests/unit/test_signal_forca.py`

## Phase 5: US3 — Thresholds 0.75/0.60 (P1)

- [ ] T013 [US3] Implementar classificação ALTA (`>=0.75`) / MÉDIA (`0.60<=f<0.75`) / NEUTRO (`<0.60`) sem adaptativo em `src/motor/signal/thresholds.py`
- [ ] T014 [P] [US3] Adicionar fixtures bordas 0.75/0.74/0.60/0.59 em `tests/fixtures/signal/thresholds.json`
- [ ] T015 [US3] Escrever Independent Test US3 em `tests/unit/test_signal_thresholds.py`

## Phase 6: US4 — Payload §3.11 (P1)

- [ ] T016 [US4] Implementar payload JSON-serializável §3.11 (`meia_vida_minutos=τ×30`; NEUTRO emite `direcao`/`confianca`=NEUTRO) em `src/motor/signal/payload.py`
- [ ] T017 [P] [US4] Adicionar fixtures schema ALTA/MÉDIA e NEUTRO em `tests/fixtures/signal/payload.json`
- [ ] T018 [US4] Escrever Independent Test US4 (chaves obrigatórias + meia_vida) em `tests/unit/test_signal_payload.py`

## Phase 7: US5 — Pipeline sobre F4 PASS (P2)

- [ ] T019 [US5] Implementar orquestra confirmação→força→threshold→payload só após F4 PASS (sem F4 PASS → sem LONG/SHORT; short-circuit 8.6) em `src/motor/signal/pipeline.py`
- [ ] T020 [P] [US5] Adicionar fixtures F4 NEUTRO, 8.6 e PASS+payload em `tests/fixtures/signal/pipeline.json`
- [ ] T021 [US5] Escrever Independent Test US5 em `tests/unit/test_signal_pipeline.py`

## Phase 8: Polish

- [ ] T022 Exportar API pública de signal em `src/motor/signal/__init__.py`
- [ ] T023 [P] Reexportar `signal` em `src/motor/__init__.py`
- [ ] T024 Verificar SC-001–SC-005 (confirmações, força/piso, thresholds, payload, escopo sem TA/executor) via suite em `tests/unit/test_signal_*.py`
