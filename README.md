# NEXUS BIOMECHANICS — v1.0.0-rc1 (release candidate)

Plataforma de pesquisa e aprendizado computacional em biomecânica (Windows 11, Python + PySide6, tema escuro, PT-BR).
**Não é dispositivo médico e não faz afirmações de precisão clínica.** Todos os parâmetros padrão (comprimentos, massas, limites articulares, atuador) são **DEMONSTRATIVOS** (hipotéticos, sem fonte científica verificada) até que você informe fontes.

Execução: `python main.py` · Testes: `python -m pytest` (127 testes) · Instalação: veja `INSTALLATION.md`.

---

## O que existe hoje (v1.0.0-rc1)

> Esta é uma *release candidate*: toda a funcionalidade planejada que dá para construir e testar aqui está pronta, mas **a 1.0.0 final depende de itens que não consegui verificar** (veja `ACCEPTANCE.md`).

| Módulo | Onde | O que faz |
|---|---|---|
| Projetos | Arquivo | Criar, abrir, salvar, salvar como, fechar; pasta com `project.json` (gravação atômica + `.bak`), recentes, árvore de componentes, propriedades, console de logs. |
| Núcleo matemático | `simulation/`, `biomechanics/`, `core/` | Unidades SI, transformações 4x4, cinemática direta/inversa/Jacobiano, trajetória de mínimo jerk, dinâmica inversa/direta de Lagrange (RK4) para 2 e N segmentos. |
| Modelo de membro inferior 3D | Modelo → Novo modelo de membro inferior | Pelve, fêmur, tíbia, fíbula, pé; quadril/joelho/tornozelo com limites configuráveis; viewport 3D real (VTK/PyVista), pose por sliders, CM e projeção no solo. Se não houver OpenGL, o app informa o motivo (não simula 3D). |
| BIO-001 | Pesquisa | Compara dois mecanismos de 2 segmentos: animação 2D, gráficos, CSV, PNG, relatório .md e PDF. |
| BIO-002 | Pesquisa | Mesma comparação com 3 segmentos (humano: quadril/joelho/tornozelo; animal: quadril/joelho/jarrete), CSV, .md, PNG, PDF. |
| SIM-001 | Simulação | Dinâmica passiva (pêndulo duplo, RK4) em thread separada, com progresso, cancelamento e deriva de energia. |
| EXO-001 | Pesquisa (Ctrl+Shift+E) | Assistência articular por exoesqueleto: atuador com curva torque-velocidade e eficiência; modos proporcional e gravidade; torque sem exo × com exo × humano residual; potência e energia do atuador; avisos de saturação; CSV, .md, PNG, PDF. |
| Importação de STL | Modelo → Importar malha STL… | Lê STL binário/ASCII (validação, soldagem de vértices, limites defensivos), pede a unidade (mm/cm/m/in), copia para `models/`, mostra triângulos, caixa limite, área e volume (só se a malha for fechada) e renderiza no 3D. Geometria **apenas visual**: não entra nos cálculos. |
| Análise por IA (arquitetura) | Análise | Contratos e registro de provedores com rótulo obrigatório "gerado por IA", procedência e limitações. **Nenhum provedor incluído**: o item de menu fica desabilitado até haver um. |
| Histórico SQLite | Pesquisa → Histórico (Ctrl+H) | Índice `history.db` (derivado do `project.json`): filtrar por tipo e ordenar por qualquer métrica do resumo. |
| Versão celular | Artefato web | Página única com Projeto, Árvore, Cinemática, Modelo 2D, **3D (com STL somente visualização)**, BIO-001, BIO-002, EXO-001, SIM-001, **Histórico** e Console. Projetos do celular abrem no desktop. |

Experimentos ficam salvos no projeto e são **reexecutáveis de forma determinística**.

