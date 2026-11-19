# Changelog
## 0.5.0 — Viewport 3D e modelo de membro inferior (Fase 2)
- Modelo de membro inferior (pelve, fêmur, tíbia, fíbula, pé; quadril/joelho/tornozelo) com limites articulares configuráveis, cinemática direta 4x4 e CM. Parâmetros DEMONSTRATIVOS.
- Viewport 3D real (VTK/PyVista via pyvistaqt): câmera (rotação/zoom/pan), eixos, grade, CM e projeção no solo, painel de Pose com sliders. Modelo salvo no projeto.
- Se não houver contexto OpenGL, o viewport informa o motivo (não simula 3D).
- Mobile: vista sagital 2D do mesmo modelo; projetos do celular abrem no desktop e reproduzem os resultados (testado).
- 80 testes. Verificado: render 3D em display virtual (Xvfb).
- NÃO verificado: seleção por clique do mouse no 3D; build PyInstaller com VTK; Windows.
## 0.4.0 — Workers, SIM-001, PDF, empacotamento
- Workers (QThread) com barra de progresso e cancelamento; SIM-001 dinâmica passiva (RK4) roda fora da thread da interface; deriva de energia reportada.
- Relatório PDF do BIO-001. Experimentos SIM-001 salvos no projeto e reexecutáveis.
- Empacotamento: nexus.spec + build_windows.bat (PyInstaller). Verificado em Linux (build + inicialização do binário); o .exe do Windows deve ser gerado no seu PC.
- 63 testes. Corrigido: decimação de amostras (teto, não piso) detectada por teste.
## 0.3.0 — BIO-001 Comparative Joint Mechanics
Experimento BIO-001 (2 modelos de 2 segmentos, parâmetros DEMONSTRATIVOS), diálogo de parâmetros, animação 2D dirigida pelos cálculos, gráficos (ângulo, velocidade, torque), comparação A vs B, exportação CSV/PNG/relatório .md, experimentos salvos no projeto e reexecutáveis (determinísticos). 55 testes. Corrigido: ação "Reexecutar" não atualizava ao selecionar item na árvore.
Pendente: viewport 3D (VTK/PyVista), PDF, workers/barra de progresso, PyInstaller, SQLite, MuJoCo/OpenSim, IA.
## 0.2.0 — Fase 3 Núcleo matemático
Unidades, transformações, cinemática planar, torque/momento/CM, dinâmica de Lagrange (RK4). 44 testes. Documentação de métodos.
## 0.1.0 — Fase 1 Foundation
Estrutura, app PySide6 tema escuro, projetos, logs, 26 testes, documentação inicial.
