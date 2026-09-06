# Implementation Plan: F3 — Hotfix 003b gate de regime (2026-09-06)

**Branch**: `hotfix/003b-regime-gate` | **Date**: 2026-09-06 | **Spec**: `specs/003-f3-regime-ou-bootstrap/spec.md` (Addendum 003b)

**Input**: Spec 003b + **LOCK Marcos** (K / θ / IC)

**Locks (Marcos 003b)**:
- H DFA = **diagnóstico** — **não** abre PASS; `H > 0.55` **não** vira tendência
- PASS reversão exige **ambos**:
  1. \(\hat\theta > 0\) **e** (se bootstrap rodou) **IC inferior > 0**
  2. \(\tau = \ln(2)/\hat\theta \le K\), **K = 20** barras M30
- Cadeado efetivo: τ≤20 + θ identificável (piso implícito \(\hat\theta \ge \ln2/K \approx 0.0347\) quando τ é meia-vida)
- Janela Hurst/OU = **200** inalterada
- Sem F7 · sem run 10×65k neste PR · `seed=42`

**Depende de**: F2 ADF \(r_t\) em `main` (#12); estimador DFA Peng em `hurst.py` (hotfix `003-hurst-dfa` / #13 código — se ainda só docs, **basear este branch no código DFA** ou mergear DFA antes). Bootstrap iid 50 / CV 0.30 / μ_θ≈0→NEUTRO **mantidos**.

## Summary

Migrar o gate de PASS de faixas H (0.45/0.55) para **OU + meia-vida**: emitir H só como diagnóstico; PASS se θ̂>0, IC inferior bootstrap >0 (quando houver), e τ≤20; senão NEUTRO. Sem path de tendência.

## Technical Context

**Language/Version**: Python ≥3.11

**Primary Dependencies**: `numpy`, `pykalman` (já no projeto) — **sem** lib nova

**IC inferior (amarrado)**: percentil empírico **2.5%** das 50 θs bootstrap (IC 95% bilateral); MUST **> 0** para PASS. (Assunção padrão; Marcos pode sobrescrever o percentil.)

**Testing**: `pytest`; SC-006: τ>20 → NEUTRO; τ≤20 + θ̂ ok + IC_low>0 → PASS **sem** exigir H&lt;0.45; H&gt;0.55 sem tendência

**Constraints**:
- Ordem: DFA (diagnóstico) → OU → **gate θ/τ/IC** → bootstrap (CV flag inalterado)
- MUST NOT restaurar H hard-gate
- MUST NOT GARCH/Z/payload/TA/F7/CUSUM

## Árvore real (`origin/main`) vs hotfix

**Já existe**:

```text
src/motor/regime/hurst.py              # ainda classifica PASS/NEUTRO por H — MUDA
src/motor/regime/ou.py                 # τ = ln2/θ; θ≤0 → NEUTRO — estende gate τ≤K
src/motor/regime/bootstrap_theta.py    # CV / μ_θ — acrescenta IC inferior
src/motor/regime/pipeline.py           # H hard-gate na orquestração — MUDA
tests/unit/test_regime_{hurst,ou,bootstrap,pipeline}.py
tests/unit/test_hurst_sanity.py        # se já existir pós-DFA
tests/fixtures/regime/
specs/003-f3-regime-ou-bootstrap/
```

**Hotfix 003b adiciona / altera**:

```text
src/motor/regime/hurst.py              # H diagnóstico; sem NEUTRO/PASS por faixa 0.45/0.55
src/motor/regime/ou.py                 # expor τ; falha se τ > K (ou delegar ao pipeline)
src/motor/regime/bootstrap_theta.py    # IC inferior (p2.5); falha se IC_low ≤ 0
src/motor/regime/pipeline.py           # ordem 003b; K=20; sem short-circuit por H
src/motor/regime/__init__.py           # export K / campos novos se preciso

tests/unit/test_regime_pipeline.py     # SC-006 gate τ/θ/IC
tests/unit/test_regime_ou.py           # τ≤20 / τ>20
tests/unit/test_regime_bootstrap.py    # IC_low > 0
tests/unit/test_regime_hurst.py        # H não força PASS/NEUTRO
tests/fixtures/regime/pipeline.json    # casos τ/K
tests/fixtures/regime/ou.json

specs/003-f3-regime-ou-bootstrap/plan.md   # este arquivo
# tasks.md append — Tasks
```

**Constante**: `K_HALF_LIFE_BARS = 20` (único lugar canônico — preferência `pipeline.py` ou módulo compartilhado em `regime/`).

## O que esta fatia MEXE

| Área | Paths |
|------|--------|
| Gate / orquestração | `src/motor/regime/pipeline.py` |
| Hurst diagnóstico | `src/motor/regime/hurst.py` |
| OU / τ | `src/motor/regime/ou.py` |
| Bootstrap IC | `src/motor/regime/bootstrap_theta.py` |
| Testes / fixtures | `tests/unit/test_regime_*.py`, `tests/fixtures/regime/` |
| Spec package | `specs/003-f3-regime-ou-bootstrap/` |

## O que NÃO MEXE

- Escalas DFA `{8,16,32,64}` / DFA Peng (exceto remover hard-gate H)
- `src/motor/filters/**`, `ohlc/`, `vol/`, `signal/`, `backtest/`
- F7 · 10×65k · mudar K sem Marcos · inventar path tendência

## Ordem interna

```text
hurst diagnóstico → ou (θ,τ) → gate τ≤20 + θ>0
  → bootstrap (CV + IC_low>0) → pipeline PASS/NEUTRO → testes SC-006
```

## Onde vive o teste

| Item | Path |
|------|------|
| SC-006 Independent Test | `tests/unit/test_regime_pipeline.py` (+ ou/bootstrap) |
| H sem hard-gate | `tests/unit/test_regime_hurst.py` |
| Fixtures | `tests/fixtures/regime/{pipeline,ou,bootstrap}.json` |

## Complexity Tracking

- Percentil IC **2.5%** amarrado no plan (Spec não fixou); Marcos sobrescreve se quiser outro.
- Código `main` ainda pode ter H hard-gate / DFA só em branch — 003b **assume** DFA presente; senão mergear `hotfix/003-hurst-dfa` primeiro.
