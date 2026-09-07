# Feature Specification: F3 — Regime + OU + bootstrap θ

**Feature Branch**: `003-f3-regime-ou-bootstrap`  
**Created**: 2026-09-05  
**Status**: Ready for Review — Addendum 003b LOCK Marcos  
**Input**: Fatia F3 (Marcos) — consolidado v1.2 §§3.4–3.6 (+ §1.1–1.2 / §6.1–6.2)  
**Fonte**: Documento consolidado v1.2  
**Depende de**: F2 — resultado **PASS** in-memory (série F1 + filtros 2.1–2.4 ok)

**Locks (Marcos)**: Kalman = **pykalman** OU discreto padrão · bootstrap = **iid** janela 200 · μ_θ≈0 → **NEUTRO** · `seed=42`
**Addendum (2026-09-06)**: estimador Hurst = **DFA** Peng em \(X_t\).
**Addendum 003b (2026-09-06)**: H **não** é hard-gate de PASS; PASS reversão = \(\hat\theta\) acima do mínimo **e** meia-vida \(\tau \le K\) (K=20 (lock Marcos)); H>0.55 continua **sem** gerar tendência. DFA em janela 200 não distingue OU lento de RW — por isso o gate passa a OU/τ.

## Objetivo

Estimar Hurst **DFA** (diagnóstico, janela 200) e OU (μ, θ, τ) com Kalman/MLE; **PASS de reversão** só se \(\hat\theta\) acima do mínimo **e** \(\tau = \ln2/\theta \le K\); bootstrap CV; H **não** hard-gate; H>0.55 **não** abre tendência — antes de GARCH/Z/payload.

## Fora de escopo

- F1 validação/transform e F2 filtros (só **consumir** PASS)
- CUSUM (§6.3 — opcional Fase 2)
- GARCH, Z-score, percentil, confirmação, força final, payload (§3.7–3.11)
- Aplicar a penalização de força no cálculo de Força (§3.10) — F3 só **produz** CV / flag; a multiplicação ×0.80 é fatia posterior (F5)
- TradingAgents, executor, paper/demo, FTMO
- `volume` / lista §9.2 / UI
- H&gt;0.55 gerar sinal de **tendência**
- Usar H sozinho como hard-gate de PASS/NEUTRO (003b)
- Hurst em \(r_t\) como série do DFA
- Inventar K ou θ_min sem lock Marcos
- Reabrir F2 ADF / F4–F6 / F7 / run 10×65k

## User Scenarios & Testing *(mandatory)*

### US1 — Hurst DFA (diagnóstico; não hard-gate) (Priority: P1)

Como pipeline do motor, quero H via **DFA Peng** em \(X_t\) (janela 200) como **métrica de contexto**, **sem** hard-gate de PASS/NEUTRO por faixas 0.45/0.55 — em N=200 o DFA não distingue OU lento de RW. H&gt;0.55 **continua sem** gerar caminho de tendência.

**Why this priority**: Addendum 003b — régua de PASS migra para OU/τ.

**Independent Test** (`tests/unit/test_hurst_sanity.py`, seed=42) — validade do estimador (não do gate de PASS):
- A branco → α ~ 0.5 (faixa tolerada do harness, ex. [0.35, 0.65])
- B OU rápido (ex. θ=0.50) com escalas adequadas → α &lt; 0.45
- C RW → α ~ 1.5 / H&gt;0.55  
Documentar que em janela 200 OU lento ≈ RW no DFA.

**Acceptance Scenarios**:

1. **Given** janela 200 de `X_t` e DFA (H:=α; nível, não \(r_t\)), **When** H é calculado, **Then** H é **emitido** no resultado in-memory **sem** sozinho forçar PASS ou NEUTRO.
2. **Given** `H > 0.55`, **When** classifica caminhos, **Then** **MUST NOT** abrir sinal/tendência (só diagnóstico).
3. **Given** histórico &lt; 200, **When** DFA/OU, **Then** **NEUTRO** (warm-up).
4. **Given** escala com 1 segmento, **When** monta escalas, **Then** inválida; conjunto N=200 = `{8,16,32,64}` (FR-002a).

