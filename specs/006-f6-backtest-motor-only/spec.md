# Feature Specification: F6 — Backtest motor-only

**Feature Branch**: `006-f6-backtest-motor-only`  
**Created**: 2026-09-05  
**Status**: Ready for Review — US6 aprovado (hotfix); fetch provider pendente  
**Hotfix**: 2026-09-06 — aparelho T001–T027 ≠ experimento §10.1; US6 fecha o run offline + gate 7/10 como aceite  
**Input**: Fatia F6 (Marcos) — mapa Fatiador + consolidado v1.2 **§10.1** (+ lista **§9.2**)  
**Fonte**: Documento consolidado v1.2 (sem reabrir F5)  
**Depende de**: F5 em `main` — pipeline F1→F5 (`src/motor/{ohlc,filters,regime,vol,signal}/`) → payload §3.11 in-memory

## Objetivo

Rodar **backtest histórico motor-only** (§10.1) sobre **histórico real** M30 (CSV/parquet): executar o motor Python puro (**sem** TA, **sem** MCP), simular PnL (entry mid-close → exit `validade_ate`/`τ`, sem flip), calcular métricas/alvos do consolidado e aplicar o **gate Sharpe** (mín. 7/10 com Sharpe > 0.5; Sharpe = equity diária, Rf=0, ×√252). O **aceite §10.1** exige o **experimento offline** (US6) sobre `data/ohlc/` real — não basta a suíte unitária em fixture.

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
- Dataset 5 anos **dentro** do git/CI (fica local/gitignore)
- Provider SDK **dentro** de `src/motor/` (fetch só em `scripts/` ou cópia manual — Plan)
- Começar **F7** antes do relatório do run US6
- Reabrir F5 / mudar limiares de sinal

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


---

### US6 — Experimento offline §10.1 (Priority: P1) *(addendum hotfix 2026-09-06)*

Como validador, quero **executar** o pipeline F6 **offline** apontando para `data/ohlc/` com os **10** arquivos §9.2 (histórico real ~5 anos M30), produzir artefato de relatório (métricas por instrumento + breakdown por ano quando couber) e obter o **veredito gate 7/10** como **critério de aceite** do §10.1 — não apenas código/unit tests em fixture.

