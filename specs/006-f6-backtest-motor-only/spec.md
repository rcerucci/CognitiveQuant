# Feature Specification: F6 — Backtest motor-only

**Feature Branch**: `006-f6-backtest-motor-only`  
**Created**: 2026-09-05  
**Status**: Ready for Review  
**Input**: Fatia F6 (Marcos) — mapa Fatiador + consolidado v1.2 **§10.1** (+ lista **§9.2**)  
**Fonte**: Documento consolidado v1.2 (sem reabrir F5)  
**Depende de**: F5 em `main` — pipeline F1→F5 (`src/motor/{ohlc,filters,regime,vol,signal}/`) → payload §3.11 in-memory

## Objetivo

Rodar **backtest histórico motor-only** (§10.1) sobre **histórico real** M30 (CSV/parquet): executar o motor Python puro (**sem** TA, **sem** MCP), simular PnL (entry mid-close → exit `validade_ate`/`τ`, sem flip), calcular métricas/alvos do consolidado e aplicar o **gate Sharpe** (mín. 7/10 com Sharpe > 0.5; Sharpe = equity diária, Rf=0, ×√252).

## Fora de escopo

- Reimplementar F1–F5 (só **consumir** APIs públicas)
- TradingAgents / adapter de rating — **F7**
- Executor / paper / demo / MCP — **F8**
- FTMO / portfólio / hard-stop — **F9**
- Calibração adaptativa (adiada em F5)
- UI, productizar, `volume`
- Inventar limiares além do consolidado + locks abaixo
- Fase Demo Forward (§10.2) e posteriores
- Download pago de provider no CI (adapter de provider **fora**; F6 lê CSV/parquet já materializado)
- Taxa só-ALTA (≥0.75) como gate — **diagnóstico F7**, não gate F6

## User Scenarios & Testing *(mandatory)*

### US1 — Runner motor-only barra-a-barra (Priority: P1)

Como validador do motor, quero percorrer série M30 histórica (ou fixture de teste) chamando F1→F5 in-memory por barra/instrumento, sem TA/MCP.

**Why this priority**: Núcleo §10.1 (“Python puro, sem TradingAgents, sem executor MCP”).

**Independent Test**: Fixture curta → N payloads; assert zero import/chamada TA/executor/broker; `seed=42` se houver aleatoriedade.

**Acceptance Scenarios**:

1. **Given** série M30 no formato F1, **When** runner F6 avança barra a barra, **Then** cada passo consome F1→F5 e produz payload §3.11 (incl. NEUTRO) in-memory.
2. **Given** runner F6, **When** executa, **Then** **MUST NOT** chamar TradingAgents, executor MCP ou API de broker/provider.
3. **Given** warm-up / NEUTRO de camadas anteriores, **When** barra não é elegível a LONG/SHORT trigger, **Then** não abre trade.

---

### US2 — Dados reais + universo §9.2 (Priority: P1)

Como validador, quero carregar **histórico real** (CSV/parquet) dos **10 instrumentos** §9.2 no horizonte **5 anos** M30; provider (OANDA/Polygon/QC/Broker) fica **adapter externo** — F6 só consome arquivo já materializado.

**Why this priority**: §10.1 Dados/Fonte; custo Zero no sentido de não acoplar API paga no runner.

**Independent Test**: Loader lê fixture CSV/parquet no formato F1; lista canônica §9.2; reject tickers fora da lista.

**Acceptance Scenarios**:

1. **Given** F6, **When** configura universo, **Then** instrumentos = §9.2: EUR/USD, GBP/JPY, USD/CAD, AUD/NZD, US500, GER30, JP225, XAU/USD, USOIL, NAS100.
2. **Given** path CSV/parquet materializado, **When** loader lê, **Then** barras no formato F1; **não** chama Polygon/OANDA/QC/Broker em runtime do backtest.
3. **Given** Independent Tests no CI, **When** rodam, **Then** usam fixtures CSV/parquet **pequenas** (sem rede); o gate §10.1 7/10 sobre **5 anos reais** é execução/validação com dataset completo (não substituído só por série sintética de preços inventada).

