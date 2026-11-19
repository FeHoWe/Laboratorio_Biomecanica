# NEXUS BIOMECHANICS (v0.2.0 — Fase 1: Foundation)
Plataforma de pesquisa e aprendizado computacional em biomecânica. **Não é dispositivo médico.**

## Estado real (Fase 1)
Implementado e testado: janela principal, menus, sistema de projetos (criar/abrir/salvar/salvar como/fechar), árvore de componentes, painel de propriedades, console de logs, configurações, diagnóstico de ambiente.
**Núcleo matemático (Fase 3, sem interface ainda):** unidades, transformações 4x4, cinemática direta/inversa/Jacobiano/trajetória de mínimo jerk (2 segmentos), torque estático, dinâmica de Lagrange com RK4. Validado por 44 testes (soluções analíticas, período de pêndulo, conservação de energia).
**Planejado (não implementado):** viewport 3D, BIO-001, gráficos, CSV/PDF, MuJoCo/OpenSim, IA. Itens de menu correspondentes ficam desabilitados e marcados "planejado".

Execução: `python main.py` — Testes: `python -m pytest`. Veja INSTALLATION.md.