**Why this priority**: O pacote T001–T027 entregou o aparelho; o §10.1 exige o **run**. QA em fixture (ex. PR #10) **não** substitui o experimento.

**Independent Test (CI)**: Com `data/ohlc/` **vazio** ou incompleto → comando/CLI do run **FAIL** explícito (não passa silenciosamente); com fixture mínima local (não 5 anos no git) o harness valida schema do artefato. O gate 7/10 sobre 5 anos reais é **aceite offline**, fora do CI obrigatório.

**Acceptance Scenarios**:

1. **Given** `data/ohlc/` com checklist dos **10** arquivos canônicos §9.2 (CSV/parquet, nomes fixados no plan), **When** o run offline executa, **Then** processa os 10 instrumentos via loader→runner→pnl→metrics→report **sem** rede/provider SDK em `src/motor/`.
2. **Given** run concluído, **When** emite artefato, **Then** grava relatório estruturado (path amarrado pelo Plan, ex. `reports/f6_backtest.json`) contendo por instrumento: Sharpe, WR, PF, MaxDD, taxa de triggers F6, mediana τ, taxa só-ALTA (diagnóstico); veredito global `count(Sharpe > 0.5) ≥ 7`; breakdown **por par + por ano** quando a série cobrir múltiplos anos.
3. **Given** `data/ohlc/` vazio, só `.gitkeep`, ou faltando instrumentos / séries **INSUFICIENTE** demais para o gate, **When** o run é invocado, **Then** **FAIL** (exit ≠ 0 / erro explícito) — não inventa Sharpe nem marca PASS.
4. **Given** dataset, **When** versionado, **Then** **MUST NOT** exigir os 5 anos dentro do git; dataset local/gitignore; CI continua só com fixtures pequenas (US1–US5).
5. **Given** F6, **When** materializa dados, **Then** fetch/provider fica em `scripts/` (ou cópia manual) — **fora** de `src/motor/`; Marcos **confirma o provider** proposto pelo Plan **antes** do coder implementar o fetch.
6. **Given** relatório US6 ausente ou gate FAIL por dados, **When** fila Spec Kit, **Then** **não** iniciar F7.

### Edge Cases

- Série < warm-up → sem triggers → instrumento **não** passa Sharpe > 0.5.
- Zero triggers → WR/PF indefinidos → falha taxa de triggers; não inventar Sharpe.
- Exit τ além do fim da série → fechar na última barra disponível e logar truncamento.
- High=Low / abort F1 → respeitar camadas anteriores.
- `data/ohlc/` só `.gitkeep` → run US6 **FAIL** (não é PASS do §10.1).
- Instrumento com horizonte << 5 anos / warm-up dominante → marca **INSUFICIENTE**; não conta para Sharpe > 0.5.

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
- **FR-011**: MUST expor comando/CLI (ou entrypoint) de run offline apontando para `data/ohlc/` (path no plan).
- **FR-012**: MUST emitir artefato de relatório do experimento (ex. `reports/f6_backtest.json` — Plan amarra path) com métricas US4 + só-ALTA diagnóstico + gate 7/10 + breakdown por instrumento e por ano.
- **FR-013**: MUST **FAIL** se `data/ohlc/` vazio/incompleto ou instrumentos INSUFICIENTE demais para avaliar o gate; MUST NOT gravar veredito PASS inventado.
- **FR-014**: MUST NOT exigir dataset 5 anos no git; MUST NOT colocar provider SDK em `src/motor/`.
- **FR-015**: Aceite §10.1 desta fatia = existência do relatório US6 do run offline + avaliação do gate (PASS ou FAIL factual) — suíte unitária sozinha **não** fecha a fatia.

### Key Entities

- **HistoricalStore**: CSV/parquet por instrumento (formato F1).
- **Fill**: entry/exit mid-close, τ/`validade_ate`, no-flip.
- **InstrumentMetrics**: Sharpe, WR, PF, MaxDD, trigger_rate, tau_median.
- **GateResult**: pass_count/10, veredito PASS|FAIL.
- **OfflineRunReport**: artefato US6 (por instrumento, por ano, gate, só-ALTA diagnóstico).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: US1 — payloads F5; suite sem TA/executor/broker.
- **SC-002**: US3 — fill entry/exit/no-flip bate fixture.
- **SC-003**: US4 — métricas + Sharpe √252 + trigger ≥0.60 batem referências; alvos §10.1 com operadores do doc.
- **SC-004**: US5 — gate 7/10 correto; relatório serializável.
- **SC-005**: US2 — lista §9.2 exata; loader só arquivo local.
- **SC-006**: US6 — com `data/ohlc/` incompleto, run FAIL; com dataset real materializado, artefato contém 10 instrumentos + métricas + gate; F7 não parte sem esse artefato.

## Riscos

- Dataset 5 anos real precisa existir fora do git/CI grande — processo de materialização (adapter) não é F6.
- Equity diária a partir de fills M30 exige regra de agregação (último equity do dia) — Plan/tasks devem fixar sem mudar limiares.
- Truncamento de τ no fim da série pode enviesar WR/PF em amostras curtas de teste.

## DIVERGÊNCIA

- Nenhuma vs F5 em `main` (não reabrir F5).
- **Aceite §10.1 incompleto**: aparelho `src/motor/backtest/` + testes em fixture ≠ experimento 5 anos; `data/ohlc/` só `.gitkeep` — US6 fecha o buraco.
- Paths do hotfix: Plan amarra CLI, `reports/`, `scripts/` (fetch), nomes canônicos dos 10 arquivos; Spec só `specs/006-f6-backtest-motor-only/`.
- §9.2 ativo para o gate (não reabre F5).

## NEEDS CLARIFICATION

1. **Fetch provider:** Plan propôs **QuantConnect** (alt. OANDA). Marcos ainda **não** confirmou — T034 fica **stub**; fetch real só após confirmação. Cópia manual dos 10 `.parquet` já desbloqueia o run.

## Decisões (locks)

1. **Fonte:** histórico **real** CSV/parquet sob `data/ohlc/`; provider/`scripts/` **fora** de `src/motor/`.
2. **PnL:** **(a)** — entry **close mid**; exit **`validade_ate` / τ**; **sem flip**.
3. **Trigger F6:** ALTA|MÉDIA (força **≥ 0.60**). Só-ALTA (≥0.75) = diagnóstico no relatório, não gate.
4. **Sharpe:** equity **diária**, **Rf = 0**, **×√252**.
5. **Aceite §10.1 (US6 aprovado 2026-09-06):** run offline `data/ohlc/` + artefato `reports/f6_backtest.json` + gate 7/10; CI fixture ≠ fechamento; dataset/reports **fora** do git; **F7 bloqueada** até o relatório.
6. **Canônicos `data/ohlc/`:** `eur_usd`, `gbp_jpy`, `usd_cad`, `aud_nzd`, `us500`, `ger30`, `jp225`, `xau_usd`, `usoil`, `nas100` + `.parquet`.
7. **CLI:** `f6-backtest --data-dir data/ohlc --out reports/f6_backtest.json` (run **não** CI).
8. **Hotfix tasks:** T028–T033 aprovados; T034 = stub até confirmação QuantConnect.

## Assumptions

- Consolidado v1.2 §10.1 + §9.2; F5 em `main` com locks 0.75/0.60 e NEUTRO com payload.
- Mid = `(bid+ask)/2` (F1).
- TA/executor/FTMO fora; F7 só depois do artefato US6.
- Run US6 é offline/local — **não** é job CI obrigatório com 5 anos.
