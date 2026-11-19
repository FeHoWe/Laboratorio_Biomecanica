# Guia do usuário (Fase 1)
Arquivo > Novo projeto: informe nome, descrição e local (cria uma pasta). Editar > Renomear (F2) ou painel Propriedades > Aplicar. Salvar: Ctrl+S. Ferramentas > Diagnóstico mostra bibliotecas presentes/ausentes.

## EXO-001 — Exoesqueleto
Pesquisa → Novo experimento EXO-001. Escolha junta, modo (proportional = fração do torque requerido; gravity = fração do torque de gravidade), ganho, massas adicionadas por segmento e parâmetros do atuador (τ de bloqueio, ω sem carga, η). O gráfico mostra o torque da junta sem exo, com exo sem assistência e humano com assistência, e o torque do atuador contra seu limite τ-ω. Se o atuador saturar, há aviso. Hipóteses: exo rígido e alinhado, sem atrito/folgas/músculos; todos os valores são DEMONSTRATIVOS.

## Importar malha STL
Modelo → Importar malha STL…, escolha o arquivo e a unidade das coordenadas (mm, cm, m ou in). O app valida o arquivo, copia para a pasta `models/` do projeto e mostra triângulos, caixa limite, área e volume (volume só para malhas fechadas). A malha é apenas visual: não entra em nenhum cálculo. Clique no item da malha na árvore para exibi-la de novo. No celular, a aba 3D tem a mesma leitura, só para visualização (não é salva).

## Análise por IA
A arquitetura existe, mas nenhum provedor está incluído; por isso Análise → "Análise assistida por IA" fica desabilitado. Quando houver um provedor, toda saída virá rotulada como "Gerado por IA — não validado", com provedor, modelo e limitações, e nunca entra nos cálculos.

## BIO-003 — Dinâmica espacial do membro inferior (3D)
Pesquisa → Novo experimento BIO-003 (Ctrl+Alt+B). Preencha: segmentos (comprimento, massa, CM como fração de L) e, por grau de liberdade (quadril flexão/abdução/rotação, joelho, tornozelo dorsiflexão/inversão): limites, pose inicial (°), velocidade inicial (°/s), torque constante e senoidal (N·m, Hz). Defina gravidade, duração, passo e integrador (rk4 ou adaptive). A simulação roda em segundo plano (cancelável).
Resultado: gráficos (ângulo, velocidade, aceleração, torque, potência, energias), resumo com deriva de energia e balanço trabalho×energia, e animação 3D (aba "Reprodução 3D": reproduzir/pausar/reiniciar, velocidade, câmera, eixos locais, CM). Sem torques a energia mecânica deve se conservar (a deriva é reportada). Limites articulares **não** são impostos: ultrapassagens são avisadas. Reexecutar: selecione o experimento na árvore → Pesquisa → Reexecutar (mesmo resultado).
Opcional: com `pip install mujoco`, Simulação → Comparar último BIO-003 com MuJoCo (só dinâmica livre). Parâmetros DEMONSTRATIVOS; sem precisão clínica.
No celular: aba BIO-003 (pose, velocidades, torques, duração, dt; RK4; animação 3D; registrar no projeto).
