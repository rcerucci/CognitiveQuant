# Feature Specification: F2 — Filtros de qualidade

**Feature Branch**: `002-f2-filtros-qualidade`  
**Created**: 2026-09-05  
**Status**: Approved + Addendum 2026-09-06 (ADF em \(r_t\))  
**Input**: Fatia F2 (Marcos) — consolidado v1.2 §3.3 (+ ordem §5.1 / decisão §5.2)  
**Fonte**: Documento consolidado v1.2  
**Depende de**: F1 — saída in-memory (série validada + P_t / X_t / r_t + flags; formato sem `volume`)

**Locks (Marcos)**: Parkinson = clássica high/low · warm-up insuficiente → NEUTRO automático · short-circuit no 1º filtro que falha (ordem §5.1)
**Addendum (2026-09-06)**: ADF de qualidade em **\(r_t\)** (não em \(X_t\)); lags=5 e p&lt;0.05 **inalterados**; spread/TR/Parkinson inalterados; F3 segue em \(X_t\).

## Objetivo

Aplicar os filtros de qualidade (pré-condições) do Passo 2 do motor sobre a série já validada/transformada pelo F1, emitindo **PASS** (prossegue) ou **NEUTRO** (com motivo/log) antes de regime/Hurst e demais passos.

## Fora de escopo

- Revalidação de formato OHLC / transform mid→log→r (F1)
- `volume` / OHLCV (continua fora; formato F1)
- Regime Hurst, OU, bootstrap θ, GARCH, Z/percentil, confirmação, força, payload (§3.4–3.11)
- Bootstrap θ e Skewness como filtros de §5 (são penalização/downstream — **não** Passo 2.1–2.4)
- TradingAgents, executor, paper/demo, FTMO
- UI / onboarding / marketing
- Lista de instrumentos §9.2 (ainda depois)
- Fonte/broker OHLC de produção
- Inventar p-crítico / mudar janela 200 / lags=5
- ADF no Hurst / mudar cortes 0.45/0.55 (F3)
- Reabrir F3–F6 além do consumo de PASS

## User Scenarios & Testing *(mandatory)*

### US1 — Filtro de spread anômalo (Priority: P1)

Como pipeline do motor, quero rejeitar barras com spread acima de 2× a média de 20 barras, marcando NEUTRO, para não operar com custo de execução anômalo.

**Why this priority**: Primeiro filtro barato na ordem §5.1; falha → NEUTRO.

**Independent Test**: Série com spread normal vs spike > 2× média(20); assert NEUTRO + motivo; sem ADF/TR/vol.

**Acceptance Scenarios**:

1. **Given** `Spread_t = Ask_t - Bid_t` e média dos últimos 20 spreads, **When** `Spread_t ≤ 2 × média(20)`, **Then** o filtro de spread passa.
2. **Given** `Spread_t > 2 × média(20)`, **When** o filtro roda, **Then** status **NEUTRO** (não Abort de formato).

---

### US2 — Filtro ADF de estacionariedade em \(r_t\) (Priority: P1)

Como pipeline do motor, quero exigir ADF com p < 0.05 na janela de **retornos** `r_{t-199:t}` (lags=5), senão NEUTRO — qualidade sobre estacionariedade dos **retornos** (consolidado), não do nível \(X_t\) (~I(1) em FX M30).

**Why this priority**: Segundo na ordem §5.1; intent do addendum 2026-09-06 (ADF(\(X\)) matava ~81% das janelas EUR/USD antes do regime).

**Independent Test** (seed=42): série preço ~RW (log-preço I(1), retorno ~branco) → ADF(\(X\)) tipicamente p≥0.05 e ADF(\(r\)) p&lt;0.05; o filtro **passa** no segundo; isolado dos outros filtros F2.

**Acceptance Scenarios**:

1. **Given** janela de **200 retornos** `r_{t-199:t}` com `r_t = X_t - X_{t-1}` e ADF lags=5, **When** `p < 0.05`, **Then** o filtro ADF passa.
2. **Given** a mesma especificação ADF em \(r\), **When** `p ≥ 0.05`, **Then** status **NEUTRO**.
3. **Given** primeira barra da série sem retorno anterior, **When** ADF é solicitado, **Then** **NEUTRO** / skip (sem inventar \(r_0\)).

