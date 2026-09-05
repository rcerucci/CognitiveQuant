# Implementation Plan: F4 — GARCH + Z + percentil

**Branch**: `004-f4-garch-z-percentil` | **Date**: 2026-09-05 | **Spec**: `specs/004-f4-garch-z-percentil/spec.md`

**Input**: Feature specification from `/specs/004-f4-garch-z-percentil/spec.md`

**Locks (Marcos)**: lib GARCH = **`arch`** · `percentileofscore` = **`mean`** · σ≤0 / não-finito → **NEUTRO** · `seed=42` quando aplicável

**Depende de**: F3 PASS in-memory — `src/motor/regime/` + série F1 (`X_t`, `r_t`) + `μ_t` (já em `main`)

## Summary

Implementar Passos 6–7 do **Motor** (§3.7–3.8): GARCH(1,1) via pacote `arch` em `r_{t-199:t}` (α+β<0.995; senão fallback √(∑r²/20)) → `Z_t=(X_t−μ_t)/σ_t` → `P_t=percentileofscore(|Z|, 200, method='mean')` como input de força — **sem** filtro de passagem por percentil. Saída in-memory. Sem confirmação/força/payload/TA. Estende `src/motor/` ao lado de `ohlc/`, `filters/`, `regime/`.

## Technical Context

**Language/Version**: Python (Camada 1 — consolidado §2.3; stack F1–F3 / `pyproject.toml` existente)

**Primary Dependencies (F4)**:
- `arch` — GARCH(1,1) MLE (consolidado §12; lock Marcos)
- `scipy.stats.percentileofscore` — método **`mean`** (lock)
- `numpy` — janelas / fallback
- Consumo: API F3 (`regime.pipeline` / PASS + `μ_t`) + `X_t`, `r_t` da série F1

**Storage**: N/A — saída **in-memory**.

**Testing**: `pytest` + fixtures sintéticas (GARCH convergente / α+β≥0.995 / fallback / Z e P de referência).

**Target Platform**: Host do motor (library Python).

**Project Type**: library — Option 1 Spec Kit; subpacote novo sob `src/motor/`.

**Constraints**:
- Ordem: GARCH → Z → percentil
- α+β < 0.995 estrito; `α+β ≥ 0.995` ou não-convergência → fallback (PASS possível se σ>0)
- σ≤0 / não-finito → **NEUTRO** (lock)
- Warm-up <200 retornos → NEUTRO
- `P_t` alto (ex. >0.95) **não** sozinho → NEUTRO
- Entrada sem F3 PASS → não promove PASS / não emite Z/P válidos
- Sem confirmação §3.9 / força §3.10 / payload §3.11

**Scale/Scope**: US1–US4 da spec F4; limiares só do doc.

## Constitution Check

- Só Motor; zero TA/executor/confirmação/força/payload.
- Fallback ≠ Abort de formato F1; σ inválido = NEUTRO.
- Percentil é input para F5, não gate.

**Gate**: PASS com `regime/` em `main`.

## Árvore real (pós-F3 em `main`) vs o que F4 adiciona

**Já existe**:

```text
pyproject.toml
src/motor/__init__.py
src/motor/ohlc/          # F1
src/motor/filters/       # F2
src/motor/regime/        # F3
tests/unit/test_ohlc_*.py
tests/unit/test_filter_*.py
tests/unit/test_regime_*.py
tests/fixtures/{ohlc,filters,regime}/
specs/001-…/ 002-…/ 003-…/
```

**F4 adiciona**:

```text
src/motor/vol/
  __init__.py
  garch.py           # US1 arch GARCH(1,1) + fallback
  zscore.py          # US2 Z condicional
  percentil.py       # US3 percentileofscore mean
  pipeline.py        # US4 orquestra sobre F3 PASS

tests/unit/
  test_vol_garch.py
  test_vol_zscore.py
  test_vol_percentil.py
  test_vol_pipeline.py

tests/fixtures/vol/
  garch.json
  zscore.json
  percentil.json
  pipeline.json
```

**Deps**: acrescentar `arch` em `pyproject.toml` (garantir `scipy`/`numpy` já pinados). Sem TradingAgents/MCP.

## Project Structure

### Documentation (this feature)

```text
specs/004-f4-garch-z-percentil/
├── plan.md              # este arquivo
├── spec.md              # Spec (entregue)
└── tasks.md             # Tasks (próximo — NÃO gerado aqui)
```

**Structure Decision**: `src/motor/vol/` ao lado de `ohlc/`, `filters/`, `regime/` — F5 (confirmação/força/payload) fica em outro subpacote; F1–F3 intactos (só consumo).

## O que esta fatia MEXE

| Área | Paths |
|------|--------|
| Spec package | `specs/004-f4-garch-z-percentil/` |
| Vol/GARCH/Z/P | `src/motor/vol/{garch,zscore,percentil,pipeline}.py` |
| Deps | `pyproject.toml` (+ `arch`) |
| Testes | `tests/unit/test_vol_*.py` + `tests/fixtures/vol/` |
| Export | `src/motor/vol/__init__.py` (+ reexport opcional em `src/motor/__init__.py`) |

## O que esta fatia NÃO MEXE

- `src/motor/ohlc/**`, `filters/**`, `regime/**` (exceto **consumir** APIs)
- Confirmação / força / direção / payload — **F5**
- Backtest / TA / executor / FTMO — **F6–F9**
- Usar `P_t` como filtro de passagem
- `volume`, UI, §9.2
- Paths fora da árvore acima

## Dependências e ordem no pipeline do sistema

```text
[F1] → [F2] → [F3 Regime+OU]  ← em main
        ↓
[F4 GARCH+Z+percentil]  ← ESTA FATIA
        ↓
[F5 Confirmação+força+payload] → …
```

Dentro de F4: **Setup deps → garch → zscore → percentil → pipeline → testes por US**.

## Onde vive o teste

| US | Independent Test → arquivo |
|----|----------------------------|
| US1 | `tests/unit/test_vol_garch.py` |
| US2 | `tests/unit/test_vol_zscore.py` |
| US3 | `tests/unit/test_vol_percentil.py` |
| US4 | `tests/unit/test_vol_pipeline.py` |
| Fixtures | `tests/fixtures/vol/` |

Runner: `pytest` na raiz.

## Complexity Tracking

N/A — `arch` e `percentileofscore(mean)` são locks Marcos + refs do consolidado; não stack inventada.
