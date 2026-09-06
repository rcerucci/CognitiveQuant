# Feature Specification: F3 — Regime + OU + bootstrap θ

**Feature Branch**: `003-f3-regime-ou-bootstrap`  
**Created**: 2026-09-05  
**Status**: Approved + Addendum 2026-09-06 (Hurst DFA)  
**Input**: Fatia F3 (Marcos) — consolidado v1.2 §§3.4–3.6 (+ §1.1–1.2 / §6.1–6.2)  
**Fonte**: Documento consolidado v1.2  
**Depende de**: F2 — resultado **PASS** in-memory (série F1 + filtros 2.1–2.4 ok)

**Locks (Marcos)**: Kalman = **pykalman** OU discreto padrão · bootstrap = **iid** janela 200 · μ_θ≈0 → **NEUTRO** · `seed=42`
**Addendum (2026-09-06)**: estimador Hurst = **DFA** em \(X_t\) (não R/S cego); cortes 0.45/0.55 **iguais**; OU/bootstrap **inalterados**.

## Objetivo

Classificar regime via Hurst **DFA** (janela 200); se reversão, estimar OU (μ, θ, τ) com Kalman/MLE e medir estabilidade de θ via bootstrap (CV); emitir PASS in-memory com parâmetros OU/CV ou NEUTRO conforme limiares do doc — antes de GARCH/Z/payload.

## Fora de escopo

- F1 validação/transform e F2 filtros (só **consumir** PASS)
- CUSUM (§6.3 — opcional Fase 2)
- GARCH, Z-score, percentil, confirmação, força final, payload (§3.7–3.11)
- Aplicar a penalização de força no cálculo de Força (§3.10) — F3 só **produz** CV / flag; a multiplicação ×0.80 é fatia posterior (F5)
- TradingAgents, executor, paper/demo, FTMO
- `volume` / lista §9.2 / UI
- H&gt;0.55 gerar sinal / mudar cortes 0.45/0.55
- Hurst em \(r_t\) como gate de regime
- Reabrir F2 ADF / F4–F6 / F7 / run 10×65k

## User Scenarios & Testing *(mandatory)*

### US1 — Regime Hurst DFA (Priority: P1)

Como pipeline do motor, quero H na janela 200 via **DFA** em \(X_t\) (log-preço) e gate de regime inalterado, para só estimar OU em reversão — o R/S vigente não classifica OU estacionário como reversão (H~0.93 em fixture).

**Why this priority**: Régua do regime; cortes corretos, estimador cego (addendum 2026-09-06).

**Independent Test** (`tests/unit/test_hurst_sanity.py`, seed=42):
- A branco N(0,1) → H ∈ [0.35, 0.65]
- B OU nível θ=0.15, σ=0.2, n≥2000 → **H&lt;0.45** e status reversão/PASS
- C RW cumsum → H&gt;0.55 e NEUTRO  
R/S atual deve **falhar** B (prova do bug). Merge só com B verde no estimador novo.

**Acceptance Scenarios**:

1. **Given** janela 200 de `X_t` e **DFA** (H = α da regressão log F(s) ~ α log(s); série em **nível**, não \(r_t\)), **When** `H < 0.45`, **Then** regime **REVERSÃO** e o passo prossegue.
2. **Given** o mesmo cálculo, **When** `0.45 ≤ H ≤ 0.55`, **Then** **ZONA NEUTRA** → status **NEUTRO**.
3. **Given** o mesmo cálculo, **When** `H > 0.55`, **Then** **TENDÊNCIA** → status **NEUTRO** (H&gt;0.55 **não** gera sinal).
4. **Given** histórico < 200 barras, **When** Hurst é solicitado, **Then** **NEUTRO** (warm-up).
5. **Given** escala candidata com **um único segmento** na janela, **When** DFA monta escalas, **Then** essa escala é **inválida** (excluída).
6. **Given** DFA falha o teste B (OU H≥0.45) no harness de aceite, **When** fallback documentado, **Then** R/S clássico **uma** estatística por escala na série completa, **sem** n com 1 bloco; ainda janela 200 e **mesmos cortes** (não é H&gt;0.55=PASS).

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
- **FR-002**: Hurst por **DFA** em \(X_t\), janela 200; H = expoente α da log-log F(s)~s; MUST NOT usar \(r_t\) como input do gate de regime.
- **FR-002a**: Escalas DFA = potências de 2 em `[8, floor(N/2)]` com `floor(N/s) ≥ 2` (**proibido** 1 segmento) e **≥4 escalas válidas** na regressão. Para N=200 o conjunto válido resultante é **`{8,16,32,64}`** (128 excluído: 1 segmento).
- **FR-002b**: Se DFA falhar o aceite B (OU), fallback R/S com uma estatística por escala válida (sem n de 1 bloco); cortes inalterados.
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
- **SC-005** (addendum): `test_hurst_sanity.py` A/B/C seed=42 verdes no estimador novo; R/S legado falha B.

## DIVERGÊNCIA

- **Addendum vs código vigente:** `hurst.py` R/S falha fixture OU (H~0.93) — hotfix DFA obrigatório.
- Não reabre F2 (salvo consumo PASS); F4–F6 fora.

## NEEDS CLARIFICATION

Nenhum aberto neste addendum — escalas DFA trancadas em FR-002a (`{8,16,32,64}` para N=200 via regra ≥2 segmentos + ≥4 pontos).

## Decisões — Addendum Hurst DFA (2026-09-06)

1. Estimador = **DFA** em \(X_t\); H:=α; janela 200.
2. Cortes **0.45 / 0.55 iguais**; H&gt;0.55 → NEUTRO (não PASS).
3. Escalas: regra FR-002a → **`{8,16,32,64}`** em N=200; proibido 1 segmento.
4. Fallback R/S documentado só se DFA falhar aceite B; ainda sem n de 1 bloco.
5. Path: `src/motor/regime/hurst.py` + `tests/unit/test_hurst_sanity.py` — Plan amarra.
6. OU / bootstrap / Kalman locks **inalterados**.

## Locks anteriores (inalterados)

pykalman · bootstrap iid · μ_θ≈0 → NEUTRO · seed=42.

## Assumptions

Locks F1/F2 permanecem. Ordem: Hurst → OU → bootstrap. CUSUM fora. Fixtures sintéticas bastam.
