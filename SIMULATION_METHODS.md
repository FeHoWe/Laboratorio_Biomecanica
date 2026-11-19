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
## BIO-001
Trajetória de mínimo jerk por junta; torque = dinâmica inversa − Jᵀ F; potência = τ·q̇; trabalho por trapézios; torque normalizado τ/(M·g·L) para comparar escalas diferentes. Reprodutível: parâmetros + resultados determinísticos. Teste: trabalho dos torques = variação de energia mecânica.
## SIM-001
M(q)q̈ + C + G = 0 integrado por RK4 (passo fixo). Validação: deriva relativa da energia mecânica; teste de equilíbrio pendurado e período de pêndulo.
## Modelo de membro inferior
Plano sagital exibido em 3D (x anterior, y cima, z lateral). Frames 4x4: T_seg = T_pai · T(comprimento) · Rz(ângulo). Quadril: Rz(+h); joelho: Rz(−k); tornozelo: Rz(+d). Limites articulares são entradas configuráveis, não valores clínicos. CM do membro = média ponderada de fêmur, tíbia e pé.
## Cadeia de N segmentos (BIO-002)
M = Σ(m_i Jv_iᵀ Jv_i + I_i Jw_iᵀ Jw_i); G = ∂U/∂q (Σ m_i g Jv_i[y]); C q̇ = Ṁ q̇ − ∂T/∂q com ∂M/∂q por diferenças centrais (h = 1e-6). Para N = 2 coincide com o modelo de 2 segmentos (teste). Ângulos relativos: q1 absoluto, qk relativo ao segmento anterior.
## Verificação
Testes: transformações, conversão de unidades, FK/IK (ida e volta), Jacobiano vs diferenças finitas, torque analítico de braço horizontal, ∂U/∂q, consistência dinâmica direta/inversa, conservação de energia, período de pêndulo físico.
