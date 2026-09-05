# Implementation Plan: F2 — Filtros de qualidade

**Branch**: `002-f2-filtros-qualidade` | **Date**: 2026-09-05 | **Spec**: `specs/002-f2-filtros-qualidade/spec.md`

**Input**: Feature specification from `/specs/002-f2-filtros-qualidade/spec.md`

**Locks (Marcos)**: Parkinson = clássica high/low · warm-up insuficiente → NEUTRO automático · short-circuit no 1º filtro que falha (ordem §5.1)

**Depende de**: F1 — saída in-memory em `src/motor/ohlc/` (já em `main`)

## Summary

Implementar o Passo 2 do **Motor** (filtros §3.3 / ordem §5.1): Spread → ADF → TR → Vol Parkinson, sobre a série F1 in-memory. Resultado PASS ou NEUTRO(/temporário) com motivo; short-circuit no primeiro filtro que falha. Sem volume, sem Hurst/OU/GARCH/TA/executor. Estende `src/motor/` pós-F1 — não recria scaffold.

## Technical Context

**Language/Version**: Python (Camada 1 — consolidado §2.3; mesma stack F1 / `pyproject.toml` existente)

**Primary Dependencies (F2)**:
- stdlib + tipagem
- `statsmodels` — ADF (consolidado §12 / refs Python statsmodels)
- F1: `src/motor/ohlc/` (consumo in-memory; **sem** reinventar validação/transform)

**Parkinson (lock)**: estimador clássico high/low (glossário §12: “usando high/low”). Por barra: \(\ln(H_t/L_t)^2\); \(\sigma_n\) = RMS na janela \(n\) com fator \(1/(4\ln 2)\) (definição clássica Parkinson). Razão \(\sigma_{20}/\sigma_{60} \leq 1.5\).

**Storage**: N/A — saída **in-memory** (mesmo lock F1).

**Testing**: `pytest` (já no projeto F1). Fixtures em `tests/fixtures/filters/`.

**Target Platform**: Host do motor (library Python).

**Project Type**: library — Option 1 Spec Kit (single project), extensão do pacote `src/motor/`.

**Constraints**:
- Ordem §5.1: Spread → ADF → TR → Vol rolling
- Warm-up: <20 (spread/TR média), <200 (ADF), <60 (Parkinson 60) → **NEUTRO** automático (não avalia o filtro incompleto)
- Short-circuit: para no 1º filtro que falha; motivo = esse filtro
- weekend_fill do F1: **não** conta como TR observado
- Falha de filtro = NEUTRO (2.4 = NEUTRO temporário 1 barra + `"volatility_spike_detected"`), **não** Abort de formato F1
- Entrada com `gap_dados`/NEUTRO F1 → F2 **não** promove a PASS

**Scale/Scope**: US1–US5 da spec F2; limiares só os do doc (§3.3).

## Constitution Check

Gates §2.2 / fail-safe (sem `constitution.md` versionado):

- Só Motor; zero TA/executor.
- NEUTRO ≠ Abort de formato.
- Escopo fechado: sem §3.4+.

**Gate**: PASS após F1 em `main`.

## Árvore real (pós-F1 em `main`) vs o que F2 adiciona

**Já existe (não recriar Setup de zero)**:

```text
pyproject.toml
src/motor/__init__.py
src/motor/ohlc/
  __init__.py
  validation.py
  sync.py
  transform.py
tests/unit/test_ohlc_*.py
tests/fixtures/ohlc/
specs/001-f1-validacao-ohlc-transform/
```

**F2 adiciona** (paths novos sob o Motor existente):

```text
src/motor/filters/
  __init__.py
  spread.py          # US1
  adf.py             # US2
  tr.py              # US3 (+ weekend_fill)
  parkinson.py       # US4
  pipeline.py        # US5 orquestra + short-circuit

tests/unit/
  test_filter_spread.py
  test_filter_adf.py
  test_filter_tr.py
  test_filter_parkinson.py
  test_filter_pipeline.py

tests/fixtures/filters/
  spread.json
  adf.json
  tr.json
  parkinson.json
  pipeline.json
```

**Dependência de pacote**: acrescentar `statsmodels` em `pyproject.toml` (ADF). Sem `arch`/TradingAgents/MCP.

## Project Structure

### Documentation (this feature)

```text
specs/002-f2-filtros-qualidade/
├── plan.md              # este arquivo
├── spec.md              # Spec (entregue)
└── tasks.md             # Tasks (próximo — NÃO gerado aqui)
```

**Structure Decision**: Novo subpacote `src/motor/filters/` ao lado de `ohlc/` — F1 permanece intacto; F3+ continua em `src/motor/` sem misturar TA.

## O que esta fatia MEXE

| Área | Paths |
|------|--------|
| Spec package | `specs/002-f2-filtros-qualidade/` |
| Filtros | `src/motor/filters/{spread,adf,tr,parkinson,pipeline}.py` |
| Deps | `pyproject.toml` (+ `statsmodels`) |
| Testes | `tests/unit/test_filter_*.py` + `tests/fixtures/filters/` |
| Export | `src/motor/filters/__init__.py` (+ opcional reexport em `src/motor/__init__.py`) |

## O que esta fatia NÃO MEXE

- `src/motor/ohlc/**` (exceto **consumir** API pública F1)
- Hurst / OU / bootstrap θ / GARCH / Z / payload — **F3–F5**
- Backtest / TA / executor / FTMO — **F6–F9**
- `volume` / OHLCV
- UI, broker de produção, lista §9.2
- Paths fora da árvore acima

## Dependências e ordem no pipeline do sistema

```text
[F1 Motor: OHLC + transform]  ← já em main
        ↓
[F2 Filtros §3.3]  ← ESTA FATIA
        ↓
[F3 Regime+OU] → [F4 GARCH+Z] → [F5 Payload]
        ↓
[F6 Backtest] → [F7 TA] → [F8 Executor] → [F9 FTMO]
```

Dentro de F2 (lógica): **Setup deps/pastas → spread → adf → tr → parkinson → pipeline (short-circuit) → testes por US**.

## Onde vive o teste

| US | Independent Test → arquivo |
|----|----------------------------|
| US1 | `tests/unit/test_filter_spread.py` |
| US2 | `tests/unit/test_filter_adf.py` |
| US3 | `tests/unit/test_filter_tr.py` |
| US4 | `tests/unit/test_filter_parkinson.py` |
| US5 | `tests/unit/test_filter_pipeline.py` |
| Fixtures | `tests/fixtures/filters/` |

Runner: `pytest` na raiz (já F1).

## Complexity Tracking

N/A — extensão natural do Motor; `statsmodels` justificado pelo consolidado (ADF), não stack nova inventada.