---

### US3 — Filtro TR anômalo (Priority: P1)

Como pipeline do motor, quero marcar NEUTRO quando o True Range excede 2.5× a média(20), sem usar barras de weekend fill do F1 como TR “observado”.

**Why this priority**: Terceiro na ordem §5.1; protege gaps/spikes de amplitude.

**Independent Test**: Barra com TR normal vs TR > 2.5× média(20); barra com flag weekend_fill do F1 não entra como observação de TR; assert NEUTRO nos casos de falha.

**Acceptance Scenarios**:

1. **Given** `TR_t = max(H-L, |H-C_{t-1}|, |L-C_{t-1}|)` e média(20) de TR, **When** `TR_t ≤ 2.5 × média(20)`, **Then** o filtro TR passa.
2. **Given** `TR_t > 2.5 × média(20)`, **When** o filtro roda, **Then** status **NEUTRO**.
3. **Given** barra marcada weekend_fill pelo F1, **When** o TR é calculado, **Then** essa barra **não** conta como TR observado preenchido (regra F1/§3.2.1: não preenche TR).

---

### US4 — Filtro de volatilidade rolling Parkinson (Priority: P1)

Como pipeline do motor, quero pausar 1 barra (NEUTRO temporário) quando `σ_20 / σ_60 > 1.5` (Parkinson clássica high/low), com log `"volatility_spike_detected"`.

**Why this priority**: Quarto na ordem §5.1; spike volátil — NEUTRO temporário, não permanente.

**Independent Test**: Razão ≤ 1.5 → PASS; razão > 1.5 → NEUTRO temporário (1 barra) + log literal; sem invocar Hurst/GARCH.

**Acceptance Scenarios**:

1. **Given** Parkinson clássica `σ_20` e `σ_60`, **When** `σ_20 / σ_60 ≤ 1.5`, **Then** o filtro de vol passa.
2. **Given** `σ_20 / σ_60 > 1.5`, **When** o filtro roda, **Then** **NEUTRO temporário (1 barra)** e log `"volatility_spike_detected"`.

---

### US5 — Orquestra filtros na ordem do doc (Priority: P2)

Como pipeline do motor, quero avaliar 2.1→2.2→2.3→2.4 na ordem §5.1 com **short-circuit** no primeiro filtro que falha, e expor resultado in-memory (PASS ou NEUTRO + quais filtros falharam), consumindo só a saída F1.

**Why this priority**: Integra os quatro filtros; valor composto após US1–US4.

**Independent Test**: Fixture onde só o 2º filtro falha → NEUTRO com motivo ADF (sem exigir cálculo dos posteriores); fixture all-pass → PASS; ordem de avaliação respeitada.

**Acceptance Scenarios**:

1. **Given** série F1 válida, **When** todos os filtros 2.1–2.4 passam, **Then** resultado **PASS** (elegível ao Passo 3 / F3).
2. **Given** falha em qualquer um de 2.1–2.3, **When** a orquestra roda, **Then** **NEUTRO** com identificação do filtro (short-circuit).
3. **Given** só 2.4 falha, **When** a orquestra roda, **Then** **NEUTRO temporário (1 barra)** + `"volatility_spike_detected"`.

### Edge Cases

