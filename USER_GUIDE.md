# Guia do usuário (Fase 1)
Arquivo > Novo projeto: informe nome, descrição e local (cria uma pasta). Editar > Renomear (F2) ou painel Propriedades > Aplicar. Salvar: Ctrl+S. Ferramentas > Diagnóstico mostra bibliotecas presentes/ausentes.

## EXO-001 — Exoesqueleto
Pesquisa → Novo experimento EXO-001. Escolha junta, modo (proportional = fração do torque requerido; gravity = fração do torque de gravidade), ganho, massas adicionadas por segmento e parâmetros do atuador (τ de bloqueio, ω sem carga, η). O gráfico mostra o torque da junta sem exo, com exo sem assistência e humano com assistência, e o torque do atuador contra seu limite τ-ω. Se o atuador saturar, há aviso. Hipóteses: exo rígido e alinhado, sem atrito/folgas/músculos; todos os valores são DEMONSTRATIVOS.

## Importar malha STL
Modelo → Importar malha STL…, escolha o arquivo e a unidade das coordenadas (mm, cm, m ou in). O app valida o arquivo, copia para a pasta `models/` do projeto e mostra triângulos, caixa limite, área e volume (volume só para malhas fechadas). A malha é apenas visual: não entra em nenhum cálculo. Clique no item da malha na árvore para exibi-la de novo. No celular, a aba 3D tem a mesma leitura, só para visualização (não é salva).

## Análise por IA
A arquitetura existe, mas nenhum provedor está incluído; por isso Análise → "Análise assistida por IA" fica desabilitado. Quando houver um provedor, toda saída virá rotulada como "Gerado por IA — não validado", com provedor, modelo e limitações, e nunca entra nos cálculos.