---

### US3 — Simulação PnL motor-only (Priority: P1)

Como validador, quero PnL sem executor: **entry** no mid-price close da barra do sinal; **exit** em `validade_ate` / `meia_vida_barras` (τ); **sem flip** (não inverte posição por sinal oposto).

**Why this priority**: Sem fill não existe Sharpe/WR/PF/MaxDD.

**Independent Test**: Fixture 1 LONG + τ conhecido → entry/exit prices e retorno batem referência; sinal oposto com posição aberta → mantém até exit, sem abrir oposta.

**Acceptance Scenarios**:

1. **Given** trigger LONG/SHORT, **When** abre posição, **Then** entry = mid `(bid+ask)/2` no **close** da barra do sinal (equivalente ao close mid da barra).
2. **Given** posição aberta com `meia_vida_barras` / `validade_ate` do payload F5, **When** atinge o horizonte, **Then** exit no mid-close dessa barra (ou da barra em que `validade_ate` cai).
3. **Given** posição aberta, **When** chega sinal na direção oposta, **Then** **não** flip — mantém até exit por τ/`validade_ate` (alinhado ao espírito §3.12.4 sem MCP).
4. **Given** custos, **When** F6 calcula PnL, **Then** **não** inventa spread/comissão além do mid já usado (custo Zero §10.1) — a menos que Marcos acrescente depois.

---

### US4 — Trigger F6 e métricas §10.1 (Priority: P1)

Como validador, quero definir **trigger F6** = payload com `direcao` LONG|SHORT e `confianca` **ALTA ou MÉDIA** (i.e. força **≥ 0.60**); calcular métricas e alvos §10.1; taxa só-ALTA (≥0.75) fica **fora do gate** (diagnóstico F7).

**Why this priority**: Gates mensuráveis do doc.

**Independent Test**: Fixtures de equity/trades → Sharpe (diário, Rf=0, ×√252), WR, PF, MaxDD, trigger_rate, mediana(τ); bordas força 0.59/0.60/0.75.

**Acceptance Scenarios**:

1. **Given** payload, **When** classifica trigger F6, **Then** conta se LONG|SHORT e confianca ∈ {ALTA, MÉDIA} (força ≥ 0.60); NEUTRO / força < 0.60 **não** conta.
2. **Given** resultados por instrumento, **When** métricas, **Then** reporta Sharpe, Win Rate, Profit Factor, Max Drawdown, Taxa de triggers (% barras com trigger F6), mediana(τ) nos triggers.
3. **Given** alvos §10.1, **When** avalia, **Then**: Sharpe **> 0.5**; WR **> 45%**; PF **> 1.3**; MaxDD **< 15%**; taxa triggers **5–15%**; mediana τ **3–8** barras.
4. **Given** Sharpe, **When** calcula, **Then** usa **retornos de equity diária**, **Rf = 0**, anualização **×√252** (não Sharpe em M30 cru).
5. **Given** F6, **When** reporta, **Then** pode expor taxa só-ALTA como campo diagnóstico opcional, **sem** usá-la como gate desta fatia.

---

### US5 — Gate 7/10 + relatório (Priority: P1)

Como validador, quero veredito global §10.1 (**≥7/10** instrumentos com Sharpe **> 0.5**) e relatório JSON-serializável in-memory.

**Why this priority**: Critério de passagem + contrato de saída.

**Independent Test**: Tabela 10 Sharpes → PASS se ≥7; FAIL se 6; schema do relatório.

**Acceptance Scenarios**:

1. **Given** Sharpe por instrumento, **When** `count(Sharpe > 0.5) ≥ 7`, **Then** **PASS**; se `< 7` → **FAIL**.
2. **Given** backtest concluído, **When** emite relatório, **Then** por instrumento: métricas US4, flags vs alvos, + veredito global; sem UI.

### Edge Cases

