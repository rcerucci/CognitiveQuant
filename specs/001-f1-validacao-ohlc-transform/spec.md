# Feature Specification: F1 — Validação OHLC + transform

**Feature Branch**: `001-f1-validacao-ohlc-transform`  
**Created**: 2026-09-05  
**Status**: Approved  
**Input**: Fatia F1 (Marcos) — consolidado v1.2 §§3.1–3.2.1 / 3.12.1  
**Fonte**: Documento consolidado v1.2 (revisão ponto a ponto)

**Locks (Marcos)**: NTP = só UTC nos timestamps · saída in-memory · US3 sem lista §9.2 · Setup criando `src/`/`tests/`

## Objetivo

Garantir entrada M30 confiável: validar barras OHLC (+ bid/ask) e produzir a transformação mid → log-preço → retorno log, como pré-requisito do motor (antes dos filtros §3.3).

## Fora de escopo

- Filtros de qualidade (§3.3: spread, ADF, TR, vol rolling)
- Regime Hurst, OU, bootstrap θ, GARCH, Z/percentil, confirmação, força, payload (§3.4–3.11)
- Determinismo seed/LLM, fixtures de motor/TA, rollover (§3.12.2–3.12.4) — fora desta fatia
- TradingAgents, executor, paper/demo, FTMO
- UI, onboarding, marketing
- Fonte/broker concreto de OHLC em produção (não definido nesta fatia)
- Lista de instrumentos §9.2 (fica para fatias posteriores)
- Check operacional de NTP (F1 valida apenas timezone UTC nos timestamps)

## User Scenarios & Testing *(mandatory)*

### US1 — Validar formato e integridade da barra (Priority: P1)

Como pipeline do motor, quero rejeitar barras malformadas ou inconsistentes com abort imediato e log explícito, para não alimentar passos seguintes com lixo.

**Why this priority**: Sem abort duro na entrada, todo o motor fica inválido (§3.2.1 nota: sem retry/bypass).

**Independent Test**: Suite unitária com fixtures de barras válidas vs inválidas; assert de abort + código de log; sem depender de filtros/Hurst/GARCH.

**Acceptance Scenarios**:

1. **Given** uma barra no formato JSON `[timestamp_UTC, open, high, low, close, bid, ask]` com timestamps UTC, **When** a validação roda, **Then** a barra é aceita para transformação.
2. **Given** payload fora desse formato, **When** a validação roda, **Then** ocorre Abort e log `"format_invalido"`.
3. **Given** `high < max(open, close)` ou `low > min(open, close)`, **When** a validação roda, **Then** Abort e log `"integridade_preco_invalida"`.
4. **Given** timestamps fora de UTC (conforme regra do doc), **When** a validação roda, **Then** Abort.

---

### US2 — Ordem temporal e gaps (Priority: P1)

Como pipeline do motor, quero série temporal ordenada, sem duplicatas, com tratamento de missing bars e weekend gaps conforme o doc, para a transformação operar sobre série alinhada.

**Why this priority**: Ordem/gaps inválidos corrompem retornos e os passos seguintes.

**Independent Test**: Fixtures com duplicata, ordem invertida, gap de 1–4 barras, gap > 4, e weekend gap; assert abort vs interpolação vs NEUTRO/`gap_dados` vs forward fill.

**Acceptance Scenarios**:

1. **Given** timestamps não crescentes ou duplicados, **When** a validação roda, **Then** Abort e log `"ordem_temporal_invalida"`.
2. **Given** missing bars com gap ≤ 4 barras, **When** a validação roda, **Then** interpolação linear entre barra anterior e posterior preenche o buraco.
3. **Given** gap > 4 barras, **When** a validação roda, **Then** marca `"gap_dados"` e status **NEUTRO** temporário (não segue como série “limpa”).
4. **Given** weekend gap, **When** a validação roda, **Then** aplica forward fill nos preços; não preenche TR (TR fora de F1; barras preenchidas devem ficar marcadas para F2 não tratar TR como observado).

---

### US3 — Sincronização multi-instrumento (Priority: P2)

Como pipeline do motor, quero instrumentos alinhados à mesma `timestamp_UTC` (merge outer + preenchimento linear), para transformações comparáveis no mesmo relógio de barras.

**Why this priority**: Necessário para N instrumentos (§3.1/3.2.1), mas secundário ao single-instrument válido.

**Independent Test**: Duas séries com timestamps parcialmente sobrepostos; assert grade unificada e preenchimento linear nos buracos do merge outer.

**Acceptance Scenarios**:

1. **Given** ≥2 instrumentos com timestamps UTC parcialmente distintos, **When** a sincronização roda, **Then** o resultado está alinhado à mesma grade `timestamp_UTC` via merge outer e preenchimento linear.

---

### US4 — Transformação mid → log → retorno (Priority: P1)

Como pipeline do motor, quero P_t, X_t e r_t calculados exatamente como no doc, a partir de bid/ask (e série já validada).

**Why this priority**: É o Passo 1 do motor; destrava entrada numérica dos passos seguintes.