### US2 — OU + gate de reversão (θ̂, τ≤K) (Priority: P1)

Como pipeline do motor, quero estimar OU (Kalman/MLE) após F2 PASS e só **PASS** se \(\hat\theta\) acima do mínimo **e** meia-vida \(\tau = \ln(2)/\theta \le K\) barras.

**Why this priority**: Gate de reversão 003b (substitui H hard-gate).

**Independent Test**: OU com τ≤K e θ̂ ok → PASS; θ≤0 → NEUTRO; τ&gt;K → NEUTRO mesmo com θ&gt;0; Kalman diverge → MLE. (K e θ_min — ver NC.)

**Acceptance Scenarios**:

1. **Given** F2 PASS e warm-up ok, **When** Kalman produz θ finito e θ̂ acima do mínimo, **Then** usa μ, θ e `τ = ln(2)/θ`.
2. **Given** Kalman θ&lt;0 ou não-finito, **When** roda, **Then** MLE janela 200.
3. **Given** θ̂ abaixo do mínimo (incl. θ≤0), **When** gate, **Then** **NEUTRO**.
4. **Given** θ̂ ok e **τ ≤ K**, **When** gate de reversão, **Then** elegível a **PASS** (sujeito a bootstrap/CV rules).
5. **Given** θ̂ ok e **τ > K**, **When** gate, **Then** **NEUTRO** (OU lento / indistinguível de RW na prática do motor).
6. **Given** H qualquer (incl. zona 0.45–0.55 ou H&gt;0.55), **When** θ̂ ok e τ≤K, **Then** H **não** anula o PASS de reversão; H&gt;0.55 **não** cria tendência.

### US3 — Bootstrap de θ e CV (Priority: P1)

**Independent Test**: CV ≤ 0.30 → estável; CV > 0.30 → flag sem NEUTRO; μ_θ≈0 → NEUTRO; seed=42.

**Acceptance Scenarios**:

1. **Given** θ > 0 e janela 200, **When** bootstrap iid com 50 reamostragens roda, **Then** calcula `CV = σ_θ / μ_θ`.
2. **Given** `CV ≤ 0.30`, **When** classifica, **Then** θ marcado **estável**.
3. **Given** `CV > 0.30`, **When** classifica, **Then** marca `forca_penalty_cv` e **prossegue**.
4. **Given** μ_θ ≈ 0, **When** CV seria indefinido, **Then** status **NEUTRO**.
5. **Given** bootstrap, **When** roda, **Then** usa `seed=42` (`numpy.random.default_rng(42)`).

### US4 — Pipeline F3 sobre PASS do F2 (Priority: P2)

**Independent Test**: F2 NEUTRO → sem PASS F3; F2 PASS + θ̂ ok + τ≤K → PASS com campos (H presente só como diagnóstico).

**Acceptance Scenarios**:

1. **Given** entrada sem F2 PASS, **When** F3 roda, **Then** **não** promove a PASS.
2. **Given** F2 PASS, θ̂ ok, τ≤K, **When** F3 completa, **Then** status **PASS** in-memory com H (diagnóstico), μ, θ, τ, `bootstrap_cv_theta` e flag CV se aplicável.
3. **Given** F2 PASS e (θ̂ baixo ou τ&gt;K), **When** F3 roda, **Then** **NEUTRO** — independentemente de H.

## Requirements *(mandatory)*

