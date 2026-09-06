# Implementation Plan: F3 — Hotfix Hurst DFA (addendum 2026-09-06)

**Branch**: `hotfix/003-hurst-dfa` | **Date**: 2026-09-06 | **Spec**: `specs/003-f3-regime-ou-bootstrap/spec.md` (Approved + Addendum Hurst DFA)

**Input**: Spec Kit `spec.md` pós-fusão (US1 / FR-002 / FR-002a / FR-002b / SC-005)

**Locks (addendum)**: estimador = **DFA** em \(X_t\) (nível) · H := α (log F(s)~α log(s)) · janela **200** · escalas N=200 = **`{8,16,32,64}`** (regra ≥2 segmentos + ≥4 escalas; **128 fora**) · cortes **0.45 / 0.55 iguais** · proibido escala com 1 segmento · fallback R/S (1 estatística/escala válida, sem n de 1 bloco) **só se** DFA falhar aceite B · OU/bootstrap **inalterados** · `seed=42`

**Depende de**: hotfix **002 ADF \(r_t\)** preferencialmente em `main` (ou mergeado antes); F2 PASS + F1; `src/motor/regime/hurst.py` vigente ainda R/S (DIVERGÊNCIA)

**Não reabre**: OU, bootstrap θ, F2 ADF (002 à parte), F4–F6, tendência como sinal

## Summary

Substituir Hurst R/S cego por **DFA** em \(X_t\) em `hurst.py`, com escalas trancadas e fallback R/S documentado; acrescentar `tests/unit/test_hurst_sanity.py` A/B/C (branco / OU / RW). Cortes e pipeline F3 (exceto consumo do novo H) intactos.

## Technical Context

**Language/Version**: Python ≥3.11

**Primary Dependencies**: `numpy` (já no projeto) — DFA em puro numpy; **sem** lib nova de fractal. Fallback R/S reusa lógica existente (ajustada: sem n de 1 bloco).

**Storage**: N/A — in-memory

**Testing**: `pytest`; `test_hurst_sanity.py` seed=42:
- A branco → H ∈ [0.35, 0.65]
- B OU nível θ=0.15 σ=0.2 n≥2000 → **H&lt;0.45** + reversão/PASS
- C RW → H&gt;0.55 + NEUTRO  
R/S legado deve **falhar** B (prova do bug). Merge só com B verde no DFA.

**Constraints**:
- Input = \(X_t\) (MUST NOT passar \(r_t\) ao gate de regime)
- Escala inválida se `floor(N/s) < 2`
- H&gt;0.55 continua **NEUTRO** (não gera sinal)
- Warm-up &lt;200 → NEUTRO

## Árvore real (`origin/main`) vs hotfix

**Já existe**:

```text
src/motor/regime/hurst.py           # hoje R/S 8/16/32/64/128 — SUBSTITUIR núcleo
src/motor/regime/{ou,bootstrap_theta,pipeline,__init__}.py  # NÃO MEXE (só consumir H)
tests/unit/test_regime_hurst.py
tests/fixtures/regime/hurst.json
specs/003-f3-regime-ou-bootstrap/{spec,plan,tasks}.md
```

**Hotfix adiciona / altera**:

```text
src/motor/regime/hurst.py                 # DFA + escalas {8,16,32,64} + fallback R/S
tests/unit/test_hurst_sanity.py           # NOVO — A/B/C SC-005
tests/unit/test_regime_hurst.py           # alinhar a DFA / escalas
tests/fixtures/regime/hurst.json          # fixtures DFA / sanity
specs/003-f3-regime-ou-bootstrap/plan.md  # este arquivo
# tasks.md append — Tasks
```

## O que esta fatia MEXE

| Área | Paths |
|------|--------|
| Hurst | `src/motor/regime/hurst.py` |
| Testes | `tests/unit/test_hurst_sanity.py`, `tests/unit/test_regime_hurst.py` |
| Fixtures | `tests/fixtures/regime/hurst.json` |
| Spec package | `specs/003-f3-regime-ou-bootstrap/` |
| Export | `src/motor/regime/__init__.py` só se API pública de Hurst mudar nome (mínimo) |

## O que NÃO MEXE

- `src/motor/regime/{ou,bootstrap_theta,pipeline}.py` (exceto se só tipagem/import do resultado Hurst)
- `src/motor/filters/**` (ADF é hotfix 002)
- `src/motor/{ohlc,vol,signal,backtest}/**`
- Cortes 0.45/0.55; H&gt;0.55=PASS; F7; run 10×65k

## Ordem interna do hotfix

```text
hurst.py DFA → fallback R/S → test_hurst_sanity A/B/C → alinhar test_regime_hurst → Tasks append
```

## Onde vive o teste

| Item | Path |
|------|------|
| SC-005 Independent Test A/B/C | `tests/unit/test_hurst_sanity.py` |
| US1 regressão Hurst | `tests/unit/test_regime_hurst.py` |
| Fixtures | `tests/fixtures/regime/hurst.json` |

## Complexity Tracking

N/A — DFA em numpy; escalas já trancadas no Spec (`{8,16,32,64}`); sem stack inventada.
