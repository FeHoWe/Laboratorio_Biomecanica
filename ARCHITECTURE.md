# Arquitetura (v1.1.0)
Camadas: `interface` (PySide6) → `application` (projetos, eventos, bootstrap) → módulos científicos sem Qt (`core`, `biomechanics`, `simulation`, `research`, `exoskeleton`, `artificial_intelligence`) → `infrastructure` (logs, workers QThread, SQLite).
- Regra: nenhum cálculo científico em `interface`.
- `EventManager`: pub/sub simples; a UI reage a eventos de projeto.
- Formato de projeto: pasta com `project.json` (schema v1, `core/validation/project_schema.py`) + `models/ experiments/ results/ exports/` (+ `history.db` derivado). Gravação atômica + `.bak`. Experimentos guardam id, tipo, parâmetros, resumo e arquivo de resultados; reexecução é determinística.
- Motor espacial (V1.1): `biomechanics/spatial/` (rotations, quaternions, transforms, coordinate_frames, rigid_body, spatial_joints, spatial_chain, spatial_jacobian, spatial_dynamics) → `simulation/spatial_kinematics/` (kinematics, inverse, trajectories), `simulation/spatial_dynamics/`, `simulation/numerical_integrators/` (RK4, DOP853), `simulation/validation/` (verificações), `simulation/physics_engines/` (MuJoCo opcional). Modelo: `biomechanics/human_model/spatial_lower_limb.py`. Experimento: `research/experiments/bio003.py`.
- Visualização: `visualization/viewport_3d/` (`scene.py` modelo sagital e STL; `spatial_scene.py` cena dinâmica por `user_matrix`; `playback.py` controlador sem Qt), `interface/widgets/spatial_player.py`, `interface/widgets/viewport3d.py`.
- Modelos são dicionários com "name"; tipos: "lower_limb", "stl_mesh". Formatos antigos continuam abrindo (nenhuma migração foi necessária na V1.1).
- Celular: `mobile/index.html` (também publicado como artefato); testado com jsdom e conferido numericamente contra o Python.
Detalhes do motor espacial: `SPATIAL_ENGINE.md`.