- Série < warm-up → sem triggers → instrumento **não** passa Sharpe > 0.5.
- Zero triggers → WR/PF indefinidos → falha taxa de triggers; não inventar Sharpe.
- Exit τ além do fim da série → fechar na última barra disponível e logar truncamento.
- High=Low / abort F1 → respeitar camadas anteriores.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: MUST consumir F1→F5; MUST NOT reimplementar ohlc/filters/regime/vol/signal.
- **FR-002**: MUST rodar **sem** TA e **sem** executor MCP.
- **FR-003**: MUST ler histórico **real** via CSV/parquet; MUST NOT acoplar provider HTTP no runner (adapter fora).
- **FR-004**: MUST usar universo **§9.2** (10) e horizonte alvo **5 anos** M30 no dataset de gate.
- **FR-005**: MUST simular PnL: entry mid-close da barra do sinal; exit `validade_ate`/`τ`; **sem flip**.
- **FR-006**: MUST definir trigger F6 = LONG|SHORT ∧ confianca ALTA|MÉDIA (força ≥ 0.60).
- **FR-007**: MUST calcular métricas/alvos literais §10.1; Sharpe = equity diária, Rf=0, ×√252.
- **FR-008**: MUST aplicar gate **≥7/10** Sharpe > 0.5.
- **FR-009**: CI Independent Tests MUST usar fixtures locais sem rede; `seed=42` se houver RNG.
- **FR-010**: Custo runtime F6 = Zero (sem API paga obrigatória no runner).

### Key Entities

- **HistoricalStore**: CSV/parquet por instrumento (formato F1).
- **Fill**: entry/exit mid-close, τ/`validade_ate`, no-flip.
- **InstrumentMetrics**: Sharpe, WR, PF, MaxDD, trigger_rate, tau_median.
- **GateResult**: pass_count/10, veredito PASS|FAIL.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: US1 — payloads F5; suite sem TA/executor/broker.
- **SC-002**: US3 — fill entry/exit/no-flip bate fixture.
- **SC-003**: US4 — métricas + Sharpe √252 + trigger ≥0.60 batem referências; alvos §10.1 com operadores do doc.
- **SC-004**: US5 — gate 7/10 correto; relatório serializável.
- **SC-005**: US2 — lista §9.2 exata; loader só arquivo local.

## Riscos

- Dataset 5 anos real precisa existir fora do git/CI grande — processo de materialização (adapter) não é F6.
- Equity diária a partir de fills M30 exige regra de agregação (último equity do dia) — Plan/tasks devem fixar sem mudar limiares.
- Truncamento de τ no fim da série pode enviesar WR/PF em amostras curtas de teste.

## DIVERGÊNCIA

- Nenhuma vs F5 em `main`.
- Paths: Plan amarra (ex. `src/motor/backtest/`); Spec só `specs/006-f6-backtest-motor-only/`.
- §9.2 adiado em F1 — **F6 ativa a lista** para o gate (não reabre F5).

## NEEDS CLARIFICATION

Nenhum aberto — recomendações fechadas em 2026-09-05 (aguardam trava Marcos).

## Decisões (recomendadas → trava Marcos)

1. **Fonte:** histórico **real** em **CSV/parquet**; provider (OANDA/Polygon/QC/Broker) = **adapter fora** do runner F6.
2. **PnL:** opção **(a)** — entry no **close mid** da barra do sinal; exit em **`validade_ate` / τ**; **sem flip**.
3. **Trigger F6:** ALTA **e** MÉDIA (força **≥ 0.60**). Taxa só-ALTA (≥0.75) = diagnóstico **F7**, não gate F6.
4. **Sharpe:** equity **diária**, **Rf = 0**, anualização **×√252** (não M30 cru).

## Assumptions

- Consolidado v1.2 §10.1 + §9.2; F5 em `main` com locks 0.75/0.60 e NEUTRO com payload.
- Mid = `(bid+ask)/2` (F1).
- TA/executor/FTMO fora.
