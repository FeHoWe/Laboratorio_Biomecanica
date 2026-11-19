# Motor biomecânico espacial 3D (V1.1.0)

Documento técnico do motor espacial: equações, convenções, algoritmos, hipóteses, limitações, testes e fontes.
**Todos os parâmetros padrão são DEMONSTRATIVOS** (hipotéticos, sem fonte científica verificada). Não é dispositivo médico.

## 1. Convenções
- Unidades SI: m, kg, s, rad (graus apenas nas entradas/saídas de interface), N, N·m, J, W. Inércia em kg·m².
- Mundo: x anterior, y para cima, z lateral direita; gravidade `g = (0, −9,80665, 0)` m/s² (configurável). Origem no solo sob o quadril.
- Referencial (frame): transformação homogênea 4×4 `T_mundo←corpo`. Rotações são matrizes SO(3) (direita, ativas).
- Quaternions `[w, x, y, z]`, Hamilton, forma canônica `w ≥ 0` (q e −q são a mesma rotação).
- Junta = origem fixa no corpo pai (translação e rotação) seguida de DOFs **em sequência**; o eixo de cada DOF é expresso no
  referencial já girado pelos DOFs anteriores (convenção intrínseca; MuJoCo usa a mesma, verificado em teste).
  `T_junta(q) = T_origem · Π_k M_k(q_k)`, `M_k` = rotação de Rodrigues (rotativo) ou translação (prismático).
- Esférica = 3 rotações sequenciais Z-X-Y (Tait-Bryan intrínseca, `R = Rz(a)Rx(b)Ry(c)`); singularidade de gimbal em `|cos b| → 0`
  (`gimbal_margin`, aviso no BIO-003). Universal = 2 rotações; fixa = 0 DOF.
- Sinais do membro inferior (compatível com o modelo sagital antigo): flexão do quadril +z, joelho em −z, dorsiflexão +z.
  Ordem de `q`: quadril flexão, abdução (eixo x), rotação (eixo y), joelho flexão, tornozelo dorsiflexão, inversão (eixo x).
  Com abdução = rotação = inversão = 0 as posições coincidem com `LowerLimbModel` (teste de 30 poses, tolerância 1e-12).

## 2. Cinemática
- Direta: produto das transformações ao longo da árvore. Jacobiano geométrico no ponto P de um corpo:
  rotativo `Jv_k = z_k × (P − o_k)`, `Jw_k = z_k`; prismático `Jv_k = z_k`; DOFs que não movem o corpo → coluna nula.
- Velocidade `v = Jv q̇`, `ω = Jw q̇`; aceleração `a = Jv q̈ + J̇v q̇`, `α = Jw q̈ + J̇w q̇` (J̇q̇ por diferença central ao longo de q̇).
- IK numérica (`simulation/spatial_kinematics/inverse.py`): mínimos quadrados amortecidos `Δq = Jᵀ(JJᵀ + λ²I)⁻¹ e`; erro de
  posição + vetor de rotação; λ cresce quando o menor valor singular cai abaixo de 5 % do maior (singularidade); passo máximo 0,3 rad;
  limites articulares por projeção; alcance por desigualdade triangular (alvo fora → mensagem sem iterar); mensagens distintas para
  "limite de iterações" e "preso em limite/singularidade". Convergência: `‖e_pos‖ < tol_pos` e `‖e_rot‖ < tol_rot`.
- Trajetórias: mínimo jerk (quíntico) no espaço articular e em linha reta no espaço cartesiano (+ IK com partida a quente).

## 3. Dinâmica
`M(q) q̈ + C(q,q̇) q̇ + G(q) = τ + Σ J_pᵀ F_p`
- `M = Σ_b [ m_b Jvᵀ Jv + Jwᵀ (R I_cm Rᵀ) Jw ]` (Jacobianos no CM de cada corpo; `I_cm` em torno do CM).
- `G = ∂V/∂q = −Σ m_b gᵀ Jv_b`, `V = −Σ m_b g·r_cm,b`.
- `C q̇` por Newton-Euler: `Σ_b [ m Jvᵀ(J̇v q̇) + Jwᵀ(I_w J̇w q̇ + ω × I_w ω) ]`; o método de Christoffel
  (`Γ_ijk = ½(∂M_ij/∂q_k + ∂M_ik/∂q_j − ∂M_jk/∂q_i)`, `∂M/∂q` por diferenças centrais, h = 1e-6) é mantido como verificação cruzada.
- Cargas externas: força (N) em ponto local de um corpo e/ou torque puro (N·m), vetores no mundo.
- Inversa `τ = M q̈ + C q̇ + G − τ_ext`; direta `q̈ = M⁻¹(τ + τ_ext − C q̇ − G)`.
- Energia: `T = ½ q̇ᵀ M q̇`, `V` acima, `E = T + V`; potência articular `τ_k q̇_k`; trabalho por trapézios.
  O corpo base (pelve fixa) não entra em M nem em V.

