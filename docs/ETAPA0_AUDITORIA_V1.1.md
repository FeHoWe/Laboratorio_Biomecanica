# ETAPA 0 — Auditoria e proteção (V1.1.0, origem: v1.0.0-rc1)

Data: 2026-11-19. Nenhum código de produção foi alterado nesta etapa.

## Proteção
- O projeto **não é um repositório Git** (`git rev-parse` falhou). Em vez de branch, foi feita **cópia de segurança completa**: `NEXUS_BIOMECHANICS_backup_v1.0.0-rc1/` (fora da pasta de trabalho, sem `__pycache__`). O ZIP `NEXUS_BIOMECHANICS_v1.0.0-rc1.zip` também permanece intacto.
- Se você preferir Git: `git init` na pasta e `git checkout -b feature/v1.1-3d-biomechanics` (não executei para não criar histórico sem você pedir).

## Baseline de testes (antes de qualquer mudança)
- Executados: **127**; aprovados: **127**; falhas: **0**; tempo ≈ 21 s (Linux, Python 3.13.18, QT offscreen).
- Por arquivo: test_main_window 18, test_math_core 18, test_project_manager 13, test_bio001 9, test_lower_limb 9, test_stl 9, test_exo001 8, test_mobile_compat 8, test_workers_and_sim 8, test_chain_dynamics 7, test_bio002 5, test_history 5, test_infrastructure 4, test_ai_architecture 3, test_scene_3d 3.
- Ambiente: o 3D real só foi exercitado em display virtual (Xvfb) e em teste offscreen; **nada foi rodado no Windows**.

## Dependências
| Pacote | Estado no ambiente | Em requirements.txt |
|---|---|---|
| PySide6 6.12.0, numpy 2.5.3, matplotlib 3.11.2, vtk 9.7.2, pyvista 0.49.2, pyvistaqt 0.14.0, pytest 9.1.1, pytest-qt 4.5.0 | presentes | sim |
| **scipy 1.18.1** | presente | **não** (hoje o código não usa; precisará entrar se `solve_ivp` for usado) |
| sympy, pyqtgraph | ausentes | não (não usados) |
| **mujoco, opensim** | **ausentes** | não |

## Inventário (89 arquivos .py fora de tests, ≈ 4.200 linhas)
- Matemática planar: `simulation/kinematics/planar.py` (TwoLink, min_jerk), `biomechanics/force_engine/planar_dynamics.py` (PlanarArm), `chain_dynamics.py` (PlanarChain, N elos, Lagrange com ∂M/∂q numérico h=1e-6).
- Geometria 3D já existente e **reutilizável**: `core/geometry/transforms.py` (rot_x/y/z, homogeneous, compose, invert, apply, is_rotation).
- Modelo 3D atual: `biomechanics/human_model/lower_limb.py` — **cinemática 3D, mas somente sagital** (3 rotações em torno de z; z só é usado para largura da pelve e deslocamento visual da fíbula). **Não há dinâmica espacial.**
- Pastas ainda vazias (só `__init__.py`): `biomechanics/{joints,motion_engine,muscles,segments}`, `simulation/{dynamics,physics,validation}`, `bioinspired/*`.
- Contratos entre módulos (imports): `interface → application → research/biomechanics/simulation/core`; experimentos usam `PlanarChain`, `min_jerk`, `Actuator`; `scene.py` (VTK) usa `LowerLimbModel`. A interface não contém cálculo científico.
- Projeto: `project.json` schema **v1**; `models` aceita qualquer objeto com `name` → um novo tipo de modelo (`spatial_*`) **não exige mudança de schema nem migração**. Modelos antigos (`lower_limb`, `stl_mesh`) continuam abrindo.

## Problemas e inconsistências encontrados (a corrigir na documentação durante a V1.1)
1. `ARCHITECTURE.md` está **desatualizado** (diz v0.1.0, cita pastas "Planejado" e uma pasta `docs/` que não existia). Será atualizado.
2. `requirements.txt` tem cabeçalho "Fase 3" e não lista scipy.
3. `SIMULATION_METHODS.md` descreve só o planar; precisa de seção espacial (`SPATIAL_ENGINE.md` será criado).
4. `LowerLimbModel` mistura geometria sagital com visual 3D; para o novo motor, o modelo espacial será **novo** (não substitui o antigo).
5. Não verificados desde a rc1: Windows/PyInstaller com VTK, clique do mouse no 3D, gestos de toque no celular.

## Plano proposto (decisões de projeto para as próximas etapas)
- **Preservar** tudo que existe; o planar continua. O motor novo fica em `biomechanics/spatial/` e `simulation/{spatial_kinematics,spatial_dynamics,numerical_integrators,validation}`, reutilizando `core/geometry/transforms.py`.
- **Convenções** (iguais às do modelo atual, para compatibilidade): mundo x anterior, y para cima, z lateral direita; gravidade −y (g = 9,80665 m/s²); SI; ângulos em rad internamente.
- **Juntas:** revoluta/prismática/fixa com coordenada generalizada; **esférica** como 3 revolutas sequenciais (documentando a singularidade de Euler) e quaternion para orientação/conversões; limites configuráveis.
- **Dinâmica:** M = Σ(mᵢ Jvᵢᵀ Jvᵢ + Jwᵢᵀ Iᵢ Jwᵢ) com Iᵢ no referencial mundo; G = ∂U/∂q; Coriolis via ∂M/∂q (diferenças centrais, com precisão e custo medidos; alternativa analítica se necessário). Validar contra o `PlanarChain` (mesmo sistema no plano), pêndulo físico, pêndulo esférico/duplo e conservação de energia.
- **Integração:** RK4 próprio (já testado) + `scipy.solve_ivp` opcional; scipy entra em requirements.txt apenas se usado. Workers (QThread) reaproveitam `TaskThread`.
- **MuJoCo:** **não está instalado**. Na Etapa 6 tentarei instalar no ambiente; se funcionar, crio o adaptador opcional e comparo com o motor interno; se não, o módulo fica marcado "planejado". Nenhum resultado de MuJoCo será simulado.
- **BIO-003** só depois do núcleo validado (Etapas 1–4); BIO-004 não será implementado (conforme o prompt).

## Observação sobre o prompt recebido
O texto do arquivo anexo termina cortado na seção 20 ("Não apresente s…"). Interpretei como: começar pela Etapa 0 e apresentar esta auditoria antes de implementar. Se havia outra instrução no trecho final, me envie.

## Critérios de saída da Etapa 0
[x] Projeto analisado · [x] documentos lidos (README, ARCHITECTURE, ACCEPTANCE, SIMULATION_METHODS, CHANGELOG, requirements) · [x] cópia de segurança · [x] baseline de testes (127/127) · [x] dependências e contratos mapeados.
