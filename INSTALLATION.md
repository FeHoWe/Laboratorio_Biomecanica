# Instalação (Windows 11)
1. Instale Python 3.11–3.13 (python.org), marcando "Add to PATH".
2. Na pasta do projeto:
```
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python main.py
python -m pytest
```
Logs e projetos recentes: `%USERPROFILE%\.nexus_biomechanics\` (altere com a variável NEXUS_HOME).
Executável (.exe): PyInstaller ainda não configurado (pendente).
