# Implementation Plan: F3 — Regime + OU + bootstrap θ

**Branch**: `003-f3-regime-ou-bootstrap` | **Date**: 2026-09-05 | **Spec**: `specs/003-f3-regime-ou-bootstrap/spec.md`

**Locks (Marcos)**: Kalman = **pykalman** OU discreto padrão · bootstrap = **iid** janela 200 · μ_θ≈0 → **NEUTRO** · `seed=42`

**Depende de**: F2 PASS in-memory — `src/motor/filters/` + F1 `src/motor/ohlc/` (já em `main` via #5)

## Summary

Implementar Passos 3–5 do **Motor** (§3.4–3.6): Hurst R/S (janela 200) → se REVERSÃO, OU via pykalman com fallback MLE (θ≤0 → NEUTRO; τ=ln(2)/θ) → bootstrap iid 50 / CV θ (CV>0.30 = flag ×0.80 para F5, não NEUTRO; μ_θ≈0 → NEUTRO). Saída in-memory. Sem GARCH/Z/payload/TA/CUSUM. Estende `src/motor/` ao lado de `ohlc/` e `filters/`.

## Technical Context

**Language/Version**: Python (Camada 1)

**Primary Dependencies (F3)**:
- `numpy` — R/S, bootstrap `default_rng(42)`
- `pykalman` — Kalman OU discreto padrão
- MLE fallback: `scipy.optimize` / likelihood OU janela 200
- Consumo: API pública F2 + série F1

**Storage**: N/A — in-memory

**Testing**: `pytest` + fixtures sintéticas

**Constraints**: Ordem Hurst → OU → bootstrap; limiares H/θ/CV do doc; warm-up <200 → NEUTRO; seed=42

## Árvore — F3 adiciona

```text
src/motor/regime/
  __init__.py
  hurst.py
  ou.py
  bootstrap_theta.py
  pipeline.py

tests/unit/
  test_regime_hurst.py
  test_regime_ou.py
  test_regime_bootstrap.py
  test_regime_pipeline.py

tests/fixtures/regime/
  hurst.json
  ou.json
  bootstrap.json
  pipeline.json
```

**Deps**: `pykalman` (+ numpy/scipy se faltarem) em `pyproject.toml`.

## O que esta fatia MEXE

`specs/003-f3-regime-ou-bootstrap/` · `src/motor/regime/**` · `pyproject.toml` · `tests/unit/test_regime_*.py` · `tests/fixtures/regime/` · reexport em `src/motor/__init__.py`

## O que esta fatia NÃO MEXE

`src/motor/ohlc/**`, `src/motor/filters/**` (só consumir) · GARCH/Z/payload/força · CUSUM · TA/executor/FTMO · volume/UI/§9.2

## Onde vive o teste

| US | arquivo |
|----|---------|
| US1 | `tests/unit/test_regime_hurst.py` |
| US2 | `tests/unit/test_regime_ou.py` |
| US3 | `tests/unit/test_regime_bootstrap.py` |
| US4 | `tests/unit/test_regime_pipeline.py` |
