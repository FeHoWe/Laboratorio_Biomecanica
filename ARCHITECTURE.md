# Arquitetura
Camadas: `interface` (PySide6) -> `application` (projetos, eventos, bootstrap) -> `core`/módulos científicos (sem Qt) ; `infrastructure` (logs, futuro SQLite/workers).
- Regra: nenhum cálculo científico em `interface`.
- `EventManager`: pub/sub simples; a UI reage a eventos de projeto.
- Formato de projeto: pasta com `project.json` (schema v1, validado em `core/validation/project_schema.py`) + `models/ experiments/ results/ exports/`. Gravação atômica + `.bak`.
- Pastas de módulos futuros existem com `__init__.py` marcado "Planejado".
Desvios da estrutura do prompt: nenhum relevante; `docs/` adicionada. Versão 0.1.0 (1.0.0 só após critérios de aceitação).
