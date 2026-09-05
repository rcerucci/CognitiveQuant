# Feature Specification: F4 — GARCH + Z + percentil

**Feature Branch**: `004-f4-garch-z-percentil`  
**Created**: 2026-09-05  
**Status**: Draft  
**Input**: Fatia F4 (Marcos) — consolidado v1.2 §§3.7–3.8 (+ §1.3 / §1.7)  
**Fonte**: Documento consolidado v1.2  
**Depende de**: F3 — resultado **PASS** in-memory (μ_t / θ / τ / H / flags CV + série F1 com `X_t`, `r_t`)

## Objetivo

Estimar volatilidade condicional GARCH(1,1) na janela de retornos, calcular Z-score condicional e percentil empírico de |Z| (janela 200) como **input de força** — sem usar o percentil como filtro de passagem — antes de confirmação/força/payload (F5).

## Fora de escopo

- F1/F2/F3 (só **consumir** PASS F3 + série)
- Confirmação de reversão, força, direção, payload (§3.9–3.11) — **F5**
- Aplicar thresholds de força / trigger TA
- Usar `P_t > 0.95` como gate de passagem (nota §3.8: percentil **não** é filtro)
- TradingAgents, executor, FTMO, CUSUM, UI, `volume`, §9.2

## User Scenarios & Testing *(mandatory)*

### US1 — GARCH(1,1) com restrição e fallback (Priority: P1)

Como pipeline do motor, quero ω, α, β via MLE em `r_{t-199:t}` com α+β &lt; 0.995, e fallback para vol móvel simples se o GARCH não converge ou viola estabilidade, para obter σ_t condicional estável.

**Why this priority**: Passo 6; base do Z condicional.

**Independent Test**: Série com GARCH convergente (α+β&lt;0.995) vs não-convergente / α+β≥0.995 → fallback; assert fonte `garch` vs `fallback`; sem Z/percentil.

**Acceptance Scenarios**:

1. **Given** janela `r_{t-199:t}` (200 retornos) e F3 PASS, **When** MLE GARCH(1,1) converge com `α + β < 0.995`, **Then** usa `σ_t² = ω + α r_{t-1}² + β σ_{t-1}²` e marca fonte **garch**.
2. **Given** GARCH que não converge **ou** `α + β ≥ 0.995` (alinhado §1.3 / tabela de stress), **When** o passo roda, **Then** aplica fallback `σ_t = √(∑ r² / 20)` e marca fonte **fallback** (não Abort de formato).
3. **Given** histórico de retornos &lt; 200, **When** GARCH é solicitado, **Then** **NEUTRO** (warm-up).

---

### US2 — Z-score condicional (Priority: P1)

Como pipeline do motor, quero `Z_t = (X_t − μ_t) / σ_t^{GARCH}` usando μ_t do F3 e σ do US1 (garch ou fallback).

**Why this priority**: Passo 7a; alimenta percentil e depois direção em F5.

**Independent Test**: Fixture com μ, X, σ conhecidos → Z bate referência; σ≤0 / não-finito → NEUTRO.

**Acceptance Scenarios**:

1. **Given** `X_t`, `μ_t` (F3) e `σ_t > 0` (GARCH ou fallback), **When** o Z é calculado, **Then** `Z_t = (X_t − μ_t) / σ_t`.
2. **Given** σ proveniente do fallback, **When** o Z é calculado, **Then** ainda usa a mesma fórmula com esse σ (Z condicional com σ disponível).

---

### US3 — Percentil empírico de |Z| (Priority: P1)

Como pipeline do motor, quero `P_t = percentil(|Z_t|, 200)` como input multiplicativo futuro de força, **sem** NEUTRO por limiar de percentil.

**Why this priority**: Passo 7b; contrato para F5 (§3.10 usa 0.35×P_t).

**Independent Test**: Janela 200 de |Z|; P_t ∈ [0,1]; extremo não força sempre 1.0 se método de score evitar isso; assert que P_t alto **não** sozinho vira NEUTRO.

**Acceptance Scenarios**:

1. **Given** |Z_t| e histórico de 200 valores |Z|, **When** o percentil roda, **Then** `P_t = rank(|Z_t|) / N` com `N = 200` (§1.7), via score empírico na janela.
2. **Given** qualquer `P_t` (incl. &gt; 0.95), **When** só F4 avalia, **Then** **não** aplica filtro de passagem por percentil (§3.8); emite `P_t` in-memory para F5.
3. **Given** implementação do score, **When** há empates no extremo, **Then** usa `scipy.stats.percentileofscore` com método **`mean`** (lock Marcos).

---

### US4 — Pipeline F4 sobre PASS do F3 (Priority: P2)

