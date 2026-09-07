# ADDENDUM F1 — gap de sessão ≠ buraco de dados
Data: 2026-09-07
Lock Marcos

## Regra
Em FX 24×5 (e ouro no mesmo calendário):
intervalo entre duas barras consecutivas que caia em
  [36 h , 72 h]
e atravesse sábado e/ou domingo UTC
NÃO liga gap_dados / series_has_gaps.

## Continua gap (F1 abort / F2 NEUTRO)
- buraco intra-sessão > 4 × 30 min (ex.: 3 h no meio de terça)
- buraco > 72 h (feed morto)
- timestamp não monótono

## Janela
As 200 barras são as 200 **existentes**. Não interpolar fim de semana.

## Fora
Não preencher OHLC de sábado.
Não mudar ADF, τ, CLV, RB.
Não M15.
