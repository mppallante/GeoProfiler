# GeoProfiler

GeoProfiler é uma ferramenta em Python para apoio ao Perfilamento Geográfico Criminal, construída com Streamlit, Pandas, Folium e Plotly.

É um ambiente analítico investigativo multi-caso: cada investigação/série é um **Caso** independente, com seu próprio cadastro de ocorrências, mapa tático, estatísticas e relatório de inteligência geográfica em linguagem natural, podendo ser arquivado ou vinculado a outros casos relacionados.

## Objetivo

Fornecer uma base modular para análise exploratória de ocorrências criminais georreferenciadas, apoiando triagem territorial, identificação de concentração espacial e formulação de hipóteses investigativas, para múltiplos casos independentes.

Os resultados são hipóteses investigativas e não conclusões periciais.

## Tecnologias

- Python
- Streamlit (navegação multi-página via `st.navigation`)
- SQLite (`sqlite3` da biblioteca padrão, sem ORM)
- Pandas
- Folium
- Streamlit Folium
- Plotly
- Requests (geocodificação via Nominatim/OpenStreetMap)
- Openpyxl (importação de XLSX)
- fpdf2 (geração de relatório PDF)
- PyInstaller

## Estrutura

```text
GeoProfiler/
|-- app.py
|-- launcher.py
|-- build_exe.bat
|-- requirements.txt
|-- requirements-dev.txt
|-- pytest.ini
|-- README.md
|-- LICENSE
|-- .gitignore
|-- .streamlit/
|   `-- config.toml
|-- assets/
|   `-- logo.png
|-- data/
|   |-- crimes.csv          (seed/exemplo, migrado uma única vez)
|   `-- geoprofiler.db      (gerado em tempo de execução, não versionado)
|-- scripts/
|   `-- migrate_to_sqlite.py
|-- src/
|   |-- data_manager.py     (camada de acesso a dados: casos e crimes)
|   |-- db.py                (conexão e schema SQLite)
|   |-- map_visualization.py
|   |-- geo_analysis.py
|   |-- statistics.py
|   |-- crime_import.py     (importação de CSV/XLSX e mapeamento de colunas)
|   |-- geocoding.py        (geocodificação de endereço via Nominatim)
|   |-- report_export.py    (exportação de mapa HTML e relatório PDF)
|   |-- utils.py
|   `-- pages/
|       |-- _shared.py       (chrome e helpers compartilhados)
|       |-- casos.py         (escolha e cadastro de casos e ocorrências)
|       |-- mapa.py
|       |-- estatisticas.py
|       `-- analise_automatizada.py
`-- tests/
    |-- conftest.py
    |-- test_geo_analysis.py
    |-- test_data_manager_db.py
    |-- test_crime_import.py
    |-- test_geocoding.py
    |-- test_report_export.py
    |-- test_shared.py
    `-- fixtures/
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

O executável inicia o Streamlit automaticamente, escolhe uma porta local disponível e abre o navegador. A base persistente fica em `dist\data\geoprofiler.db`, ao lado do executável. Na primeira execução, o `data/crimes.csv` de exemplo é migrado automaticamente para um caso chamado "Caso Exemplo".

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

## Casos

Cada investigação/série de crimes é um **Caso** independente (`nome`, `descrição`, `responsável`, `data de abertura`, `notas`, `barreiras geográficas`), com seu próprio conjunto de ocorrências — sem compartilhamento de dados entre casos. Um caso pode ser **arquivado** (some da lista padrão, continua utilizável enquanto aberto, reversível a qualquer momento) e pode ser **vinculado** a outros casos suspeitos de estarem relacionados (ex.: mesmo autor/série) — o vínculo é simétrico e aparece dos dois lados. Os dados ficam em `data/geoprofiler.db` (SQLite), criado automaticamente na primeira execução. Cada ocorrência pertence a exatamente um caso e usa as colunas abaixo:

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

- Gestão de múltiplos casos (séries/investigações) independentes
- Arquivamento de casos (ocultos da lista padrão, reversível, sem perda de dados)
- Vínculo entre casos relacionados (ex.: suspeita de mesmo autor/série), simétrico e navegável
- Filtro de período compartilhado entre Mapa, Estatísticas e Análise Automatizada
- Cadastro manual de ocorrências por caso
- Persistência em SQLite local, sem servidor
- Mapa interativo com camadas claro/escuro, dividido em mapa + lista de ocorrências do período filtrado
- Pinos do mapa e itens da lista coloridos por tipo de crime, com a mesma paleta usada nos gráficos
- Clusterização de ocorrências
- Heatmap contínuo de densidade espacial (vetorizado com NumPy)
- Perfil de probabilidade de Rossmo (CGT — Criminal Geographic Targeting), com camada própria no mapa
- Centro de Gravidade Criminal (CGC)
- Zona de conforto
- Base de operações estimada
- Zona de segurança
- Círculo de Canter (Circle Hypothesis) com raio de buffer ajustável pelo usuário, incluindo diagrama esquemático com CGC, base estimada e os dois crimes que definem o círculo
- Classificação geográfica Marauder/Commuter baseada no teste geométrico do Círculo de Canter
- Classificação de ocorrências dentro/fora da zona de buffer
- Relatório de inteligência geográfica em linguagem natural (página de Análise Automatizada), incluindo as premissas metodológicas do modelo de Rossmo
- Importação em massa de ocorrências via CSV/XLSX, com mapeamento de colunas assistido
- Geocodificação de endereço para latitude/longitude (Nominatim/OpenStreetMap) no cadastro manual
- Exportação do mapa interativo (HTML) e de um relatório do caso (PDF) com resumo, zonas, relatório narrativo e lista de ocorrências
- Comparação de métodos de decaimento (Rossmo, exponencial negativa, linear, normal/gaussiana) — mostra o quanto o pico de probabilidade estimado muda conforme a premissa metodológica escolhida, com barra de distância inline na tabela
- Classificação de bairros em Zona de Conforto/Transição, com base na distância média ao CGC
- Anotação de barreiras geográficas (rios, rodovias) por caso, editável e referenciada no relatório narrativo
- Estatísticas por tipo de crime (gráfico de rosca), bairro, dia, horário e linha do tempo
- Sistema de design próprio: tokens de cor/tipografia/raio, ícones consistentes, badges de status coloridos, cards com acabamento em vidro (tema claro) ou glow (tema escuro)
- Tema claro e tema escuro
- Build Windows com PyInstaller

## Testes

```bash
pip install -r requirements-dev.txt
pytest
```

## Licença

Projeto proprietário. Todos os direitos reservados.
