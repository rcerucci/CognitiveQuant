# Feature Specification: F5 — Confirmação + força + payload

**Feature Branch**: `005-f5-confirmacao-forca-payload`  
**Created**: 2026-09-05  
**Status**: Draft  
**Input**: Fatia F5 (Marcos) — consolidado v1.2 §§3.9–3.11 (+ §1.4–1.5)  
**Fonte**: Documento consolidado v1.2 (lock Marcos)  
**Depende de**: F4 **PASS** in-memory (`Z_t`, `percentil_z`/`P_t`, `garch_sigma`, fonte) + F3 (H, regime, μ, θ, τ, `forca_penalty_cv`) + F2 flags + OHLC/candle F1

## Objetivo

Aplicar confirmações de reversão (§3.9), calcular direção e força (§3.10) com penalizações e thresholds **fixos** 0.75/0.60, e emitir o **payload JSON** do motor (§3.11) in-memory (incl. NEUTRO) — fechando a Camada 1 antes de TA/executor. Adaptativo adiado.

## Fora de escopo

- Reimplementar F1–F4 (só **consumir** PASS + campos)
- TradingAgents / trigger §7 / executor / paper / FTMO — **F7–F9**
- Backtest motor-only — **F6**
- CUSUM, UI, `volume`, lista §9.2
- Productizar (tela, onboarding, marketing)
- Inventar limiares além do consolidado
- Calibração adaptativa de threshold (trigger rate 2 semanas) — **adiada**

## User Scenarios & Testing *(mandatory)*

### US1 — Confirmações de reversão (Priority: P1)

Como pipeline do motor, quero avaliar 8.1–8.6 sobre a barra/série elegível (F4 PASS), para só emitir LONG/SHORT quando as confirmações exigidas passam e para NEUTRO em skewness extrema.

**Why this priority**: Passo 8; gate qualitativo antes da força.

**Independent Test**: Fixtures por indicador (ACF, LB, CLV, RB, shadow, skew); assert NEUTRO em 8.6; assert métricas CLV/RB/US/LS pelas fórmulas §1.5.

**Acceptance Scenarios**:

1. **Given** retornos na janela adequada, **When** ACF(1) é calculado, **Then** `ρ_1` disponível; `ρ_1 > 0` confirma reversão; `ρ_1 < 0` **não** sozinho define direção — alimenta penalização de força (§3.10).
2. **Given** Ljung-Box com k=5, **When** `p < 0.05`, **Then** condição 8.2 satisfeita; se `p ≥ 0.05` → falha de confirmação → **NEUTRO** (direção: “qualquer falha”).
3. **Given** OHLC da barra, **When** CLV/RB/US/LS são calculados (§1.5), **Then** 8.3 exige `|CLV| > 0.30`; 8.4 exige `RB > 0.50` com direção do candle alinhada ao sinal pretendido (Close>Open para LONG, Close<Open para SHORT); 8.5 exige sombra oposta ao desvio `> 0.50` (lower p/ LONG, upper p/ SHORT).
4. **Given** skewness `S`, **When** `S < -2.0` (candidato LONG) ou `S > +2.0` (candidato SHORT), **Then** **NEUTRO** (8.6).

---

### US2 — Direção e força com penalizações (Priority: P1)

Como pipeline do motor, quero direção LONG/SHORT/NEUTRO e força ∈ [0,1] pela fórmula do doc, com penalizações multiplicativas na ordem skewness → CV_θ → ACF, piso 0.18, arredondamento 2 casas.

**Why this priority**: Passo 9; núcleo do sinal.

**Independent Test**: Valores de referência P_t, ρ_1, CLV, RB → força bruta; aplicar cada penalização; assert piso 0.18 e round 2dp; CV flag do F3 → ×0.80.

**Acceptance Scenarios**:

