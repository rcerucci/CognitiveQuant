# F1 OHLC Implementation Verification (T001-T020)

## Arquivos Implementados

| Arquivo | US | Função |
|---------|-----|--------|
| `src/motor/ohlc/validation.py` | US1, US2 | Valida formato, integridade, ordem temporal, gaps |
| `src/motor/ohlc/transform.py` | US4 | P_t → X_t → r_t (mid → log → return) |
| `src/motor/ohlc/sync.py` | US3 | Merge outer + preenchimento linear multi-instrumento |
| `src/motor/ohlc/__init__.py` | - | API pública exportada |
| `tests/unit/test_ohlc_*.py` | - | Independent Tests US1-US4 |
| `tests/fixtures/ohlc/*.json` | - | Fixtures de teste |

## Requisitos Funcionais (FR-001 a FR-010)

### FR-001: Formato de Entrada
```
[ts_UTC_millis, open, high, low, close, bid, ask]
```

### FR-002: Validação de Formato
- Código de log: `"format_invalido"`
- Abort imediato via `raise ValidationError`

### FR-003: Timestamp UTC
- Unix timestamps em milissegundos são inherentemente UTC
- Validação via `datetime.fromtimestamp(ts/1000.0, tz=timezone.utc)`

### FR-004: Integridade de Preços
- `high >= max(open, close)`
- `low <= min(open, close)`
- Código de log: `"integridade_preco_invalida"`

### FR-005: Ordem Temporal
- Timestamps crescentes
- Sem duplicatas
- Código de log: `"ordem_temporal_invalida"`

### FR-006: Tratamento de Gaps
- Gap ≤ 4 barras: interpolação linear
- Gap > 4 barras: status `"neutro"` + flag `gap_dados`

### FR-007: Weekend Fill
- Forward-fill para gaps de fim de semana
- Flag `"weekend_fill"` adicionada
- Não preencher TR (reserva para F2)

### FR-008: Sync Multi-Instrumento
- União de timestamps via merge outer
- Preenchimento linear nos gaps

### FR-009: Transformação
```python
P_t = (Bid_t + Ask_t) / 2    # Mid-price
X_t = ln(P_t)                # Log-price  
r_t = X_t - X_{t-1}          # Log-return
```

### FR-010: Abort Sem Retry
- `raise ValidationError` imediato
- Sem retry nem bypass

### FR-001b: Preços Devem Ser Positivos ⚠️ BUG CORRIGIR
- Todos os campos de preço (open, high, low, close, bid, ask) devem ser **estritamente positivos (> 0)**
- VALORES ≤ 0 devem ser rejeitados em `validate_ohlc_format()` com `format_invalido`
- `math.isfinite()` retorna True para valores negativos e zero; requer verificação explícita `> 0`

## Success Criteria (SC-001 a SC-004)

| SC | Verificação | Resultado |
|----|-------------|-----------|
| SC-001 | 100% violações → Abort com log correto | ✅ 5/5 testes passam |
| SC-002 | Gap ≤4 → interpolate, Gap >4 → NEUTRO | ✅ 3/3 testes passam |
| SC-003 | Valores transformação baterem fixture | ✅ 3/3 testes passam |
| SC-004 | Nenhum módulo filtro §3.3+ importado | ✅ Verificado |

## Testes de Borda Críticos

### Payload Malformado
- `[]` → `format_invalido`
- `[ts, open, high]` (missing) → `format_invalido`
- `[ts, ..., extra]` (extra) → `format_invalido`
- `["ts", ...]` (string ts) → `format_invalido`
- `[..., 0, ...]` (zero price) → `format_invalido`
- `[..., -0.5, ...]` (negative price) → `format_invalido`

### Valores Especiais
- `NaN` → `format_invalido`
- `Infinity` → `format_invalido` (via isfinite)
- `None` bid/ask → `format_invalido`
- P_t ≤ 0 → `ValueError` no transform (deve ser evitado pela validação)

### Timestamp
- Timestamp negativo → ACEITO (valores UNIX válidos para datas pré-1970)

### Transição de Status (Gap Handling)
- Gap ≤ 4: barra interpolada com flag `"interpolated"`
- Gap 1-4: interpolação linear entre barras adjacentes
- Gap > 4: status `neutro`, flag `gap_dados`
- Weekend gap: flag `weekend_fill` no preço preenchido

## Estrutura de Teste

```
tests/
├── unit/
│   ├── test_ohlc_format_integrity.py  (US1 Independent Test)
│   ├── test_ohlc_order_gaps.py       (US2 Independent Test)
│   ├── test_ohlc_sync.py             (US3 Independent Test)
│   ├── test_ohlc_transform.py        (US4 Independent Test)
│   └── test_success_criteria.py      (SC-001 a SC-004)
└── fixtures/ohlc/
    ├── format_integrity.json
    ├── order_gaps.json
    ├── transform_reference.json
    └── sync_multi.json
```

## Comandos de Verificação

```bash
# Executar todos os testes F1
pytest tests/unit/ -v

# Verificar coverage
pytest tests/ --cov=src/motor --cov-report=term-missing

# Verificar integridade de preços
from motor.ohlc.validation import validate_price_integrity
validate_price_integrity(100, 101, 99, 100)  # True
validate_price_integrity(100, 99, 101, 100)   # False (high < open)

# Verificar rejeição de preços não positivos (edge case) ⚠️ NÃO IMPLEMENTADO
from motor.ohlc.validation import validate_bar
validate_bar([1704067200000, 100, 101, 99, 100, -5, 101])  # DEVE levantar ValidationError
```

## Padrão de Teste para Preços Positivos

```python
def test_positive_prices_required():
    """Preços devem ser estritamente positivos (>0)."""
    # Fixture: barra com preço zero
    bar_zero = [1704067200000, 0, 101, 99, 100, 100.5, 101]
    with pytest.raises(ValidationError) as exc:
        validate_bar(bar_zero)
    assert exc.value.code == "format_invalido"

def test_negative_prices_rejected():
    """Preços negativos devem ser rejeitados."""
    bar_neg = [1704067200000, 100, 101, 99, 100, -5, 101]
    with pytest.raises(ValidationError) as exc:
        validate_bar(bar_neg)
    assert exc.value.code == "format_invalido"
```
