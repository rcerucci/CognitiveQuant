# Implementation Plan: F5 — Confirmação + força + payload

**Branch**: `005-f5-confirmacao-forca-payload` | **Date**: 2026-09-05 | **Spec**: `specs/005-f5-confirmacao-forca-payload/spec.md`

**Input**: Feature specification from `/specs/005-f5-confirmacao-forca-payload/spec.md`

**Locks (Marcos)**: 8.1 soft · 8.2–8.5 hard-gate · 8.6 abort (NEUTRO) · limiares fixos **0.75 / 0.60** (adaptativo adiado) · NEUTRO **emite** payload (`direcao`/`confianca` = NEUTRO) · fonte = consolidado v1.2 · `seed=42` se houver aleatoriedade

**Depende de**: F4 PASS in-memory — `src/motor/vol/` (`Z_t`, `percentil_z`, σ, fonte) + F3 (`μ`, `θ`, `τ`, H, regime, `forca_penalty_cv`) + F2 flags + OHLC F1

## Summary

Fechar a Camada 1 do **Motor** (§3.9–3.11): confirmações 8.1–8.6 → direção/força com penalizações (piso 0.18, 2 dp) → classificação ALTA/MÉDIA/NEUTRO (0.75/0.60) → payload JSON §3.11 in-memory (incl. registro NEUTRO). Sem TA/executor/adaptativo persistente. Estende `src/motor/` ao lado de `ohlc/`, `filters/`, `regime/`, `vol/`.

## Technical Context

**Language/Version**: Python (Camada 1 — consolidado §2.3; stack F1–F4 / `pyproject.toml` existente)

**Primary Dependencies (F5)**:
- `statsmodels` — ACF(1), Ljung-Box k=5 (já no projeto via F2; consolidado §12)
- `numpy` / `scipy` — skewness, aritmética de força
- Consumo: APIs públicas F4 (`vol.pipeline`), F3 (`regime`), F1 (`ohlc`) — **sem** reimplementar

**Storage**: N/A — saída **in-memory** (dict JSON-serializável). Sem arquivo de estado de trigger-rate (adaptativo fora).

**Testing**: `pytest` + fixtures sintéticas (confirmações, força/penalizações, thresholds, payload schema).

**Target Platform**: Host do motor (library Python).

**Project Type**: library — Option 1 Spec Kit; subpacote novo sob `src/motor/`.

**Constraints**:
- Ordem: confirmação → direção/força → threshold → payload
- 8.1 (ACF): soft — métrica + penalização ×0.70 se ρ₁<0; **não** hard-gate sozinho
- 8.2–8.5: hard-gate → NEUTRO se falha
- 8.6: abort → NEUTRO
- High=Low → NEUTRO (CLV/RB/shadow indefinidos)
- Força: `0.35×P_t + 0.25×max(ρ₁,0) + 0.25×|CLV| + 0.15×RB`; penalizações skew→CV_θ→ACF; piso **0.18**; round **2** dp
- Classificação: `>=0.75` ALTA; `0.60<=f<0.75` MÉDIA; `<0.60` NEUTRO (sem adaptativo)
- NEUTRO: **emite** payload com `direcao`/`confianca` = NEUTRO
- `meia_vida_minutos = τ × 30`
- Entrada sem F4 PASS → não promove LONG/SHORT
- Sem TradingAgents / executor / broker

**Scale/Scope**: US1–US5 da spec F5; limiares só do doc + locks.

## Constitution Check

- Só Motor Camada 1; zero TA/executor.
- NEUTRO ≠ Abort de formato F1; 8.6 = NEUTRO de sinal.
- Adaptativo adiado — sem persistência de trigger rate.

**Gate**: PASS com `vol/` (F4) em `main` (ou feature mergeada antes do coderbot F5).

## Árvore real (pós-F4) vs o que F5 adiciona

**Já existe** (não recriar):

```text
pyproject.toml
src/motor/__init__.py
src/motor/ohlc/          # F1
src/motor/filters/       # F2
src/motor/regime/        # F3
src/motor/vol/           # F4
tests/unit/test_{ohlc,filter,regime,vol}_*.py
tests/fixtures/{ohlc,filters,regime,vol}/
specs/001-…/ … /004-…/
```

**F5 adiciona**:

```text
src/motor/signal/
  __init__.py
  confirmacao.py     # US1 — 8.1–8.6 (ACF, LB, CLV, RB, shadows, skew)
  forca.py           # US2 — direção + força + penalizações
  thresholds.py      # US3 — ALTA/MÉDIA/NEUTRO 0.75/0.60
  payload.py         # US4 — schema §3.11 in-memory
  pipeline.py        # US5 — orquestra sobre F4 PASS

tests/unit/
  test_signal_confirmacao.py
  test_signal_forca.py
  test_signal_thresholds.py
  test_signal_payload.py
  test_signal_pipeline.py

tests/fixtures/signal/
  confirmacao.json
  forca.json
  thresholds.json
  payload.json
  pipeline.json
```

**Deps**: nenhuma lib nova obrigatória além do ecossistema já no repo (`statsmodels`/`scipy`/`numpy`). Sem `arch` novo (já F4).

## Project Structure

### Documentation (this feature)

```text
specs/005-f5-confirmacao-forca-payload/
├── plan.md              # este arquivo
├── spec.md              # Spec (aprovada)
└── tasks.md             # Tasks (próximo — NÃO gerado aqui)
```

**Structure Decision**: `src/motor/signal/` ao lado de `ohlc/`, `filters/`, `regime/`, `vol/` — fecha Camada 1; F6+ não misturam TA aqui.

## O que esta fatia MEXE

| Área | Paths |
|------|--------|
| Spec package | `specs/005-f5-confirmacao-forca-payload/` |
| Sinal/payload | `src/motor/signal/{confirmacao,forca,thresholds,payload,pipeline}.py` |
| Testes | `tests/unit/test_signal_*.py` + `tests/fixtures/signal/` |
| Export | `src/motor/signal/__init__.py` (+ reexport opcional em `src/motor/__init__.py`) |

## O que esta fatia NÃO MEXE

- `src/motor/ohlc/**`, `filters/**`, `regime/**`, `vol/**` (exceto **consumir**)
- Calibração adaptativa / trigger rate 2 semanas — **depois**
- Backtest motor-only — **F6**
- TradingAgents / executor / paper / FTMO — **F7–F9**
- UI, `volume`, §9.2
- Paths fora da árvore acima

## Dependências e ordem no pipeline do sistema

```text
[F1] → [F2] → [F3] → [F4 vol]  ← pré-requisito
        ↓
[F5 signal: confirmação+força+payload]  ← ESTA FATIA
        ↓
[F6 Backtest] → [F7 TA] → …
```

Dentro de F5: **Setup pastas → confirmacao → forca → thresholds → payload → pipeline → testes por US**.

## Onde vive o teste

| US | Independent Test → arquivo |
|----|----------------------------|
| US1 | `tests/unit/test_signal_confirmacao.py` |
| US2 | `tests/unit/test_signal_forca.py` |
| US3 | `tests/unit/test_signal_thresholds.py` |
| US4 | `tests/unit/test_signal_payload.py` |
| US5 | `tests/unit/test_signal_pipeline.py` |
| Fixtures | `tests/fixtures/signal/` |

Runner: `pytest` na raiz.

## Complexity Tracking

N/A — sem stack nova; locks Marcos fecham ambiguidade de gates/adaptativo/NEUTRO.
