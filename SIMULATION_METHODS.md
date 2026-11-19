# Métodos de simulação (v0.2.0)
Unidades SI (m, kg, s, rad, N, N.m). Plano vertical x-y, gravidade -y (g = 9,80665 m/s²).

## Cadeia planar de 2 segmentos (`simulation/kinematics/planar.py`)
- q1 = ângulo absoluto do segmento 1; q2 = ângulo relativo do segmento 2.
- Direta: p_joint = l1[cos q1, sin q1]; p_tip = p_joint + l2[cos(q1+q2), sin(q1+q2)].
- Inversa analítica: cos q2 = (x²+y²−l1²−l2²)/(2 l1 l2); q1 = atan2(y,x) − atan2(l2 sin q2, l1 + l2 cos q2). Alvo fora do alcance -> erro explícito.
- Jacobiano 2x2 (m/rad). Trajetória: quíntico de mínimo jerk (vel. e acel. nulas nas bordas).
## Estática (`biomechanics/force_engine/planar_dynamics.py`)
- Momento 2D: r × F = rx·Fy − ry·Fx. CM do sistema: média ponderada pelas massas.
- Torque de gravidade = ∂U/∂q. Torque estático com força na ponta: τ = τ_g − Jᵀ F.
## Dinâmica
- M(q)q̈ + C(q,q̇) + G(q) = τ (Lagrange; segmentos rígidos com massa, CM e inércia). Integração RK4 passo fixo.
## Hipóteses e limitações
Sem atrito, sem músculos, juntas ideais, 2D. Parâmetros de segmentos são entradas do usuário; nenhum dado antropométrico verificado está embutido. Não há validação clínica.
## Verificação
Testes: transformações, conversão de unidades, FK/IK (ida e volta), Jacobiano vs diferenças finitas, torque analítico de braço horizontal, ∂U/∂q, consistência dinâmica direta/inversa, conservação de energia, período de pêndulo físico.