Como pipeline do motor, quero encadear GARCH → Z → percentil só após F3 PASS, com saída in-memory (σ, ω/α/β ou flag fallback, Z_t, percentil_z, fonte).

**Why this priority**: Integra US1–US3; contrato para F5.

**Independent Test**: F3 NEUTRO → F4 não promove PASS; F3 PASS + GARCH ok → PASS com campos; fallback ainda pode PASS se σ&gt;0 e Z/P calculáveis.

**Acceptance Scenarios**:

1. **Given** entrada sem F3 PASS, **When** F4 roda, **Then** **não** promove a PASS e **não** emite Z/P válidos para F5.
2. **Given** F3 PASS e GARCH/fallback com σ&gt;0, **When** F4 completa, **Then** status **PASS** in-memory com `garch_sigma`, `Z_t`, `percentil_z`, fonte (`garch`|`fallback`).
3. **Given** fallback ativado, **When** F4 completa com σ&gt;0, **Then** ainda pode **PASS** (fallback não é NEUTRO automático).

### Edge Cases

- `α + β` exatamente 0.995 → trata como violação da restrição estrita `&lt; 0.995` → fallback.
- σ_t = 0 ou não-finito após garch/fallback → **NEUTRO** (lock Marcos).
- Warm-up &lt; 20 no fallback √(∑r²/20) com série curta já barrada por &lt;200 no GARCH.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Sistema MUST consumir apenas **F3 PASS** (+ `X_t`, `r_t`, `μ_t`); MUST NOT reimplementar Hurst/OU/filtros.
- **FR-002**: Sistema MUST estimar GARCH(1,1) `σ_t² = ω + α r_{t-1}² + β σ_{t-1}²` via MLE em `r_{t-199:t}`.
- **FR-003**: Sistema MUST exigir `α + β < 0.995`; se não converge ou `α + β ≥ 0.995`, MUST usar fallback `σ_t = √(∑ r² / 20)`.
- **FR-004**: Sistema MUST calcular `Z_t = (X_t − μ_t) / σ_t` com σ do GARCH ou fallback.
- **FR-005**: Sistema MUST calcular `P_t = percentil(|Z_t|, 200)` (§1.7 / §3.8) e MUST NOT usar P_t como filtro de passagem.
- **FR-006**: Saída MUST ser **in-memory** (`garch_sigma`, params ou flag fallback, `Z_t`, `percentil_z`, fonte, status).
- **FR-007**: Histórico &lt; 200 retornos → **NEUTRO**.
- **FR-008**: F4 MUST NOT importar/executar confirmação §3.9, força §3.10, payload §3.11, TA, executor.
- **FR-009**: Operações aleatórias (se houver no MLE/fit) MUST respeitar `seed=42` quando aplicável (§3.12.2).

### Key Entities

- **ResultadoGARCH**: ω, α, β (se garch), `garch_sigma`, fonte (`garch` | `fallback`).
- **ResultadoZ**: `Z_t`.
- **ResultadoPercentil**: `percentil_z` (`P_t` ∈ [0,1]).
- **ResultadoF4**: agrega acima + status PASS | NEUTRO.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: US1 — casos α+β&lt;0.995 convergente usam garch; violação/não-convergência usam fallback; 100% nos Independent Tests.
- **SC-002**: US2 — Z bate valores de referência da fixture (σ&gt;0).
- **SC-003**: US3 — P_t ∈ [0,1]; P_t alto **não** sozinho causa NEUTRO em F4.
- **SC-004**: Nenhum teste F4 importa confirmação/força/payload/TA/executor.

## Riscos

- Lib GARCH pinada em `arch` (lock).
- `percentileofscore(method="mean")` pinado (lock).
- σ≤0 / não-finito → NEUTRO (lock); testes devem cobrir.

## DIVERGÊNCIA

- Nenhuma vs locks anteriores (in-memory, UTC, sem volume).
- Paths: Plan amarra sob `src/motor/` com `regime/` já em `main`; Spec só fixa `specs/004-f4-garch-z-percentil/`.

## NEEDS CLARIFICATION

Nenhum aberto — Marcos fechou em 2026-09-05 (recomendados).

## Decisões (Marcos, 2026-09-05)

1. **Lib GARCH:** pacote **`arch`** (ref consolidado §12).
2. **percentileofscore:** método **`mean`**.
3. **σ_t ≤ 0 / não-finito:** status **NEUTRO** (não Abort de formato).

## Assumptions

- Locks F1–F3: in-memory; seed=42; F3 fornece μ_t; entrada só com F3 PASS.
- Fallback é continuação (PASS possível), não NEUTRO automático — exceto se σ resultante ≤0 / não-finito → NEUTRO (lock).
- `P_t > 0.95` em §1.7 é contexto de extremo / F5 — **não** gate em F4.
- Fixtures sintéticas bastam.