- Histórico insuficiente (&lt;20 spread/TR, &lt;200 ADF, &lt;60 Parkinson 60) → **NEUTRO** automático (lock Marcos).
- Entrada ainda com status NEUTRO/`gap_dados` do F1 → F2 MUST NOT promover a PASS; permanece não elegível.
- NaN/inf em bid/ask/OHLC após F1 → não esperado (F1 Abort).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Sistema MUST consumir a saída in-memory do F1 (barra/série validada com bid/ask, OHLC, `X_t`, flags; **sem** `volume`).
- **FR-002**: Sistema MUST aplicar filtro Spread: `Ask_t - Bid_t ≤ 2 × média(20)`; falha → NEUTRO; warm-up &lt;20 → NEUTRO.
- **FR-003**: Sistema MUST aplicar ADF em **`r_{t-199:t}`** (`r_t = X_t - X_{t-1}`) com lags=5; passagem `p < 0.05`; falha → NEUTRO; warm-up &lt;200 retornos → NEUTRO; sem \(r\) na 1ª barra → NEUTRO/skip. MUST NOT usar \(X_t\) como série do ADF de qualidade.
- **FR-004**: Sistema MUST aplicar TR: `TR_t = max(H-L, |H-C_{t-1}|, |L-C_{t-1}|)` e `TR_t ≤ 2.5 × média(20)`; falha → NEUTRO; warm-up &lt;20 → NEUTRO.
- **FR-005**: Sistema MUST NOT tratar barras weekend_fill do F1 como TR observado preenchido.
- **FR-006**: Sistema MUST aplicar vol rolling Parkinson **clássica high/low** `σ_20 / σ_60 ≤ 1.5`; falha → NEUTRO temporário (1 barra) + log `"volatility_spike_detected"`; warm-up &lt;60 → NEUTRO.
- **FR-007**: Sistema MUST avaliar filtros na ordem §5.1: Spread → ADF → TR → Vol rolling, com **short-circuit** no primeiro que falha.
- **FR-008**: Saída MUST ser **in-memory** (status PASS/NEUTRO[+temporário], motivos/logs, métricas dos filtros calculados até o short-circuit); sem schema/arquivo intermediário obrigatório.
- **FR-009**: Falha de filtro MUST ser NEUTRO (ou NEUTRO temporário no 2.4) — **não** é o Abort de formato do F1.
- **FR-010**: F2 MUST NOT importar nem executar Hurst/OU/GARCH/payload/TA/executor.

### Key Entities

- **ResultadoFiltros**: status (`PASS` | `NEUTRO` | `NEUTRO_TEMPORARIO`), filtros avaliados, motivos/logs, valores (spread, p_ADF, TR, razão σ20/σ60) quando calculados.
- **SérieF1**: entrada — timestamps UTC, OHLC, bid/ask, `X_t`, flags (`gap_dados`, `weekend_fill`, …).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Independent Tests US1–US4: 100% das falhas de limiar do doc produzem NEUTRO (ou NEUTRO temporário + log no 2.4) sem falso PASS.
- **SC-002**: Ordem de avaliação nos testes de US5 segue Spread → ADF → TR → Vol com short-circuit.
- **SC-003**: Nenhum teste de F2 importa módulos de §3.4+ / TA / executor (escopo fechado).
- **SC-004**: Barras `weekend_fill` não contribuem TR observado nos testes de US3.
- **SC-005** (addendum): fixture RW seed=42 — filtro ADF passa em \(r\) e **não** exige passagem em \(X\); spread/TR/Parkinson inalterados nos testes.

## Riscos

- ADF lags=5 pode ser conservador (nota do doc); falso NEUTRO alto — aceito nesta fatia (Hurst é regime primário depois).

## DIVERGÊNCIA

- Nenhuma vs F1: formato/saída in-memory.
- **Addendum vs código vigente:** implementação atual ADF(\(X\)) diverge do intent pós-addendum — hotfix em `filters/adf.py` / pipeline (Plan/Tasks).
- Paths F2: `src/motor/filters/` — plan hotfix amarra.

## NEEDS CLARIFICATION

Nenhum aberto neste addendum.

## Decisões — Addendum ADF (2026-09-06)

1. Série do ADF de qualidade = **\(r_t\)** (não \(X_t\)).
2. Janela = 200 retornos; lags=5; p&lt;0.05 **iguais**.
3. Path: `src/motor/filters/adf.py` (+ pipeline) — Plan amarra; Spec não mexe em F3+.
4. F3 continua estimando regime/OU em **\(X_t\)**.

## Locks anteriores (inalterados)

1. Parkinson → **clássica high/low** (fator \(1/(4\ln 2)\); razão σ20/σ60).
2. Warm-up → **NEUTRO automático** se série insuficiente.
3. Short-circuit → **sim**, ordem §5.1.

## Assumptions

- Locks F1 permanecem: UTC-only; saída in-memory; sem lista §9.2; sem `volume`.
- “Aborta?” em §5.1 para estes quatro filtros = NEUTRO (temporário no 2.4), não Abort de formato.
- Bootstrap θ / Skewness da tabela §5.2 **não** entram em F2 (só 2.1–2.4).
- Fixtures sintéticas bastam para Independent Tests.
