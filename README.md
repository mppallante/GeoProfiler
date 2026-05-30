# GeoProfiler

GeoProfiler é uma ferramenta em Python para apoio ao Perfilamento Geográfico Criminal, construída com Streamlit, Pandas, GeoPandas, Folium e Plotly.

A versão 2 evolui o projeto de um dashboard geográfico para um ambiente analítico investigativo com cadastro de ocorrências, mapa tático, estatísticas, análise espacial, zonas de perfilamento e relatório de inteligência geográfica.

## Objetivo

Fornecer uma base modular para análise exploratória de ocorrências criminais georreferenciadas, apoiando triagem territorial, identificação de concentração espacial e formulação de hipóteses investigativas.

Os resultados são hipóteses investigativas e não conclusões periciais.

## Tecnologias

- Python
- Streamlit
- Pandas
- GeoPandas
- Folium
- Streamlit Folium
- Plotly
- PyInstaller

## Estrutura

```text
GeoProfiler/
|-- app.py
|-- launcher.py
|-- build_exe.bat
|-- requirements.txt
|-- README.md
|-- LICENSE
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

## Como executar

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

2. Instale as dependências:

```bash
pip install -r requirements.txt
```

3. Execute a aplicação:

```bash
streamlit run app.py
```

Também é possível executar pelo launcher usado no empacotamento:

```bash
python launcher.py
```

### Como executável

Depois de gerar o build, execute:

```powershell
.\dist\GeoProfiler.exe
```

O executável inicia o Streamlit automaticamente, escolhe uma porta local disponível e abre o navegador. A base persistente fica em `dist\data\crimes.csv`, ao lado do executável.

## Como gerar o executável

No Windows, dê duplo clique em:

```text
build_exe.bat
```

O script cria o ambiente virtual `.venv` caso ele ainda não exista, instala as dependências de `requirements.txt` e usa PyInstaller para gerar:

```text
dist\GeoProfiler.exe
```

Para gerar um novo build, execute novamente `build_exe.bat`.

## Formato dos dados

O arquivo CSV é criado automaticamente em `data/crimes.csv` quando ainda não existir. O formato deve permanecer compatível com as colunas abaixo:

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

## Funcionalidades

- Cadastro manual de ocorrências
- Persistência em CSV
- Mapa interativo com camadas claro/escuro
- Clusterização de ocorrências
- Heatmap contínuo de densidade espacial
- Centro de Gravidade Criminal (CGC)
- Zona de conforto
- Base de operações estimada
- Zona de segurança
- Classificação geográfica Marauder/Commuter
- Relatório de inteligência geográfica
- Estatísticas por tipo de crime, bairro, dia, horário e linha do tempo
- Tema claro e tema escuro
- Build Windows com PyInstaller

## Licença

Projeto proprietário. Todos os direitos reservados.
