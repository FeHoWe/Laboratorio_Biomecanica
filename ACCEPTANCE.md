# Critérios de aceitação — estado real (v1.1.0)

Regra do projeto: um módulo só conta como pronto quando a interface funciona, os cálculos existem, os resultados aparecem, os testes passam e os erros são tratados. Esta lista foi preenchida com o que foi **realmente verificado** (209 testes automatizados; renderização 3D conferida em display virtual Linux). "Não verificado" significa que não foi testado no ambiente em que o item importa.

## Por módulo
| Módulo | Estado | Observações |
|---|---|---|
| Human Model | Pronto (parâmetros demonstrativos) | Membro inferior (pelve, fêmur, tíbia, fíbula, pé), limites configuráveis, FK 4x4, CM; modelo salvo no projeto. |
| Motion Engine | Parcial | Cinemática direta/inversa, Jacobiano, trajetórias de mínimo jerk. Sem importação de captura de movimento. |
| Force Engine | Pronto para o escopo mecânico (sem músculos) | Planar (2 e N segmentos) e **espacial 3D**: M, C, G, energias, direta/inversa, forças externas, RK4/DOP853 (ver SPATIAL_ENGINE.md). Sem músculos, contato ou atrito. |
| Spatial Engine (V1.1) | Pronto (parâmetros demonstrativos) | Rotações, quaternions, frames, juntas, cadeia, Jacobiano, IK, trajetórias; verificado por testes numéricos (analíticos, diferenças finitas, energia, MuJoCo). |
| BIO-003 | Pronto (modelo simplificado) | Quadril 3 DOF, joelho 1, tornozelo 2; thread, gráficos, 3D animado, CSV/.md/PNG/PDF, histórico, reexecução determinística. Limites articulares não impostos (avisados). |
| MuJoCo | Pronto como comparação opcional | Adaptador testado com MuJoCo 4.0.1 (dinâmica livre). OpenSim: não implementado. |
| Bioinspired Lab | Pronto (parâmetros demonstrativos) | BIO-001 e BIO-002: humano × animal; a 3ª junta do animal é o jarrete. Sem fontes científicas para os parâmetros. |
| Exoskeleton Lab | Pronto (modelo simplificado) | EXO-001: atuador com curva torque-velocidade, modos proporcional/gravidade, saturação, energia. Sem controle em malha fechada, atrito ou folgas. |
| 3D Lab | Pronto, com ressalva | Viewport VTK/PyVista, sliders de pose, CM, importação de STL (malha só visual). Seleção por clique do mouse **não verificada**; a cena espacial animada foi renderizada e conferida em display virtual Linux. |
| AI Analysis | Somente arquitetura (como especificado) | Contratos, registro de provedores, rótulo obrigatório "gerado por IA", procedência e limitações. Nenhum provedor incluído: sem provedor, nada é gerado. |
| Research Center | Pronto | Experimentos reproduzíveis salvos no projeto, histórico SQLite, relatórios .md/CSV/PNG/PDF (PDF para BIO-001, BIO-002, EXO-001 e BIO-003). |
| Celular | Pronto (testado com jsdom) | Mesmos cálculos do desktop (incl. BIO-003), conferidos numericamente; 3D por software; STL somente visualização. Teste de visibilidade de todas as abas (corrigiu abas 3D/Histórico/EXO que não apareciam). Gestos de toque não testados em aparelho real. |

## Princípios obrigatórios
- Sem recursos falsos: itens não implementados ficam desabilitados e marcados "planejado". ✔
- Sem dados aleatórios como ciência; resultados determinísticos e reexecutáveis. ✔
- Unidades explícitas (SI) e hipóteses/limitações nos relatórios. ✔
- Parâmetros não verificados marcados como DEMONSTRATIVO. ✔ (todos os parâmetros padrão estão nessa categoria)
- Sem alegar precisão clínica; não é dispositivo médico. ✔
- Erros tratados com mensagem ao usuário (arquivos inválidos, limites articulares, banco corrompido etc.). ✔

## O que impede declarar a 1.0.0/1.1.0 finais
1. **Windows não verificado:** o `.exe` (PyInstaller) só foi gerado e iniciado em Linux. Falta rodar `build_windows.bat` e abrir o app no Windows 11.
2. **Parâmetros sem fonte científica:** nenhum parâmetro tem referência; sem isso os resultados ilustram o método, não anatomia real.
3. **OpenSim:** não implementado. MuJoCo é apenas comparação opcional.
4. **Seleção por clique no 3D** e **gestos de toque no celular:** não verificados em ambiente real.
5. **SciPy no pacote do Windows:** o PyInstaller com SciPy/VTK não foi testado (o integrador RK4 não precisa de SciPy; só o adaptativo).
6. **Dinâmica espacial sem validação experimental**: os testes provam consistência matemática e concordância com MuJoCo, não correspondência com movimento humano real.

Quando 1 a 4 forem resolvidos (ou aceitos conscientemente como fora de escopo da 1.0), altere `application/version.py` para `1.1.0`.
