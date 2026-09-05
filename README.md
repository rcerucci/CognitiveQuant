# CognitiveQuant

Sistema autônomo de sinais quantitativos (motor → TradingAgents → executor / paper trade).

## Spec Kit

Documentação de fatias em `specs/<fatia>/`:
- `spec.md`
- `plan.md`
- `tasks.md`

Pipeline: Fatiador → Spec → Plan → Tasks → Dispatch → Hermes (coderbot → qabot).

PRs de documentação: preferir mudanças sob `specs/`.
Código de trading: branches `feature/<fatia>` (nunca push direto em `main` sem aprovação).
