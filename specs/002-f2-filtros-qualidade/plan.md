# Implementation Plan: F2 — Hotfix ADF em \(r_t\) (addendum 2026-09-06)

**Branch**: `hotfix/002-adf-rt` | **Date**: 2026-09-06 | **Spec**: `specs/002-f2-filtros-qualidade/spec.md` (Approved + Addendum ADF \(r_t\))

**Input**: Spec Kit `spec.md` pós-fusão do addendum (US2 / FR-003 / SC-005)

**Locks (addendum)**: série ADF = **\(r_t = X_t - X_{t-1}\)** · janela **200 retornos** · lags=**5** · p&lt;**0.05** iguais · warm-up &lt;200 retornos → NEUTRO · 1ª barra sem \(r\) → NEUTRO/skip · Spread/TR/Parkinson **inalterados** · F3 segue em \(X_t\) · `seed=42` no aceite

**Depende de**: F1 `src/motor/ohlc/` (já em `main`); código F2 vigente em `main` (ADF ainda em \(X_t\) — DIVERGÊNCIA do addendum)

**Ordem vs 003**: aplicar **este hotfix antes** do Hurst DFA (003), para o filtro de qualidade não matar barras antes do regime.

## Summary

Trocar o input do `FilterADF` de log-preço \(X_t\) para retornos \(r_t\), ajustar a extração no `filters/pipeline.py`, atualizar testes/fixtures US2 + SC-005. Não reabre F3–F6; não muda outros filtros F2.

## Technical Context

**Language/Version**: Python ≥3.11 (`pyproject.toml` em `main`)

**Primary Dependencies**: `statsmodels.tsa.stattools.adfuller` (já no projeto) — **sem** lib nova

**Storage**: N/A — in-memory

**Testing**: `pytest`; fixture RW seed=42 — ADF(\(r\)) passa; não exigir passagem em \(X\)

**Constraints**:
- Ordem §5.1 inalterada: Spread → ADF → TR → Parkinson
- MUST NOT usar \(X_t\) como série do ADF de qualidade
- MUST NOT mudar limiar p, lags, janela numérica (200), spread/TR/Parkinson

## Árvore real (`origin/main`) vs hotfix

**Já existe** (consumir / editar pontualmente):

```text
src/motor/filters/adf.py          # hoje: ADF(X_t) — MUDA input
src/motor/filters/pipeline.py     # hoje: monta X_t e passa ao ADF — MUDA extração → r_t
src/motor/filters/{spread,tr,parkinson,__init__}.py  # NÃO MEXE
tests/unit/test_filter_adf.py
tests/fixtures/filters/adf.json
specs/002-f2-filtros-qualidade/{spec,plan,tasks}.md
```

**Hotfix adiciona / altera**:

```text
src/motor/filters/adf.py              # aceitar r_t / documentar janela de retornos
src/motor/filters/pipeline.py         # r_t = ΔX; warm-up &lt;200 retornos; skip 1ª barra
tests/unit/test_filter_adf.py         # SC-005 + US2 em r
tests/fixtures/filters/adf.json       # série RW / retornos alinhados
specs/002-f2-filtros-qualidade/plan.md # este arquivo
# tasks.md append — Tasks (não Plan)
```

## O que esta fatia MEXE

| Área | Paths |
|------|--------|
| ADF | `src/motor/filters/adf.py` |
| Pipeline F2 | `src/motor/filters/pipeline.py` (só passagem de série ao ADF) |
| Testes / fixtures | `tests/unit/test_filter_adf.py`, `tests/fixtures/filters/adf.json` |
| Spec package | `specs/002-f2-filtros-qualidade/` |

## O que NÃO MEXE

- `src/motor/filters/{spread,tr,parkinson}.py`
- `src/motor/{ohlc,regime,vol,signal,backtest}/**`
- Limiares p/lags/janela; F3 Hurst/OU; F4–F6; F7

## Ordem interna do hotfix

```text
adf.py (input r_t) → pipeline.py (extrai r) → testes/fixtures SC-005 → Tasks append
```

## Onde vive o teste

| Item | Path |
|------|------|
| US2 / SC-005 Independent Test | `tests/unit/test_filter_adf.py` |
| Fixture | `tests/fixtures/filters/adf.json` |

## Complexity Tracking

N/A — mudança de intent/série; mesma API statsmodels; sem stack nova.
