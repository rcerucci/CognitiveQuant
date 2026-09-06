# Implementation Plan: F6 — Backtest motor-only

**Branch**: `feature/006-f6-backtest-motor-only` (hotfix US6) | **Date**: 2026-09-06 | **Spec**: `specs/006-f6-backtest-motor-only/spec.md`

**Input**: Feature specification + **Addendum US6** (hotfix aceite §10.1)

**Locks (Marcos)**: fonte = **CSV/parquet real** sob `data/ohlc/` · PnL **(a)** mid-close → `validade_ate`/τ · **sem flip** · trigger = **ALTA|MÉDIA** (≥ 0.60) · só-ALTA = diagnóstico · Sharpe = equity **diária**, Rf=0, **×√252** · gate **≥7/10** Sharpe **> 0.5** · `seed=42` · **aceite §10.1 = run offline US6 + artefato** (CI fixture ≠ fechamento)

**Depende de**: aparelho F6 (T001–T027) em `src/motor/backtest/` + F5 em `main` — **não** reabrir F5 · **não** iniciar F7 até existir `reports/f6_backtest.json`

**NC aberto (Spec)**: Marcos **confirma o provider** abaixo **antes** do coder implementar o fetch em `scripts/`.

---

## Summary

Fechar o buraco §10.1: além do aparelho (US1–US5), executar o **experimento offline** (US6) em `data/ohlc/` (10 × §9.2), gravar `reports/f6_backtest.json` (métricas + por ano + gate 7/10 + só-ALTA), FAIL se pasta vazia/INSUFICIENTE. Dataset **fora** do git; run **não** é CI; fetch **fora** de `src/motor/`.

## Technical Context

**Language/Version**: Python ≥3.11 (stack F6 já em branch: pandas, pyarrow, …)

**Primary Dependencies (hotfix US6)**:
- Reuso: `motor.backtest.{loader,runner,pnl,metrics,report,pipeline}`
- **Sem** SDK de provider em `src/motor/`
- Fetch (após confirmação Marcos): deps do provider **só** em `scripts/` / optional-deps `fetch` — **não** no runtime do motor

**Storage**:
- Input: `data/ohlc/{canonical}.parquet` (preferência) ou `.csv`
- Output: `reports/f6_backtest.json`
- Ambos **gitignore** (exceto `data/ohlc/.gitkeep`); dataset 5 anos **não** entra no git

**Testing**:
- CI: FAIL explícito se `data/ohlc/` vazio; schema do artefato com fixture mínima — **sem** 5 anos no CI
- Aceite §10.1: run local offline com dataset real → artefato + gate factual

**Constraints (US6)**:
- Run **não** é job CI obrigatório com 5 anos
- Equity diária = **último equity do dia UTC** (agregação M30→diário; sem mudar limiares)
- Instrumento INSUFICIENTE (série curta / só warm-up) → **não** conta Sharpe > 0.5; run FAIL se incompleto demais para o gate
- F7 bloqueada até artefato US6 existir

---

## Provider proposto (NC — Marcos confirma antes do fetch)

**Proposta única: QuantConnect** (histórico multi-asset → materializa parquet local).

| Motivo | Detalhe |
|--------|---------|
| Cobertura | FX + índices/commodities do §9.2 num único pipeline de dados |
| Isolamento | SDK/API **somente** em `scripts/`; loader F6 continua **só** arquivo local |
| Alternativa (se Marcos rejeitar QC) | **OANDA** — forte em FX/XAU; confirmar cobertura de US500/GER30/JP225/USOIL/NAS100 na conta dele |

**Até Marcos confirmar:** coder **não** implementa fetch; cópia manual dos 10 arquivos canônicos em `data/ohlc/` é suficiente para o run.

---

## Nomes canônicos dos 10 arquivos (`data/ohlc/`)

Regra = loader já em branch: `instrumento.replace("/", "_").lower()` + extensão.

| §9.2 | Arquivo canônico (preferir parquet) |
|------|-------------------------------------|
| EUR/USD | `eur_usd.parquet` |
| GBP/JPY | `gbp_jpy.parquet` |
| USD/CAD | `usd_cad.parquet` |
| AUD/NZD | `aud_nzd.parquet` |
| US500 | `us500.parquet` |
| GER30 | `ger30.parquet` |
| JP225 | `jp225.parquet` |
| XAU/USD | `xau_usd.parquet` |
| USOIL | `usoil.parquet` |
| NAS100 | `nas100.parquet` |

CSV aceito com o mesmo stem (`.csv`) se parquet ausente — comportamento atual do loader.

