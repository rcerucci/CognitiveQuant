# Implementation Plan: F6 — Backtest motor-only

**Branch**: `006-f6-backtest-motor-only` | **Date**: 2026-09-05 | **Spec**: `specs/006-f6-backtest-motor-only/spec.md`

**Input**: Feature specification from `/specs/006-f6-backtest-motor-only/spec.md`

**Locks (Marcos)**: fonte = **CSV/parquet real** (provider = adapter **fora**) · PnL **(a)** entry mid-close · exit `validade_ate`/τ · **sem flip** · trigger = **ALTA|MÉDIA** (força ≥ 0.60) · só-ALTA = diagnóstico F7 · Sharpe = equity **diária**, Rf=0, **×√252** · gate **≥7/10** com Sharpe **> 0.5** · `seed=42` se houver aleatoriedade

**Depende de**: F5 em `main` (`415a7bf`) — `src/motor/{ohlc,filters,regime,vol,signal}/` (pipeline F1→F5)

## Summary

Implementar backtest histórico **motor-only** (§10.1): carregar OHLC M30 real (CSV/parquet) dos **10** instrumentos §9.2, rodar F1→F5 barra a barra sem TA/MCP, simular trades (entry mid-close → exit τ/`validade_ate`, sem flip), métricas §10.1 + Sharpe diário ×√252, gate 7/10, relatório in-memory. Não reabre F5.

## Technical Context

**Language/Version**: Python ≥3.11 (Camada 1 — consolidado §2.3; stack F1–F5 / `pyproject.toml` em `main`)

**Primary Dependencies (F6)**:
- **Novas**: `pandas` (+ `pyarrow` se parquet) — leitura CSV/parquet materializado (`pyproject.toml` hoje: `statsmodels`, `pykalman`, `numpy`, `scipy`, `arch` — **sem** pandas)
- Consumo: APIs públicas F1–F5 (`run_f5_pipeline` / `F5Pipeline`, ohlc/filters/regime/vol) — **sem** reimplementar
- **Sem** SDKs Polygon/OANDA/QC/Broker; **sem** TradingAgents/MCP

**Storage**: arquivos **já materializados** em `data/ohlc/` (runtime; **não existe em `main` hoje** — Setup F6 cria o path) + fixtures em `tests/fixtures/backtest/`. Sem download de provider no runner/CI. Dataset 5 anos pode ficar fora do git (gitignore/local); CI usa fixtures pequenas.

**Testing**: `pytest` + fixtures CSV/parquet **pequenas** (sem rede). Gate 7/10 com dataset 5 anos = execução offline com dados reais (não inventar preços sintéticos como substituto do gate).

**Target Platform**: Host do motor (library / CLI leve opcional).

**Project Type**: library — Option 1 Spec Kit; subpacote `src/motor/backtest/`.

**Constraints**:
- Universo §9.2 (exato): EUR/USD, GBP/JPY, USD/CAD, AUD/NZD, US500, GER30, JP225, XAU/USD, USOIL, NAS100
- Horizonte doc: **5 anos** M30
- Trigger F6: `direcao` ∈ {LONG, SHORT} e `confianca` ∈ {ALTA, MÉDIA} (força ≥ 0.60)
- Entry = mid `(bid+ask)/2` no close da barra do sinal; exit = mid-close na barra de `validade_ate` / `meia_vida_barras`; sem flip
- Custo Zero §10.1 — sem inventar spread/comissão além do mid
- Sharpe: retornos de **equity diária**, Rf=0, ×√252
- Alvos reportados: Sharpe > 0.5; WR > 45%; PF > 1.3; MaxDD < 15%; taxa triggers 5–15%; mediana τ 3–8 barras
- Gate: `count(Sharpe > 0.5) ≥ 7` → PASS global
- Truncamento: exit além do fim da série → última barra + log
- Zero triggers → não inventar Sharpe; instrumento falha gate

**Scale/Scope**: US1–US5 da spec F6.

## Constitution Check

- Só motor puro; zero TA/executor/MCP.
- Não reabre F5 / não muda limiares de sinal.
- Provider adapter fora (não acoplar API no runner).

**Gate**: PASS com F5 `signal/` em `main`.

## Árvore real (`origin/main` pós-F5) vs o que F6 adiciona

**Já existe** (não recriar):