### Limitações atuais (reais)
- Parâmetros demonstrativos; sem validação experimental. Modelos 2D no plano sagital, sem músculos, atrito, folgas ou contato com solo. Sem controle em malha fechada no exoesqueleto.
- Não verificado: execução e `.exe` no Windows; build PyInstaller com VTK; seleção de segmentos por clique do mouse no 3D; gestos de toque no celular em aparelho real (só jsdom); aparência dos gráficos num monitor real.
- Não implementado (itens de menu desabilitados e marcados "planejado"): MuJoCo/OpenSim, importação STEP, provedor de IA (só a arquitetura existe), PDF do SIM-001, parâmetros com fontes científicas.
- STL no celular: somente visualização (não é salvo no projeto); exibe no máximo ~4000 triângulos por quadro (amostragem) por desempenho.

---

## Histórico de versões

### 1.0.0-rc1 — Release candidate (127 testes) — pulou as versões 0.11 a 0.99 a pedido
Reúne o que estava planejado para as versões intermediárias:
- Novo: **importação de STL** (desktop e celular). Desktop: parser com validação (binário/ASCII, tamanho inconsistente, NaN/Inf, triângulos degenerados, limites de 200 MB e 2.000.000 triângulos), cópia para `models/` sem sobrescrever, estatísticas, render 3D (conferido em display virtual), tratamento de erro para arquivo ausente. Celular: mesmo leitor em JS, conferido contra os valores do Python (cubo: área, volume, fechamento).
- Novo: **arquitetura do módulo de IA** (`artificial_intelligence/`): `Analyzer`, `AnalyzerRegistry`, `AnalysisRequest/Result`, rótulo obrigatório, erros de provedor tratados, nenhum provedor incluído.
- Novo: `ACCEPTANCE.md` com o estado real de cada módulo e o que impede a 1.0.0 final.
- Mudado: versão `1.0.0-rc1` (e não `1.0.0`) porque os critérios do master prompt não estão todos verificados (Windows, fontes científicas, MuJoCo/OpenSim).
- Corrigido: o menu "Importar STL" deixou de ser item "planejado".

Cada versão foi entregue como ZIP próprio (`NEXUS_BIOMECHANICS_vX.Y.Z.zip`; a 0.1.0 é `..._fase1.zip`). Número de testes = testes automatizados passando na entrega.

### 0.10.0 — Histórico de experimentos em SQLite (127 testes)
- Novo: `history.db` na pasta do projeto, índice **derivado** do `project.json` (reconstruído ao criar/abrir/salvar; pode ser apagado; banco corrompido não impede abrir o projeto, só gera aviso). "Salvar como" não copia o índice antigo.
- Novo: consulta por tipo e ordenação por métrica numérica do resumo (listas viram `chave[i]`). Menu Pesquisa → Histórico de experimentos (Ctrl+H); duplo clique seleciona o experimento na árvore.
- Celular: aba **Histórico** (mesma consulta sobre o `project.json`, em JS; o celular não usa SQLite). A achatagem de métricas do JS coincide com a do Python.
- Não verificado: desempenho com milhares de experimentos; Windows.

### 0.9.0 — Vista 3D no celular (106 testes)
- Novo (celular): aba **3D** com render por software em canvas (sem biblioteca externa) do membro inferior: arrastar gira a câmera; dois dedos ou roda do mouse dão zoom e deslocam; grade, eixos, CM com projeção no solo; sliders de pose com limites; toque em um segmento o seleciona e mostra comprimento, massa, CM e fonte.
- Verificado: a geometria 3D do celular coincide com a do Python (4 poses, tolerância 1e-9); seleção, câmera e sincronia dos sliders testadas com jsdom.
- Diferenças do desktop: sem VTK/OpenGL (sombreamento simples), sem STL. Gestos de toque não testados em aparelho real.

### 0.8.0 — Relatório PDF para BIO-002 e EXO-001 (105 testes)
- Novo: "Exportar relatório PDF" vale para BIO-001, BIO-002 e EXO-001 (texto do relatório técnico + gráficos). SIM-001 continua sem PDF.
- PDF conferido visualmente em Linux; aparência no Windows não verificada. Celular: sem PDF (só desktop).