- **FR-001**: Consumir apenas F2 PASS (+ série F1); MUST NOT reimplementar filtros §3.3.
- **FR-002**: Hurst por **DFA Peng** em \(X_t\), janela 200; H:=α; MUST NOT usar \(r_t\) como input do DFA; H é **diagnóstico** (MUST emitir).
- **FR-002a**: Escalas DFA N=200 → **`{8,16,32,64}`** (proibido 1 segmento; ≥4 pontos).
- **FR-002b**: Fallback R/S (sem n de 1 bloco) só se harness DFA de sanidade falhar — não restaura H hard-gate.
- **FR-003**: H **MUST NOT** ser hard-gate de PASS/NEUTRO. `H > 0.55` MUST NOT gerar tendência/sinal.
- **FR-004**: OU com **pykalman** discreto padrão; θ < 0 ou não-finito → MLE janela 200.
- **FR-005**: Calcular `τ = ln(2)/θ` quando θ̂ finito e acima do mínimo; caso contrário NEUTRO.
- **FR-005a**: PASS de reversão MUST exigir **θ̂ acima do mínimo** **e** **τ ≤ K** (K e mínimo — NC). Falha → NEUTRO.
- **FR-006**: Bootstrap **iid** 50; `CV = σ_θ / μ_θ`.
- **FR-007**: CV ≤ 0.30 estável; CV > 0.30 → flag ×0.80 para F5 sem NEUTRO só por CV.
- **FR-008**: `seed=42`.
- **FR-009**: Saída in-memory.
- **FR-010**: MUST NOT GARCH/Z/payload/TA/executor/CUSUM.
- **FR-011**: Histórico < 200 → NEUTRO.
- **FR-012**: μ_θ ≈ 0 → NEUTRO.

## Success Criteria *(mandatory)*

- **SC-001**: H não sozinho força PASS/NEUTRO; H&gt;0.55 sem tendência.
- **SC-002**: gate τ≤K e θ̂ mínimo: PASS vs NEUTRO conforme NC lockados; τ = ln(2)/θ.
- **SC-003**: CV > 0.30 marca penalização sem forçar NEUTRO; seed=42 reproduz; μ_θ≈0 → NEUTRO.
- **SC-004**: Nenhum teste F3 importa GARCH/payload/TA/executor/CUSUM.
- **SC-005**: `test_hurst_sanity.py` A/B/C seed=42 (DFA Peng: branco~0.5; OU rápido α&lt;0.45; RW~1.5).
- **SC-006** (003b): fixture τ&gt;K → NEUTRO; τ≤K + θ̂ ok → PASS elegível (sem depender de H&lt;0.45).

## DIVERGÊNCIA

- Código/spec pré-003b: H hard-gate (0.45/0.55) — **superseded** por gate θ̂+τ≤K.
- DFA janela 200: OU lento ≈ RW — motivação do 003b.
- Não reabre F2; F4–F7 fora.

## NEEDS CLARIFICATION

Nenhum aberto — Marcos fechou LOCK 003b em 2026-09-06.

## Decisões — Addendum 003b (LOCK Marcos 2026-09-06)

1. H = DFA Peng diagnóstico; **não** hard-gate; H>0.55 **não** vira tendência.
2. PASS reversão: θ̂ > 0 ∧ IC_low (p2.5% bootstrap) > 0 ∧ τ ≤ **K=20** barras M30.
3. Janela Hurst/OU = 200 inalterada.
4. Sem F7 / 10×65k neste hotfix.

## Assumptions

Locks F1/F2 permanecem. Ordem: DFA (diagnóstico) → OU → gate τ/θ → bootstrap. CUSUM fora. Fixtures sintéticas bastam.
Plan/Tasks **calados** até Marcos lockar K (e θ_min se ≠ θ>0).

## Nota sobre S1 (hotfix 003b-s1-discreto)

**S1 do aceite US2 NÃO é Euler.**

O aceite original propunha a fórmula de Euler discreto:
```
X[t] += θ * (μ - X[t]) + σ * ε
```

**S1 é o OU discreto padrão** que `ou.py` estima:
```
X[t] = exp(-θ) * X[t-1] + σ * ε
```

### Diferença:
- **Euler discreto**: φ = 1 - θ
- **OU discreto correto**: φ = exp(-θ)

Para θ = 0.50:
- Euler: φ = 1 - 0.5 = 0.5
- OU discreto: φ = exp(-0.5) ≈ 0.6065

O OU discreto é a formulação correta para o processo OU em tempo discreto com passo dt=1.