**Independent Test**: Valores de referência conhecidos (bid/ask → mid → ln → delta); comparar com tolerância numérica fixa de teste (sem inventar parâmetro de produção).

**Acceptance Scenarios**:

1. **Given** barra validada com `bid` e `ask`, **When** a transformação roda, **Then** P_t = (Bid_t + Ask_t) / 2.
2. **Given** P_t > 0, **When** a transformação roda, **Then** X_t = ln(P_t).
3. **Given** X_t e X_{t-1} disponíveis, **When** a transformação roda, **Then** r_t = X_t - X_{t-1}.
4. **Given** primeira barra sem predecessor, **When** a transformação roda, **Then** r_t não é emitido para esse índice (série de retornos começa em t ≥ 1).

### Edge Cases

- Barra com `bid`/`ask` ausentes ou não numéricos → Abort `"format_invalido"` (formato exige os sete campos).
- P_t ≤ 0 após mid → Abort (ln indefinido); tratar como falha de integridade/entrada.
- Gap exatamente 4 barras → interpolação (limiar do doc: falha só se gap **>** 4).
- Gap exatamente 5 barras → `"gap_dados"` + NEUTRO temporário.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Sistema MUST aceitar entrada OHLC M30 com campos do §3.1: `timestamp`, `open`, `high`, `low`, `close` (mid-price), `bid`, `ask`.
- **FR-002**: Sistema MUST validar formato JSON `[timestamp_UTC, open, high, low, close, bid, ask]`; falha → Abort + log `"format_invalido"`.
- **FR-003**: Sistema MUST exigir timestamps em UTC; falha → Abort.
- **FR-004**: Sistema MUST validar `high >= max(open, close)` e `low <= min(open, close)`; falha → Abort + log `"integridade_preco_invalida"`.
- **FR-005**: Sistema MUST exigir ordem temporal crescente sem duplicatas; falha → Abort + log `"ordem_temporal_invalida"`.
- **FR-006**: Sistema MUST interpolar linearmente missing bars com gap ≤ 4; se gap > 4, marcar `"gap_dados"` e NEUTRO temporário.
- **FR-007**: Sistema MUST forward-fill preços em weekend gaps; MUST NOT preencher TR (marcação para F2).
- **FR-008**: Sistema MUST alinhar multi-instrumento por `timestamp_UTC` (merge outer + preenchimento linear); lista §9.2 fora desta fatia.
- **FR-009**: Sistema MUST calcular P_t = (Bid_t + Ask_t)/2, X_t = ln(P_t), r_t = X_t - X_{t-1} **in-memory**.
- **FR-010**: Em falha de validação com Abort, sistema MUST parar imediatamente — sem retry nem bypass (nota §3.2.1 / §8.6).

### Key Entities

- **Barra M30**: `timestamp_UTC`, open, high, low, close, bid, ask.
- **Série transformada**: por instrumento — timestamps, P_t, X_t, r_t, flags (`gap_dados`, weekend_fill, status NEUTRO quando aplicável).
- **Grade multi-instrumento**: união de timestamps UTC após merge outer.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% das violações de formato/integridade/ordem temporal nos Independent Tests de US1–US2 resultam em Abort com o log do doc (sem falso aceite).
- **SC-002**: Para fixtures com gap ≤ 4 e gap > 4, o comportamento (interpolação vs `"gap_dados"`+NEUTRO) corresponde ao §3.2.1 em 100% dos casos de teste.
- **SC-003**: Transformação P_t, X_t, r_t bate valores de referência da fixture em todos os pontos t ≥ 1.
- **SC-004**: Nenhum teste de F1 exige ou invoca filtros §3.3+ (escopo fechado).

## Riscos

- Regra “não preenche TR” antecipa F2; se a marcação de weekend_fill não for explícita, F2 pode calcular TR em preço preenchido.
- Sync multi-instrumento sem lista §9.2 deixa N genérico; risco de escopo crescer se alguém fixar instrumentos cedo demais.

## DIVERGÊNCIA

- **Resolvida (Marcos)**: scaffold sem `src/`/`tests/` → **Setup desta fatia cria** a árvore (`src/motor/ohlc/`, `tests/unit/`, `tests/fixtures/ohlc/`, `pyproject.toml`). Paths concretos no `plan.md`.

## NEEDS CLARIFICATION

*(fechados por Marcos — recomendados)*

1. NTP em F1 → **só UTC nos timestamps** (sem check operacional nesta fatia).
2. Saída canônica pós-F1 → **in-memory** (API/módulo; sem schema/arquivo intermediário obrigatório).
3. Instrumentos na sync (US3) → lista **§9.2 depois**; F1 usa N genérico.

## Assumptions

- Fixtures sintéticas bastam para Independent Tests de F1 (fonte OHLC de produção fica para fatias posteriores / F6).
- §3.12.1 é o mesmo quadro que §3.2.1 (duplicata no consolidado); F1 cobre um único conjunto de regras.
- Logs de abort usam as strings literais do doc.
