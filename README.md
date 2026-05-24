# GeoProfiler

GeoProfiler e uma aplicacao inicial em Python para perfilamento geografico criminal, construida com Streamlit, Pandas, GeoPandas e Folium.

Esta versao contem uma estrutura profissional inicial com cadastro manual de crimes, persistencia em CSV, metricas basicas e visualizacao das ocorrencias em mapa.

## Objetivo

Organizar uma base modular para evoluir uma aplicacao de analise geografica criminal, mantendo separacao clara entre interface, carregamento de dados, visualizacao em mapa, estatisticas e utilidades.

## Tecnologias

- Python
- Streamlit
- Pandas
- GeoPandas
- Folium
- Streamlit Folium

## Estrutura

```text
GeoProfiler/
|-- app.py
|-- launcher.py
|-- build_exe.bat
|-- requirements.txt
|-- README.md
|-- .gitignore
|-- .streamlit/
|   `-- config.toml
|-- assets/
|   `-- logo.png
|-- data/
|   `-- crimes.csv
`-- src/
    |-- data_manager.py
    |-- map_visualization.py
    |-- geo_analysis.py
    |-- statistics.py
    `-- utils.py
```

## Como Executar

### Modo desenvolvimento

1. Crie e ative um ambiente virtual:

```bash
python -m venv .venv
source .venv/bin/activate
```

No Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

2. Instale as dependencias:

```bash
pip install -r requirements.txt
```

3. Execute a aplicacao:

```bash
streamlit run app.py
```

Tambem e possivel executar pelo launcher usado no empacotamento:

```bash
python launcher.py
```

### Como executavel

Depois de gerar o build, execute:

```powershell
.\dist\GeoProfiler.exe
```

O executavel inicia o Streamlit automaticamente, escolhe uma porta local disponivel e abre o navegador. A base de dados persistente fica em `dist\data\crimes.csv`, ao lado do executavel.

## Como gerar o executavel

No Windows, de duplo clique em:

```text
build_exe.bat
```

O script cria o ambiente virtual `.venv` caso ele ainda nao exista, instala as dependencias de `requirements.txt` e usa PyInstaller para gerar:

```text
dist\GeoProfiler.exe
```

Para gerar um novo build, execute novamente `build_exe.bat`. O processo usa `--clean` e `--noconfirm`, recriando os artefatos em `build/` e `dist/`.

Arquivos incluidos no executavel:

- `launcher.py`
- `app.py`
- `src/`
- `data/`
- `assets/`
- `.streamlit/`
- `requirements.txt`

## Formato dos Dados

O arquivo CSV e criado automaticamente em `data/crimes.csv` quando ainda nao existir. A base utiliza as seguintes colunas:

- `id`
- `tipo_crime`
- `data`
- `hora`
- `latitude`
- `longitude`
- `cidade`
- `bairro`
- `modus_operandi`
- `observacoes`

Um arquivo de exemplo esta disponivel em `data/crimes.csv`.

## Entrada de Dados

A tela principal permite cadastrar ocorrencias manualmente. O sistema gera o ID automaticamente, valida latitude e longitude, salva os registros na base local e atualiza a tabela de crimes cadastrados.

## Analise Geografica Criminal

O modulo `src/geo_analysis.py` calcula indicadores exploratorios iniciais:

- Centro medio geografico
- Distancia de cada crime ate o centro
- Distancia media e desvio padrao espacial
- Crime mais proximo e mais distante do centro
- Grade geografica com contagem por celula
- Ranking das celulas mais criticas
- Interpretacao automatica com hipoteses e limitacoes

## Modulo Estatistico

O modulo `src/statistics.py` gera as tabelas estatisticas usadas pelo dashboard:

- Frequencia por tipo de crime
- Frequencia por bairro
- Frequencia por dia da semana
- Frequencia por horario
- Linha do tempo dos crimes
- Dados estruturados para graficos interativos no Streamlit

## Interface

A aplicacao usa tema escuro profissional, sidebar com logotipo, cards de indicadores, abas operacionais e graficos interativos com estilo visual consistente para uso analitico e investigativo.

## Status do Projeto

Estrutura inicial criada. A logica avancada de perfilamento geografico ainda nao foi implementada.

## Roadmap Inicial

- Validacao robusta dos dados carregados
- Filtros por periodo e tipo de crime
- Camadas avancadas de visualizacao geografica
- Analises estatisticas e espaciais
- Exportacao de relatorios

## Licenca

Defina a licenca do projeto antes da publicacao.