### 0.7.0 — EXO-001: Exoesqueleto (104 testes)
- Novo: módulo `exoskeleton/` com atuador de junta (curva torque-velocidade linear, eficiência) e o experimento EXO-001 (dinâmica inversa sem/com a massa do exoesqueleto; assistência proporcional ou de gravidade com ganho; saturação com aviso; torque humano residual, potência e energia elétrica do atuador; CSV, .md, PNG, registro e reexecução no projeto).
- Celular: aba EXO-001 (resultados conferidos contra o Python); projetos do celular com EXO-001 reproduzem no desktop.

### 0.6.0 — BIO-002: comparação com 3 segmentos (94 testes)
- Novo: dinâmica de Lagrange para cadeia planar de N segmentos (validada contra o modelo de 2 segmentos em 25 poses aleatórias e contra soluções analíticas e conservação de energia para N=3).
- Novo: BIO-002 humano (coxa, perna, pé) × animal (fêmur, tíbia, metatarso/jarrete): animação, gráficos por junta, CSV, .md, registro e reexecução.
- Celular: aba BIO-002, conferida numericamente com o Python.

### 0.5.0 — Viewport 3D e modelo de membro inferior (80 testes)
- Novo: modelo de membro inferior (pelve, fêmur, tíbia, fíbula, pé) com limites articulares configuráveis, cinemática direta 4x4 e CM.
- Novo: viewport 3D real (VTK/PyVista via pyvistaqt): câmera, eixos, grade, CM e projeção no solo, painel de Pose; modelo salvo no projeto. Sem OpenGL, o viewport informa o motivo.
- Celular: vista sagital 2D do mesmo modelo; projetos do celular abrem no desktop e reproduzem os resultados (testado).
- Verificado: render 3D em display virtual (Xvfb). Não verificado: seleção por clique no 3D; build PyInstaller com VTK; Windows.

### 0.4.0 — Workers, SIM-001, PDF e empacotamento (63 testes)
- Novo: workers (QThread) com barra de progresso e cancelamento; SIM-001 dinâmica passiva (RK4) fora da thread da interface, com deriva de energia reportada.
- Novo: relatório PDF do BIO-001; experimentos SIM-001 salvos e reexecutáveis.
- Novo: `nexus.spec` + `build_windows.bat` (PyInstaller). Verificado em Linux (build e inicialização do binário); o `.exe` do Windows deve ser gerado no seu PC.
- Corrigido: decimação de amostras (teto, não piso), detectada por teste.

### 0.3.0 — BIO-001 Comparative Joint Mechanics (55 testes)
- Novo: experimento BIO-001 (2 modelos de 2 segmentos), diálogo de parâmetros, animação 2D dirigida pelos cálculos, gráficos (ângulo, velocidade, torque), comparação A × B, exportação CSV/PNG/relatório .md, experimentos salvos e reexecutáveis (determinísticos).
- Corrigido: a ação "Reexecutar" não atualizava ao selecionar item na árvore.

### 0.2.0 — Núcleo matemático (44 testes)
- Novo: unidades, transformações, cinemática planar (direta/inversa/Jacobiano, mínimo jerk), torque/momento/CM, dinâmica de Lagrange (RK4). Validado com soluções analíticas, período de pêndulo e conservação de energia. Documentação de métodos (`SIMULATION_METHODS.md`).

### 0.1.0 — Foundation (26 testes)
- Novo: estrutura de camadas, app PySide6 com tema escuro, menus, projetos (criar/abrir/salvar/salvar como/fechar), árvore de componentes, propriedades, console de logs, configurações, diagnóstico de ambiente, documentação inicial.

---

## Para virar 1.0.0 final
Veja `ACCEPTANCE.md`: verificar o `.exe` no Windows 11, informar fontes científicas para os parâmetros, e decidir sobre MuJoCo/OpenSim. Depois, trocar a versão em `application/version.py`.

Documentação: `ACCEPTANCE.md`, `ARCHITECTURE.md`, `USER_GUIDE.md`, `SIMULATION_METHODS.md`, `INSTALLATION.md`, `CHANGELOG.md`.