1. **Given** `Z_t < 0` e confirmações exigidas OK, **When** direção é definida, **Then** **LONG**; `Z_t > 0` + confirmações OK → **SHORT**; qualquer falha de confirmação exigida → **NEUTRO**.
2. **Given** `P_t`, `ρ_1`, `|CLV|`, `RB`, **When** força bruta é calculada, **Then** `Força = 0.35×P_t + 0.25×max(ρ_1,0) + 0.25×|CLV| + 0.15×RB`.
3. **Given** penalizações aplicáveis, **When** aplicadas em sequência (1) skewness |S| leve (`S < -1` LONG ou `S > +1` SHORT) → ×0.70; (2) `CV_θ > 0.30` / flag F3 → ×0.80; (3) `ρ_1 < 0` em reversão → ×0.70, **Then** produto cumulativo **não** reduz força abaixo de **0.18**; resultado arredondado a **2** casas.
4. **Given** 8.6 (skew extrema), **When** avaliado, **Then** **NEUTRO** (não só penalização).

---

### US3 — Thresholds fixos 0.75 / 0.60 (Priority: P1)

Como pipeline do motor, quero classificar força em ALTA / MÉDIA / NEUTRO com limiares **fixos** 0.75 / 0.60 nesta fatia (adaptativo adiado).

**Why this priority**: Define se há sinal LONG/SHORT vs NEUTRO no payload.

**Independent Test**: Força 0.75, 0.74, 0.60, 0.59; assert faixas e operador `>=`; assert que limiar 0.70 adaptativo **não** entra em F5.

**Acceptance Scenarios**:

1. **Given** limiares F5, **When** `força >= 0.75`, **Then** confianca **ALTA**; `0.60 <= força < 0.75` → **MÉDIA**; `força < 0.60` → **NEUTRO**.
2. **Given** F5, **When** classifica, **Then** **não** aplica threshold adaptativo 0.70 (fora de escopo desta fatia).

---

### US4 — Payload JSON do motor (Priority: P1)

Como pipeline do motor, quero emitir o payload estruturado §3.11 (objeto in-memory serializável JSON) com sinal, estatísticas, filtros_passados, candle_contexto, evidencias, riscos e calibracao_adaptativa.

**Why this priority**: Contrato de saída da Camada 1 para F6/F7.

**Independent Test**: Schema/campos obrigatórios do exemplo §3.11; `meia_vida_minutos = meia_vida_barras × 30`; `validade_ate` coerente com meia-vida; NEUTRO não inventa direção LONG/SHORT.

**Acceptance Scenarios**:

1. **Given** sinal ALTA ou MÉDIA (não NEUTRO), **When** payload é montado, **Then** inclui `versao_protocolo`, `timestamp_geracao` UTC, `origem`, `instrumento`, `sinal_quantitativo` (direcao, forca, confianca, z_score, percentil_z, hurst, regime, meia_vida_*, validade_ate), `estatisticas_modelo`, `filtros_passados`, `candle_contexto`, `evidencias`, `riscos_estatisticos`, `calibracao_adaptativa` conforme §3.11.
2. **Given** `τ` em barras (F3), **When** payload é montado, **Then** `meia_vida_barras = τ` e `meia_vida_minutos = τ × 30` (M30).
3. **Given** status NEUTRO, **When** F5 termina, **Then** **emite payload** com `direcao: "NEUTRO"` e `confianca: "NEUTRO"` (demais campos preenchidos quando disponíveis).

---

### US5 — Pipeline F5 sobre PASS do F4 (Priority: P2)

Como pipeline do motor, quero encadear confirmação → força/direção → payload só após F4 PASS.

**Why this priority**: Integra US1–US4.

**Independent Test**: F4 NEUTRO → pipeline F5 não promove LONG/SHORT (pode NEUTRO); F4 PASS + fluxo completo → payload ALTA/MÉDIA ou NEUTRO; short-circuit em 8.6.

**Acceptance Scenarios**:

1. **Given** entrada sem F4 PASS, **When** F5 roda, **Then** não promove sinal LONG/SHORT.
2. **Given** F4 PASS e fluxo completo, **When** F5 completa, **Then** payload §3.11 in-memory (ALTA/MÉDIA ou NEUTRO conforme força/confirmações).

### Edge Cases