```text
pyproject.toml
src/motor/__init__.py
src/motor/ohlc/          # F1
src/motor/filters/       # F2
src/motor/regime/        # F3
src/motor/vol/           # F4
src/motor/signal/        # F5
tests/unit/test_{ohlc,filter,regime,vol,signal}_*.py
tests/fixtures/{ohlc,filters,regime,vol,signal}/
specs/001-…/ … /005-…/
```

**Não existe em `main`**: `data/`, `src/motor/backtest/`, `tests/fixtures/backtest/`, deps `pandas`/`pyarrow`.

**F6 adiciona**:

```text
src/motor/backtest/
  __init__.py
  loader.py          # US2 — CSV/parquet → barras F1; universo §9.2
  runner.py          # US1 — barra-a-barra F1→F5
  pnl.py             # US3 — entry/exit/sem flip
  metrics.py         # US4 — Sharpe/WR/PF/MaxDD/trigger_rate/mediana τ
  report.py          # US5 — gate 7/10 + relatório in-memory
  pipeline.py        # orquestra loader→runner→pnl→metrics→report

data/ohlc/                 # path Setup (materializado; provider fora)
  # 10 arquivos §9.2 (csv|parquet); nomes canônicos a fixar no loader

tests/unit/
  test_backtest_loader.py
  test_backtest_runner.py
  test_backtest_pnl.py
  test_backtest_metrics.py
  test_backtest_report.py
  test_backtest_pipeline.py

tests/fixtures/backtest/
  sample_bars.csv / .parquet
  equity_trades.json
  sharpe_table.json

specs/006-f6-backtest-motor-only/
  plan.md / spec.md / tasks.md
```

**Deps**: acrescentar `pandas` (+ `pyarrow` se parquet) em `pyproject.toml`. Sem SDKs de broker/Polygon/OANDA/QC.

## Project Structure

### Documentation (this feature)

```text
specs/006-f6-backtest-motor-only/
├── plan.md              # este arquivo
├── spec.md              # Spec (aprovada)
└── tasks.md             # Tasks (próximo — NÃO gerado aqui)
```

**Structure Decision**: `src/motor/backtest/` ao lado das camadas F1–F5 — validação §10.1 sem misturar TA (F7) nem executor (F8).

## O que esta fatia MEXE

| Área | Paths |
|------|--------|
| Spec package | `specs/006-f6-backtest-motor-only/` |
| Backtest | `src/motor/backtest/{loader,runner,pnl,metrics,report,pipeline}.py` |
| Dados | `data/ohlc/` (Setup novo) + `tests/fixtures/backtest/` |
| Deps | `pyproject.toml` (+ pandas/pyarrow) |
| Testes | `tests/unit/test_backtest_*.py` |
| Export | `src/motor/backtest/__init__.py` (+ reexport opcional em `src/motor/__init__.py`) |

## O que esta fatia NÃO MEXE

- `src/motor/{ohlc,filters,regime,vol,signal}/**` (exceto **consumir**)
- Adapter Polygon/OANDA/QC/Broker — **fora**
- TradingAgents — **F7**
- Executor / paper / MCP — **F8**
- FTMO challenge / hard-stop — **F9**
- UI, productizar, `volume`
- Paths fora da árvore acima

## Dependências e ordem no pipeline do sistema

```text
[F1]→[F2]→[F3]→[F4]→[F5 signal]  ← em main
        ↓
[F6 backtest motor-only]  ← ESTA FATIA
        ↓
[F7 TA] → [F8 Executor] → [F9 FTMO]
```

Dentro de F6: **Setup → loader → runner → pnl → metrics → report/pipeline → testes por US**.

## Onde vive o teste

| US | Independent Test → arquivo |
|----|----------------------------|
| US1 | `tests/unit/test_backtest_runner.py` |
| US2 | `tests/unit/test_backtest_loader.py` |
| US3 | `tests/unit/test_backtest_pnl.py` |
| US4 | `tests/unit/test_backtest_metrics.py` |
| US5 | `tests/unit/test_backtest_report.py` (+ pipeline) |
| Fixtures | `tests/fixtures/backtest/` |

Runner: `pytest` na raiz.

## Complexity Tracking

N/A — pandas/pyarrow só para I/O de série (não estavam em `main`); locks Marcos fecham PnL/Sharpe/fonte; sem stack inventada fora do ecossistema Python do motor.