## 4. Integração
- RK4 de passo fixo (padrão) e DOP853 adaptativo (SciPy, `rtol=1e-9`, `atol=1e-11`) amostrado em passos fixos.
- Cancelamento cooperativo (`SimulationCancelled`), progresso 0–100, detecção de divergência (valores não finitos ou `|q̇| > 1e4 rad/s`).
- Registra t, q, q̇, q̈, τ, T, V, E e potência. Limites articulares **não são impostos** na dinâmica: violações são contadas e avisadas.
- Execução na interface em `QThread` (`TaskThread`) com barra de progresso e botão cancelar.

## 5. Visualização 3D (VTK/PyVista)
Cada corpo é um ator criado uma vez com geometria local; a cada quadro só `actor.user_matrix = T_mundo←corpo` é atualizado
(nenhum ator é recriado — testado). Mostra segmentos, juntas, eixos locais, CM por corpo e do conjunto, vetores (função
`set_vectors`), trajetória, seleção e 4 câmeras (isométrica, lateral, frontal, superior). Reprodução: play/pause/reiniciar,
velocidades 0,1×–4×, posição por slider; só escolhe quadros de uma trajetória já calculada.

## 6. BIO-003 — Spatial lower limb dynamics
Pelve fixa → fêmur (quadril 3 DOF) → tíbia (joelho 1 DOF) → pé (tornozelo 2 DOFs) + fíbula fixa à tíbia. Entradas: segmentos
(comprimento, massa, CM), limites, pose e velocidades iniciais, gravidade, torque por DOF `τ_k(t) = τ_const + τ_amp·sen(2πft)`,
duração, passo e integrador. Saídas: ângulos, velocidades, acelerações, torques, potências, T/V/E, ponta do pé e CM; CSV, relatório
.md, PNG, PDF, registro no projeto (histórico SQLite) e reexecução determinística.

## 7. MuJoCo (opcional)
`simulation/physics_engines/mujoco_adapter.py` gera o MJCF da cadeia e compara M, viés (C q̇ + G), dinâmica inversa, posições,
CMs, energia e trajetória com o motor interno. **O motor interno continua sendo a referência**; sem MuJoCo instalado nada é simulado
(`MujocoUnavailable`). Versão testada: 4.0.1. A comparação cobre dinâmica livre (sem torques) e sem limites articulares.
OpenSim: não implementado.

## 8. Hipóteses e limitações
- Corpos rígidos, juntas ideais sem atrito/folga, sem músculos, ligamentos, contato com o solo ou controle.
- Quadril 3 DOF, joelho 1 DOF, tornozelo 2 DOFs são **simplificações mecânicas**, não anatomia articular.
- Inércias de cilindros homogêneos; parâmetros e limites de abdução/rotação/inversão são hipotéticos.
- `∂M/∂q` e `J̇q̇` são numéricos (O(h²)); para passos grandes ou movimentos muito rápidos a energia deriva (reportada).
- Singularidade de gimbal do quadril: reportada, não tratada com quaternions na dinâmica (a dinâmica usa ângulos).
- Sem validação experimental. Não há fontes científicas para os parâmetros.

## 9. Testes (209 no total; os do motor espacial)
`test_spatial_core` (19): Rodrigues, SO(3), `matrix_log` (inclui ≈π e ângulos ~1e-6), Euler/gimbal, quaternions, frames, inércia
(analítica e eixos paralelos), juntas. `test_spatial_kinematics` (14): FK vs módulo planar e vs modelo sagital (30 poses), Jacobiano
vs diferenças finitas (linear e angular), velocidade/aceleração vs derivadas numéricas, IK (alvos alcançáveis, fora de alcance,
singularidade, limites), trajetórias. `test_spatial_dynamics` (19): pêndulo físico (M, G, período de pequenas oscilações),
equilíbrio, pêndulo duplo vs fórmulas analíticas e vs `PlanarChain`, M simétrica/definida positiva, `Ṁ − 2C` antissimétrica,
G = ∇V, Newton-Euler = Christoffel, direta×inversa, forças externas, queda livre, conservação de energia (RK4 e adaptativo),
ordem 4 do RK4, trabalho = ΔE, determinismo, cancelamento/progresso/divergência. `test_spatial_scene` (4), `test_bio003` (16),
`test_mujoco_adapter` (6), `test_mobile_compat` (porta JS = motor Python em M, G, C q̇, q̈, energias e trajetórias).

## 10. Fontes
Métodos clássicos de robótica/dinâmica de sistemas multicorpo (Jacobiano geométrico, Lagrange/Newton-Euler, Christoffel, mínimos
quadrados amortecidos, RK4, DOP853) — não foram consultadas fontes bibliográficas específicas nesta implementação; nenhum dado
antropométrico foi extraído de literatura. Referência de comparação numérica: MuJoCo 4.0.1.