- High=Low → CLV/RB/shadow indefinidos → **NEUTRO** (divisão por zero).
- Força após penalizações exatamente 0.18 → permitida (piso).
- Força exatamente 0.75 / 0.70 / 0.60 → usar `>=` inclusivo (§3.10).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Sistema MUST consumir F4 PASS + campos F1–F3 necessários; MUST NOT reimplementar GARCH/Hurst/filtros.
- **FR-002**: Sistema MUST calcular ACF(1), Ljung-Box (k=5), CLV, RB, US, LS, skewness conforme §1.4–1.5 / §3.9.
- **FR-003**: Sistema MUST aplicar 8.6 → NEUTRO; falha de confirmações exigidas (8.2–8.5) → NEUTRO para direção.
- **FR-004**: Sistema MUST definir LONG se `Z_t < 0` + confirmações OK; SHORT se `Z_t > 0` + confirmações OK.
- **FR-005**: Sistema MUST calcular força pela fórmula §3.10 e penalizações na ordem skewness → CV_θ → ACF, piso **0.18**, round **2** dp.
- **FR-006**: Sistema MUST classificar ALTA/MÉDIA/NEUTRO com limiares **fixos** `>= 0.75` / `>= 0.60` (adaptativo fora de F5).
- **FR-007**: Sistema MUST montar payload alinhado ao schema §3.11 para ALTA, MÉDIA **e** NEUTRO (`direcao`/`confianca` = NEUTRO neste caso).
- **FR-008**: Saída MUST permanecer **in-memory** (objeto/dict JSON-serializável); sem productizar UI.
- **FR-009**: F5 MUST NOT chamar TradingAgents, executor, broker.
- **FR-010**: `seed=42` quando houver aleatoriedade (§3.12.2).

### Key Entities

- **Confirmacao**: flags/métricas 8.1–8.6.
- **Sinal**: direcao, forca, confianca (ALTA|MÉDIA|NEUTRO).
- **PayloadMotor**: documento §3.11.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Independent Tests US1 — 8.6 e falhas 8.2–8.5 produzem NEUTRO; fórmulas CLV/RB/shadow batem fixture.
- **SC-002**: US2 — força/penalizações/piso 0.18/2dp batem referências.
- **SC-003**: US3 — bordas 0.75/0.60 com `>=` corretas; sem limiar adaptativo 0.70 em F5.
- **SC-004**: US4 — payload §3.11 para ALTA/MÉDIA e para NEUTRO (`direcao`/`confianca` NEUTRO); meia_vida_minutos = barras×30.
- **SC-005**: Nenhum teste F5 importa TA/executor/broker.

## Riscos

- Adaptativo (§3.10) existe no doc mas está **adiado**; risco de esquecer em fatia posterior.
- Payload NEUTRO ainda carrega estatísticas/candle — testes devem fixar quais campos obrigatórios vs opcionais nesse caso.

## DIVERGÊNCIA

- Nenhuma vs locks F1–F4 (in-memory, UTC, sem volume, F4 `arch`/`mean`).
- Paths: Plan amarra sob `src/motor/` após F4 em `main`; Spec só fixa `specs/005-f5-confirmacao-forca-payload/`.

## NEEDS CLARIFICATION

Nenhum aberto — Marcos fechou em 2026-09-05.

## Decisões (Marcos, 2026-09-05)

1. **Gates:** 8.1 = **soft** (só penalização de força); **8.2–8.5 = hard-gate** (falha → NEUTRO); **8.6 = abort** → NEUTRO.
2. **Thresholds nesta fatia:** só **0.75 / 0.60** (ALTA / MÉDIA / NEUTRO). Calibração adaptativa (**adiada** — fora de F5).
3. **Saída NEUTRO:** **emite payload** com `direcao: "NEUTRO"` e `confianca: "NEUTRO"`.
4. **Fonte:** consolidado **v1.2** oficial.

## Assumptions

- Fonte = consolidado v1.2 §§3.9–3.11.
- Locks anteriores: in-memory; seed=42; F4 PASS fornece Z e P_t; F3 fornece flag CV.
- `ρ_1 < 0` penaliza força (×0.70) e não conta no termo `max(ρ_1,0)` (8.1 soft).
- Instrumento no payload usa identificador já presente na série (sem fixar lista §9.2).
- TA/executor fora; adaptativo fora de F5.
