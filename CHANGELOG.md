# Changelog
## 1.0.0-rc1 — Release candidate (pulou 0.11–0.99 a pedido)
- Importação de STL (desktop e celular) com validação e estatísticas; malha apenas visual.
- Arquitetura do módulo de IA (sem provedor; rótulo obrigatório "gerado por IA").
- ACCEPTANCE.md: estado real por módulo. Versão marcada rc1 porque Windows, fontes científicas e MuJoCo/OpenSim não estão verificados/implementados.
- 127 testes.
## 0.10.0 — Histórico de experimentos em SQLite
- `history.db` na pasta do projeto: índice derivado do project.json (reconstruído a cada criar/abrir/salvar; pode ser apagado; banco corrompido não impede abrir o projeto — só gera aviso). project.json continua sendo a fonte da verdade; "Salvar como" não copia o índice antigo.
- Consulta por tipo e ordenação por qualquer métrica numérica do resumo (listas viram `chave[i]`). Menu Pesquisa → Histórico de experimentos (Ctrl+H); duplo clique seleciona o experimento na árvore.
- Mobile: aba Histórico (mesma consulta sobre o project.json, em JS; o celular não usa SQLite). A achatagem de métricas do JS coincide com a do Python.
- 113 testes. Não verificado: desempenho com milhares de experimentos; Windows.
## 0.9.0 — Vista 3D no celular
- Aba "3D" no celular: render 3D por software (canvas, sem biblioteca externa) do mesmo membro inferior: câmera orbitável (arrastar), zoom/deslocar (dois dedos ou roda do mouse), grade, eixos, CM com projeção no solo, sliders de pose com limites, seleção de segmento por toque (mostra comprimento, massa, CM e fonte).
- A geometria 3D do celular coincide com a do Python (4 poses, tolerância 1e-9) e é testada com jsdom (picking, câmera, sincronia dos sliders).
- Diferenças do desktop: o celular não usa VTK/OpenGL (sombreamento simples, cilindros desenhados como traços); sem malhas STL. Não verificado em aparelho real (só jsdom); gestos de toque não foram testados em dispositivo.
## 0.8.0 — Relatório PDF para BIO-002 e EXO-001
- "Exportar relatório PDF" agora vale para BIO-001, BIO-002 e EXO-001 (texto do relatório técnico + gráficos). SIM-001 continua sem PDF (usa .md/CSV); pedir PDF dele dá erro claro.
- 105 testes. PDF conferido visualmente em Linux; aparência no Windows não verificada. Mobile: sem PDF (só desktop).
## 0.7.0 — EXO-001: Exoesqueleto Lab (Fase 6, início)
- Atuador de junta com curva torque-velocidade linear e eficiência (DEMONSTRATIVO); módulo `exoskeleton/`.
- EXO-001: dinâmica inversa da cadeia de 3 segmentos sem e com a massa do exoesqueleto; assistência proporcional ou de gravidade com ganho; saturação pela curva τ-ω (com aviso); torque humano residual, potência mecânica e energia elétrica do atuador; CSV, relatório .md, PNG, registro e reexecução no projeto.
- Mobile: aba EXO-001 (resultados conferidos contra o Python); projetos do celular com EXO-001 reproduzem no desktop.
- 104 testes. Não verificado: Windows, build com VTK, controle em malha fechada (não existe), validação experimental.
## 0.6.0 — BIO-002: comparação com 3 segmentos (Fase 4)
- Dinâmica de Lagrange para cadeia planar de N segmentos (validada contra o modelo de 2 segmentos em 25 poses aleatórias, e contra soluções analíticas e conservação de energia para N=3).
- BIO-002: humano (coxa, perna, pé) vs. animal (fêmur, tíbia, metatarso/jarrete): animação, gráficos por junta, CSV, relatório .md, registro e reexecução no projeto.
- Mobile: aba BIO-002 (mesmos resultados do Python, conferido numericamente); projetos do celular com BIO-002 reproduzem no desktop.
- 94 testes. Pendente: PDF do BIO-002, ajuste fino de parâmetros com fontes científicas, MuJoCo/OpenSim, IA, Windows.
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
