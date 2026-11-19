# Critérios de aceitação — estado real (v1.0.0-rc1)

Regra do projeto: um módulo só conta como pronto quando a interface funciona, os cálculos existem, os resultados aparecem, os testes passam e os erros são tratados. Esta lista foi preenchida com o que foi **realmente verificado** (127 testes automatizados; renderização 3D conferida em display virtual Linux). "Não verificado" significa que não foi testado no ambiente em que o item importa.

## Por módulo
| Módulo | Estado | Observações |
|---|---|---|
| Human Model | Pronto (parâmetros demonstrativos) | Membro inferior (pelve, fêmur, tíbia, fíbula, pé), limites configuráveis, FK 4x4, CM; modelo salvo no projeto. |
| Motion Engine | Parcial | Cinemática direta/inversa, Jacobiano, trajetórias de mínimo jerk. Sem importação de captura de movimento. |
| Force Engine | Parcial | Dinâmica inversa/direta de Lagrange planar (2 e N segmentos), RK4, energia, potência, trabalho. Sem 3D completo e sem músculos. |
| Bioinspired Lab | Pronto (parâmetros demonstrativos) | BIO-001 e BIO-002: humano × animal; a 3ª junta do animal é o jarrete. Sem fontes científicas para os parâmetros. |
| Exoskeleton Lab | Pronto (modelo simplificado) | EXO-001: atuador com curva torque-velocidade, modos proporcional/gravidade, saturação, energia. Sem controle em malha fechada, atrito ou folgas. |
| 3D Lab | Pronto, com ressalva | Viewport VTK/PyVista, sliders de pose, CM, importação de STL (malha só visual). Seleção de segmentos por clique do mouse **não verificada**. |
| AI Analysis | Somente arquitetura (como especificado) | Contratos, registro de provedores, rótulo obrigatório "gerado por IA", procedência e limitações. Nenhum provedor incluído: sem provedor, nada é gerado. |
| Research Center | Pronto | Experimentos reproduzíveis salvos no projeto, histórico SQLite, relatórios .md/CSV/PNG/PDF (PDF para BIO-001, BIO-002 e EXO-001). |
| Celular | Pronto (testado com jsdom) | Mesmos cálculos do desktop, conferidos numericamente; 3D por software, STL somente visualização. Gestos de toque não testados em aparelho real. |

## Princípios obrigatórios
- Sem recursos falsos: itens não implementados ficam desabilitados e marcados "planejado". ✔
- Sem dados aleatórios como ciência; resultados determinísticos e reexecutáveis. ✔
- Unidades explícitas (SI) e hipóteses/limitações nos relatórios. ✔
- Parâmetros não verificados marcados como DEMONSTRATIVO. ✔ (todos os parâmetros padrão estão nessa categoria)
- Sem alegar precisão clínica; não é dispositivo médico. ✔
- Erros tratados com mensagem ao usuário (arquivos inválidos, limites articulares, banco corrompido etc.). ✔

## O que impede declarar a 1.0.0 final
1. **Windows não verificado:** o `.exe` (PyInstaller) só foi gerado e iniciado em Linux. Falta rodar `build_windows.bat` e abrir o app no Windows 11.
2. **Parâmetros sem fonte científica:** nenhum parâmetro tem referência; sem isso os resultados ilustram o método, não anatomia real.
3. **MuJoCo / OpenSim:** não implementados (itens de menu desabilitados).
4. **Seleção por clique no 3D** e **gestos de toque no celular:** não verificados em ambiente real.

Quando 1 a 4 forem resolvidos (ou aceitos conscientemente como fora de escopo da 1.0), altere `application/version.py` para `1.0.0`.
