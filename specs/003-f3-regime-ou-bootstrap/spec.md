# Feature Specification: F3 — Regime + OU + bootstrap θ

**Feature Branch**: `003-f3-regime-ou-bootstrap`  
**Created**: 2026-09-05  
**Status**: Approved  
**Input**: Fatia F3 (Marcos) — consolidado v1.2 §§3.4–3.6 (+ §1.1–1.2 / §6.1–6.2)  
**Fonte**: Documento consolidado v1.2  
**Depende de**: F2 — resultado **PASS** in-memory (série F1 + filtros 2.1–2.4 ok)

**Locks (Marcos)**: Kalman = **pykalman** OU discreto padrão · bootstrap = **iid** janela 200 · μ_θ≈0 → **NEUTRO** · `seed=42`

## Objetivo

Classificar regime via Hurst (janela 200); se reversão, estimar OU (μ, θ, τ) com Kalman/MLE e medir estabilidade de θ via bootstrap (CV); emitir PASS in-memory com parâmetros OU/CV ou NEUTRO conforme limiares do doc — antes de GARCH/Z/payload.

## Fora de escopo

- F1 validação/transform e F2 filtros (só **consumir** PASS)
- CUSUM (§6.3 — opcional Fase 2)
- GARCH, Z-score, percentil, confirmação, força final, payload (§3.7–3.11)
- Aplicar a penalização de força no cálculo de Força (§3.10) — F3 só **produz** CV / flag; a multiplicação ×0.80 é fatia posterior (F5)
- TradingAgents, executor, paper/demo, FTMO
- `volume` / lista §9.2 / UI

## User Scenarios & Testing *(mandatory)*

### US1 — Regime Hurst R/S (Priority: P1)

Como pipeline do motor, quero H na janela 200 com sub-tamanhos 8/16/32/64/128 e gate de regime, para só estimar OU em reversão.

**Independent Test**: Séries sintéticas de reversão / RW / tendência; assert classificação e NEUTRO/PASS sem chamar OU.

**Acceptance Scenarios**:

1. **Given** janela 200 de `X_t` e R/S com sub-tamanhos 8/16/32/64/128 + regressão log-log, **When** `H < 0.45`, **Then** regime **REVERSÃO** e o passo prossegue.
2. **Given** o mesmo cálculo, **When** `0.45 ≤ H ≤ 0.55`, **Then** **ZONA NEUTRA** → status **NEUTRO**.
3. **Given** o mesmo cálculo, **When** `H > 0.55`, **Then** **TENDÊNCIA** → status **NEUTRO**.
4. **Given** histórico < 200 barras, **When** Hurst é solicitado, **Then** **NEUTRO** (warm-up).

### US2 — OU Kalman com fallback MLE (Priority: P1)

**Independent Test**: Série OU sintética com θ>0 → PASS com τ finito; θ≤0 → NEUTRO; Kalman diverge força MLE.

**Acceptance Scenarios**:

1. **Given** regime REVERSÃO, **When** Kalman produz θ finito e θ > 0, **Then** usa μ_t, θ_t do Kalman e `τ = ln(2)/θ`.
2. **Given** Kalman com θ < 0 ou não-finito, **When** o passo roda, **Then** estima MLE em janela 200.
3. **Given** θ ≤ 0 após Kalman/MLE, **When** a guarda roda, **Then** status **NEUTRO**.
4. **Given** θ > 0, **When** τ é calculado, **Then** `τ = ln(2)/θ` (barras).

### US3 — Bootstrap de θ e CV (Priority: P1)

**Independent Test**: CV ≤ 0.30 → estável; CV > 0.30 → flag sem NEUTRO; μ_θ≈0 → NEUTRO; seed=42.

**Acceptance Scenarios**:

1. **Given** θ > 0 e janela 200, **When** bootstrap iid com 50 reamostragens roda, **Then** calcula `CV = σ_θ / μ_θ`.
2. **Given** `CV ≤ 0.30`, **When** classifica, **Then** θ marcado **estável**.
3. **Given** `CV > 0.30`, **When** classifica, **Then** marca `forca_penalty_cv` e **prossegue**.
4. **Given** μ_θ ≈ 0, **When** CV seria indefinido, **Then** status **NEUTRO**.
5. **Given** bootstrap, **When** roda, **Then** usa `seed=42` (`numpy.random.default_rng(42)`).

### US4 — Pipeline F3 sobre PASS do F2 (Priority: P2)

**Independent Test**: F2 NEUTRO → sem OU; F2 PASS + H<0.45 + θ>0 → PASS com campos.

**Acceptance Scenarios**:

1. **Given** entrada sem F2 PASS, **When** F3 roda, **Then** **não** promove a PASS e **não** emite OU válido.
2. **Given** F2 PASS e Hurst NEUTRO, **When** F3 roda, **Then** status **NEUTRO**.
3. **Given** F2 PASS, H<0.45, θ>0, **When** F3 completa, **Then** status **PASS** in-memory com H, μ, θ, τ, `bootstrap_cv_theta` e flag CV se aplicável.

## Requirements *(mandatory)*

- **FR-001**: Consumir apenas F2 PASS (+ série F1); MUST NOT reimplementar filtros §3.3.
- **FR-002**: Hurst R/S janela 200, sub-tamanhos 8/16/32/64/128, regressão log-log.
- **FR-003**: `H < 0.45` → REVERSÃO; `0.45 ≤ H ≤ 0.55` → NEUTRO; `H > 0.55` → NEUTRO.
- **FR-004**: OU com **pykalman** discreto padrão; θ < 0 ou não-finito → MLE janela 200.
- **FR-005**: θ ≤ 0 → NEUTRO; θ > 0 → `τ = ln(2)/θ`.
- **FR-006**: Bootstrap **iid** 50; `CV = σ_θ / μ_θ`.
- **FR-007**: CV ≤ 0.30 estável; CV > 0.30 → flag ×0.80 para F5 sem NEUTRO só por CV.
- **FR-008**: `seed=42`.
- **FR-009**: Saída in-memory.
- **FR-010**: MUST NOT GARCH/Z/payload/TA/executor/CUSUM.
- **FR-011**: Histórico < 200 → NEUTRO.
- **FR-012**: μ_θ ≈ 0 → NEUTRO.

## Success Criteria *(mandatory)*

- **SC-001**: Limiares H corretos (incl. bordas 0.45/0.55).
- **SC-002**: θ ≤ 0 → NEUTRO; θ > 0 → τ = ln(2)/θ.
- **SC-003**: CV > 0.30 marca penalização sem forçar NEUTRO; seed=42 reproduz; μ_θ≈0 → NEUTRO.
- **SC-004**: Nenhum teste F3 importa GARCH/payload/TA/executor/CUSUM.

## NEEDS CLARIFICATION

*(fechados por Marcos)* pykalman · bootstrap iid · μ_θ≈0 → NEUTRO.

## Assumptions

Locks F1/F2 permanecem. Ordem: Hurst → OU → bootstrap. CUSUM fora. Fixtures sintéticas bastam.
