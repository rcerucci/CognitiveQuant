# Implementation Plan: F1 — Validação OHLC + transform

**Branch**: `001-f1-validacao-ohlc-transform` | **Date**: 2026-09-05 | **Spec**: `specs/001-f1-validacao-ohlc-transform/spec.md`

**Input**: Feature specification from `/specs/001-f1-validacao-ohlc-transform/spec.md`

**Locks (Marcos)**: NTP = só UTC nos timestamps · saída in-memory · US3 sem lista §9.2 · Setup criando `src/`/`tests/`

## Summary

Implementar a entrada confiável do **Motor** (Camada 1): validar barras OHLC M30 (+ bid/ask) e calcular mid → log-preço → retorno log in-memory, com abort duro e logs literais do consolidado v1.2 §§3.1–3.2.1 / 3.12.1. Repo hoje é scaffold; esta fatia cria a árvore mínima Python + testes unitários por US. Não avança filtros (§3.3), TA nem executor.

## Technical Context

**Language/Version**: Python (Camada 1 = “Python puro”, consolidado §2.3) — **versão exata não pinada no repo**; Setup pode fixar runtime no `pyproject.toml` sem mudar stack.

**Primary Dependencies (F1)**: stdlib (`math`, `datetime`, tipagem). Sem `arch` / `statsmodels` / TradingAgents / MCP nesta fatia.

**Storage**: N/A — saída **in-memory** (API/módulo); sem schema/arquivo intermediário obrigatório.

**Testing**: `pytest` (consolidado §3.12.3 — unitário / abort-edge). Fixtures sintéticas sob `tests/fixtures/`.

**Target Platform**: Host do motor (Linux/local), library Python — não web/UI.

**Project Type**: library (motor quant) — Option 1 Spec Kit (single project).

**Performance Goals**: N/A nesta fatia (pré-requisito de corretude, não throughput).

**Constraints**: Abort imediato sem retry/bypass (§3.2.1 / §8.6); timestamps UTC-only; gap ≤4 interpola, gap >4 → `gap_dados` + NEUTRO; weekend forward-fill de preços **sem** preencher TR (flag para F2).

**Scale/Scope**: F1 = US1–US4 da spec; N instrumentos genéricos na sync (lista §9.2 **depois**).

## Constitution Check

*Sem `constitution.md` no repo scaffold.* Gates alinhados ao consolidado §2.2 / fail-safe:

- Separação de camadas: só Motor; zero TA/executor.
- Fail-safe: Abort + log literal em falha de validação.
- Determinismo de seed/LLM (§3.12.2): **fora de F1** (spec).

**Gate**: PASS para iniciar implementação de F1 após Setup.

## Árvore real (hoje) vs Setup

**Hoje (`rcerucci/CognitiveQuant` `main`)**:

```text
.gitignore
README.md
specs/.gitkeep
```

**DIVERGÊNCIA resolvida (Marcos)**: Setup **cria** `src/` e `tests/` (e pasta da feature sob `specs/`). Paths abaixo são **novos** — não existiam no scaffold; Tasks só usa estes.

## Project Structure

### Documentation (this feature)

```text
specs/001-f1-validacao-ohlc-transform/
├── plan.md              # este arquivo
├── spec.md              # Spec (já entregue)
└── tasks.md             # Tasks (próximo no pipeline — NÃO gerado aqui)
```

### Source Code (após Setup desta fatia)

```text
src/
└── motor/
    ├── __init__.py
    └── ohlc/
        ├── __init__.py
        ├── validation.py    # US1 formato/integridade + US2 ordem/gaps/weekend
        ├── sync.py          # US3 merge outer + preenchimento linear
        └── transform.py     # US4 P_t, X_t, r_t

tests/
├── unit/
│   ├── test_ohlc_format_integrity.py   # US1 Independent Test
│   ├── test_ohlc_order_gaps.py         # US2 Independent Test
│   ├── test_ohlc_sync.py               # US3 Independent Test
│   └── test_ohlc_transform.py          # US4 Independent Test
└── fixtures/
    └── ohlc/                           # barras válidas/inválidas, gaps, multi-instrumento

pyproject.toml   # Setup: projeto Python + pytest (stack do doc)
```

**Structure Decision**: Option 1 (single project). Pacote `src/motor/ohlc/` isola Passo 1 do motor; fatias F2+ estendem `src/motor/` sem misturar TA/executor. Testes unitários espelham Independent Tests da spec.

## O que esta fatia MEXE

| Área | Paths / artefato |
|------|------------------|
| Setup árvore | criar `src/motor/ohlc/`, `tests/unit/`, `tests/fixtures/ohlc/`, `pyproject.toml` |
| Spec package | `specs/001-f1-validacao-ohlc-transform/` (spec + plan; tasks depois) |
| Validação | `src/motor/ohlc/validation.py` |
| Sync multi-instrumento | `src/motor/ohlc/sync.py` (N genérico; sem lista §9.2) |
| Transform | `src/motor/ohlc/transform.py` (in-memory) |
| Testes | `tests/unit/test_ohlc_*.py` + fixtures |

## O que esta fatia NÃO MEXE

- Filtros §3.3 (spread, ADF, TR, vol rolling) — **F2**
- Hurst / OU / bootstrap θ / GARCH / Z / percentil / confirmação / força / payload — **F3–F5**
- Backtest motor-only — **F6**
- TradingAgents adapter — **F7**
- Executor / paper / MCP — **F8**
- FTMO / portfólio / hard-stop — **F9**
- UI, onboarding, marketing
- Fonte/broker OHLC de produção
- Qualquer path fora da árvore Setup acima

## Dependências e ordem no pipeline do sistema

```text
[F1 Motor: OHLC validate + transform]  ← ESTA FATIA
        ↓
[F2 Filtros] → [F3 Regime+OU] → [F4 GARCH+Z] → [F5 Payload]
        ↓
[F6 Backtest motor-only]
        ↓
[F7 TradingAgents] → [F8 Executor/paper] → [F9 FTMO]
```

Dentro de F1 (lógica, não tasks): **Setup → validation (US1+US2) → sync (US3) → transform (US4) → testes por US**.

## Onde vive o teste

| US | Independent Test → arquivo |
|----|----------------------------|
| US1 | `tests/unit/test_ohlc_format_integrity.py` |
| US2 | `tests/unit/test_ohlc_order_gaps.py` |
| US3 | `tests/unit/test_ohlc_sync.py` |
| US4 | `tests/unit/test_ohlc_transform.py` |
| Fixtures | `tests/fixtures/ohlc/` |

Runner: `pytest` na raiz do repo (após Setup).

## Complexity Tracking

N/A — sem constitution file e sem violações a justificar; Setup de árvore é decisão explícita do Marcos para fechar a DIVERGÊNCIA scaffold.
