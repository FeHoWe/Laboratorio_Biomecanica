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
## Gerar o executável (.exe)
Com o venv ativo: `build_windows.bat` -> `dist\NEXUS_BIOMECHANICS\NEXUS_BIOMECHANICS.exe` (pasta portátil).
Verificado em Linux (build e inicialização); o build no Windows ainda não foi testado por mim — se falhar, envie o log.