Formato barras: F1 (`timestamp`, `open`, `high`, `low`, `close`, `bid`, `ask`); timeframe **M30**; horizonte alvo **~5 anos**.

---

## Árvore real (branch feature/006) vs hotfix US6

**Já existe** (não recriar aparelho):

```text
src/motor/backtest/{__init__,loader,runner,pnl,metrics,report,pipeline}.py
data/ohlc/.gitkeep
tests/unit/test_backtest_*.py
tests/fixtures/backtest/
specs/006-f6-backtest-motor-only/{spec,plan,tasks}.md
```

**Hotfix US6 adiciona**:

```text
src/motor/backtest/cli.py     # entrypoint run offline → data/ohlc/ → reports/
reports/.gitkeep             # path do artefato (conteúdo gitignored)
reports/f6_backtest.json     # artefato local (NÃO no git)

scripts/fetch_ohlc.py        # SÓ após Marcos confirmar provider
                             # (ou cópia manual — skip fetch)

.gitignore                   # ver bloco abaixo
pyproject.toml               # console script `f6-backtest` → cli

tests/unit/test_backtest_cli.py          # FAIL pasta vazia / schema artefato
tests/fixtures/backtest/run_empty/      # harness incompleto (opcional)
```

### `.gitignore` (DIVERGÊNCIA a corrigir)

Hoje `scripts/` está **inteiro** no `.gitignore` de `main` — conflita com Spec (fetch versionado em `scripts/`). Hotfix:

```gitignore
# Dataset e relatório do experimento (não versionar)
data/ohlc/*
!data/ohlc/.gitkeep
reports/*
!reports/.gitkeep

# Scripts: versionar fetch; não ignorar a pasta inteira
# (remover a linha `scripts/` do ignore atual)
```

---

## CLI / comando (amarrado)

```text
f6-backtest --data-dir data/ohlc --out reports/f6_backtest.json
```

Equiv. módulo: `python -m motor.backtest.cli --data-dir data/ohlc --out reports/f6_backtest.json`

- Exit **≠ 0** se: pasta vazia / só `.gitkeep` / faltam canônicos / INSUFICIENTE demais para avaliar gate
- Exit **0** com artefato gravado quando os 10 arquivos existem e o pipeline corre (veredito gate PASS|FAIL **factual** no JSON — FAIL de gate ≠ crash se dados ok)

## Artefato `reports/f6_backtest.json` (schema mínimo)

- `gate`: `{ pass_count, threshold: 0.5, min_instruments: 7, veredito: PASS|FAIL }`
- `instruments[]`: símbolo, Sharpe, WR, PF, MaxDD, trigger_rate, tau_median, alta_only_rate (diagnóstico), status (OK|INSUFICIENTE), `by_year[]` quando couber
- `meta`: data_dir, seed=42, timeframe=M30, gerado_em

## O que esta fatia / hotfix MEXE

| Área | Paths |
|------|--------|
| Spec package | `specs/006-f6-backtest-motor-only/` (spec US6 + este plan + tasks T028+) |
| CLI | `src/motor/backtest/cli.py` + entry em `pyproject.toml` |
| Reports | `reports/.gitkeep` (+ artefato local) |
| Fetch (pós-confirmação) | `scripts/fetch_ohlc.py` |
| Ignore | `.gitignore` (data/ohlc content, reports, liberar `scripts/`) |
| Testes US6 | `tests/unit/test_backtest_cli.py` |

## O que NÃO MEXE

- `src/motor/{ohlc,filters,regime,vol,signal}/**` (F5 fechado)
- Provider SDK dentro de `src/motor/`
- TradingAgents / F7 / Executor F8 / FTMO F9
- Reimplementar loader/runner/pnl/metrics/report (só consumir + CLI + persistência do relatório)
- Exigir dataset 5 anos no git/CI

## Ordem pipeline hotfix

```text
Setup ignore/reports → CLI → checklist 10 arquivos → persist report
  → (Marcos confirma provider) → scripts/fetch_ohlc.py
  → run offline local → artefato → Tasks T028+
```

Dentro do Spec Kit: **não** começar F7 sem `reports/f6_backtest.json`.

## Onde vive o teste (US6)

| Item | Path |
|------|------|
| Independent Test CI (FAIL vazio + schema) | `tests/unit/test_backtest_cli.py` |
| Aceite offline §10.1 | run local + `reports/f6_backtest.json` (fora do CI) |

## Complexity Tracking

- Provider QC proposto — **aguarda confirmação Marcos** (NC Spec).
- `.gitignore` `scripts/` — correção obrigatória para versionar fetch sem inventar outra pasta.
