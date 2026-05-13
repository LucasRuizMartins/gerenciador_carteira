# 📊 Sistema de Carteiras Diárias — Carmel Capital

Sistema de ETL (Extract-Transform-Load) para processamento automático de carteiras diárias de fundos FIDC, integrando dados de múltiplas administradoras e persistindo os resultados em relatórios Excel gerenciais.

---

## 📋 Índice

- [Visão Geral](#visão-geral)
- [Arquitetura](#arquitetura)
- [Estrutura de Arquivos](#estrutura-de-arquivos)
- [Fluxo de Dados](#fluxo-de-dados)
- [Fundos Suportados](#fundos-suportados)
- [Administradoras](#administradoras)
- [Configuração](#configuração)
- [Como Executar](#como-executar)
- [Testes](#testes)
- [Camada `src/` — Nova Arquitetura](#camada-src--nova-arquitetura)
- [Migração Futura para Banco de Dados](#migração-futura-para-banco-de-dados)
- [Débitos Técnicos](#débitos-técnicos)

---

## Visão Geral

O sistema lê os arquivos de **carteira diária** de cada fundo (planilhas Excel fornecidas pelas administradoras), extrai as posições financeiras (direitos creditórios, cotas, contas a pagar/receber, taxas, patrimônio), e preenche automaticamente os **relatórios gerenciais** da Carmel Capital em Excel (abas `CD` e `MEC`).

```
Planilha da Administradora (.xlsx / .xlsb)
        │
        ▼
  Classe de Carteira (ETL)
        │
        ▼
  Builder de Relatório
        │
        ▼
  ExcelWriter (xlwings)
        │
        ▼
  Relatório Gerencial Carmel Capital (.xlsb)
```

---

## Arquitetura

O sistema segue os princípios **Clean Code**, **DRY** e **SOLID**:

| Princípio | Aplicação |
|-----------|-----------|
| **SRP** | Cada classe tem uma responsabilidade: `CarteiraBase` lê dados, `ReportBuilder` monta relatórios, `ExcelWriter` persiste |
| **OCP** | Novo fundo = nova entrada no `REGISTRO` + novo `Builder`. Nenhum código existente é alterado |
| **DIP** | `ExcelWriter` é injetado no executor — permite substituição por `DatabaseWriter` sem alterar builders |
| **DRY** | Funções puras de conversão centralizadas em `src/core/converters.py` |

### Hierarquia de Classes de Carteira

```
CarteiraBase (ABC)
├── Carteira               — Administradora genérica (Cobuccio FIDC)
├── CarteiraBRL            — Administradora BRL Trust
│   ├── CarteiraGenial     — Genial (herda lógica BRL via _MixinCdAtual)
│   └── CarteiraQI         — QI Tech (herda lógica BRL via _MixinCdAtual)
├── CarteiraTERRA          — Terra Investimentos
├── CarteiraMASTER         — Master (engine xlrd, abas Page 1/2/3)
├── CarteiraAVANTI         — Avanti (engine openpyxl)
├── CarteiraSingulareQI    — Singulare/QI (coluna Carteira Diária)
└── CarteiraPORTOFINO      — Portofino (engine openpyxl, abas Page 1/2/3)
```

---

## Estrutura de Arquivos

```
CARTEIRA/
│
├── 📄 Carteira.py              — Classes de carteira (toda a hierarquia OO)
├── 📄 funcoes_uteis.py         — Helpers de suporte (ETL, Excel, CSV)
├── 📄 carteira_apex.py         — Funções de geração por fundo (legado + MAPA_FUNCOES)
├── 📄 executar_carteira.py     — Interface gráfica (Tkinter) e CLI
├── 📄 config.json              — Configuração central de paths e fundos
├── 📄 requirements.txt         — Dependências Python
├── 📄 TODO.md                  — Débitos técnicos e roadmap
│
├── 📁 src/                     — Nova arquitetura modular
│   ├── 📁 config/
│   │   └── settings.py         — Singleton de configuração (lru_cache)
│   ├── 📁 core/
│   │   └── converters.py       — Funções puras de parsing/conversão
│   └── 📁 services/
│       ├── excel_writer.py     — Serviço de persistência Excel (xlwings)
│       ├── report_builder.py   — Builders de mapeamento CD/MEC por fundo
│       └── registry.py         — Registro declarativo de fundos
│
├── 📁 tests/                   — Suite de testes pytest
│   ├── conftest.py             — Fixtures compartilhadas
│   ├── 📁 core/
│   │   ├── test_converters.py  — 41 testes das funções puras
│   │   └── test_base.py        — 20 testes da CarteiraBase
│   └── 📁 services/
│       └── test_excel_writer.py
│
├── 📁 escritorio/              — Ambiente virtual (legado, não usar)
├── 📁 venv/                    — Ambiente virtual ativo
│
│   ── Arquivos legados (deprecados, manter por compatibilidade) ──
├── 📄 brl.py                   — [DEPRECATED] Cópia de fidara com paths hardcoded
├── 📄 fidara.py                — [DEPRECATED] Wrapper redundante de executar_carteira.py
├── 📄 carteira_avanti.py       — [DEPRECATED] Orquestração Avanti com paths hardcoded
├── 📄 carteira_genial.py       — [DEPRECATED] Orquestração Genial com paths hardcoded
├── 📄 carteira_master.py       — [DEPRECATED] Orquestração Master com paths hardcoded
├── 📄 carteira_qi.py           — [DEPRECATED] Orquestração QI com paths hardcoded
├── 📄 carteira_terra.py        — [DEPRECATED] Orquestração Terra com paths hardcoded
└── 📄 carteiras_singulari.py   — [DEPRECATED] Orquestração Singulare com paths hardcoded
```

---

## Fluxo de Dados

### 1. Leitura da Planilha (ETL)

```python
# Cada administradora tem sua classe com parsing específico
carteira = CarteiraBRL("C:/.../.../Carteira Diaria - Fidara FIDC - APEX.xlsb")
carteira.acrescentar_contas_pagar("Administração", "ANBIMA", "Gestão", ...)
carteira.carregar_dados(aba="CD_ATUAL")

# Após carregar_dados(), os atributos estão populados:
carteira.data                  # datetime — data de referência
carteira.patrimonio_total      # float — PL do fundo
carteira.saldo_tesouraria      # float — caixa disponível
carteira.valor_administracao   # float — taxa de administração
carteira.valor_taxa_gestao     # float — taxa de gestão
carteira.df_contas_filtrado    # DataFrame — contas agrupadas e classificadas
```

### 2. Construção do Mapeamento (Report Builder)

```python
builder = FidaraReportBuilder()

mapeamento_cd = builder.construir_mapeamento_cd(carteira)
# Retorna: [{"Categoria": "Data-Base", "Valor": datetime(...)}, ...]

mapeamento_mec = builder.construir_mapeamento_mec(carteira)
# Retorna: [{"Categoria": "DATA", "Valor": datetime(...)}, ...]
```

### 3. Persistência (Excel Writer)

```python
writer = ExcelWriter()
writer.salvar_carteira_diaria(
    path="/.../.../FIDARA FIDC.xlsb",
    mapeamento_cd=mapeamento_cd,
    mapeamento_mec=mapeamento_mec,
)
# Abre o arquivo no Excel após salvar
```

### 4. Fluxo via Registry (Nova Arquitetura)

```python
from src.registry import processar_fundo_registrado

# Uma única chamada processa o fundo inteiro
processar_fundo_registrado("FIDARA", aba="CD_ATUAL")
```

---

## Fundos Suportados

| Fundo | Administradora | Classe | Builder |
|-------|---------------|--------|---------|
| FIDARA FIDC | BRL Trust | `CarteiraBRL` | `FidaraReportBuilder` ✅ |
| CDC EMPRESTIMOS FIDC | BRL Trust | `CarteiraBRL` | `CdcReportBuilder` ✅ |
| CARMEL II FIDC | BRL Trust | `CarteiraBRL` | `CarmelIIReportBuilder` ✅ |
| GERAR CAPITAL FIDC | BRL Trust | `CarteiraBRL` | 🔄 Em construção |
| ENEL II FIDC | BRL Trust | `CarteiraBRL` | 🔄 Em construção |
| HOUSI FIDC | BRL Trust | `CarteiraBRL` | 🔄 Em construção |
| INFRA PORTFOLIO I | BRL Trust | `CarteiraBRL` | 🔄 Em construção |
| MOOVPAY | BRL Trust | `CarteiraBRL` | 🔄 Em construção |
| RESIDENCE CLUB FIDC | BRL Trust | `CarteiraBRL` | 🔄 Em construção |
| SB MULTIESTRATEGIA II | BRL Trust | `CarteiraBRL` | 🔄 Em construção |
| ZULU FIP | BRL Trust | `CarteiraBRL` | 🔄 Em construção |
| VIRTUS CAPITAL | BRL Trust | `CarteiraBRL` | 🔄 Em construção |
| CRÉDITOS COLATERALIZADOS | BRL Trust | `CarteiraBRL` | 🔄 Em construção |
| AVANTI FIDC | Avanti | `CarteiraAVANTI` | 🔄 Em construção |

---

## Administradoras

### BRL Trust (`CarteiraBRL`)
- Formato: `.xlsb` (pyxlsb) ou `.xlsx` (openpyxl)
- Aba: `CD_ATUAL`
- Estrutura: Planilha com marcadores de seção (ex: "VALORES A LIQUIDAR", "COTAS DE INVESTIMENTO")
- Coluna-chave: Detectada dinamicamente (geralmente `"Carteira"`)

### Genial (`CarteiraGenial`)
- Formato: `.xlsx`
- Aba: `CD_ATUAL`
- Coluna-chave: `"Unnamed: 0"`

### QI Tech (`CarteiraQI`)
- Formato: `.xlsx`
- Aba: `CD_ATUAL`
- Coluna-chave: `"Unnamed: 0"`, categorias em maiúsculo

### Terra (`CarteiraTERRA`)
- Formato: `.xlsx`
- Abas: `CD_ATUAL_CLASSE` e `CD_ATUAL_SUBCLASSE`

### Master (`CarteiraMASTER`)
- Formato: `.xls` (engine `xlrd`)
- Abas: `Page 1`, `Page 2`, `Page 3`

### Avanti (`CarteiraAVANTI`)
- Formato: `.xlsx` (engine `openpyxl`)
- Aba: `CD_ATUAL` + aba adicional `ESTOQUE_ATUAL`

### Singulare/QI (`CarteiraSingulareQI`)
- Formato: `.xlsx`
- Aba: `CD_ATUAL`
- Coluna-chave: `"Carteira Diária"`

### Portofino (`CarteiraPORTOFINO`)
- Formato: `.xlsx` ou `.xlsm` (engine `openpyxl`)
- Abas: `Page 1`, `Page 2`, `Page 3`

---

## Configuração

Toda a configuração está em **`config.json`** na raiz do projeto. O arquivo **não deve conter senhas**.

```jsonc
{
  "paths": {
    "root_dir": "Carmel Capital/Arquivos - Documentos/00 - CARMEL ASSET",
    "relatorio_diario": "01 - OPERACIONAL/CONTROLADORIA/01 - Relatorios Diarios/Relatorios Diarios",
    "feriados": "..."
  },

  // Nome do arquivo de relatório gerencial por fundo
  "arquivo_gerencial": {
    "FIDARA": "FIDARA FIDC.xlsb",
    "CDC": "CDC EMPRESTIMOS FIDC.xlsb"
    // ...
  },

  // Caminho relativo da carteira diária por fundo
  "carteiras": {
    "FIDARA": "01 - OPERACIONAL/.../Carteira Diaria - Fidara FIDC - APEX.xlsb",
    "CDC": "01 - OPERACIONAL/.../2025_ Carteira Diária - CDC Emprestimo.xlsx"
    // ...
  },

  // Palavras-chave para classificar contas a pagar de cada fundo
  "configuracoes_fundos": {
    "FIDARA": {
      "contas_pagar": ["Administração", "ANBIMA", "Auditoria", "Custódia", "CVM", "Gestão"]
    }
    // ...
  }
}
```

### Resolução de Caminhos

Todos os paths são **relativos ao `USERPROFILE` do Windows**:

```
%USERPROFILE%\{root_dir}\{caminho_relativo}
```

Exemplo: `C:\Users\Nowtek\Carmel Capital\Arquivos - Documentos\...\FIDARA FIDC.xlsb`

---

## Como Executar

### Pré-requisitos

```bash
# Criar e ativar o ambiente virtual
python -m venv venv
venv\Scripts\activate

# Instalar dependências
pip install -r requirements.txt
```

### Interface Gráfica (recomendado)

```bash
python executar_carteira.py
```

Abre uma janela Tkinter com um botão para cada fundo. Clicar no botão:
1. Lê as abas disponíveis na planilha do fundo
2. Abre um seletor de aba (padrão: `CD_ATUAL`)
3. Processa e salva o relatório em background (sem travar a UI)
4. Abre o arquivo Excel ao finalizar

### Linha de Comando

```bash
# Processar um fundo específico
python executar_carteira.py FIDARA
python executar_carteira.py FIDARA CD_ATUAL

# Listar fundos disponíveis
python executar_carteira.py
```

### Nova API (Registry)

```python
from src.registry import processar_fundo_registrado, listar_fundos_registrados

# Lista fundos com builder implementado
print(listar_fundos_registrados())  # ['FIDARA', 'CDC', 'CARMEL_II']

# Processa um fundo
processar_fundo_registrado("FIDARA")
processar_fundo_registrado("CDC", aba="CD_ATUAL")
```

---

## Testes

```bash
# Ativar o venv antes de rodar os testes
venv\Scripts\activate

# Rodar todos os testes
pytest tests/ -v

# Rodar com cobertura
pytest tests/ -v --cov=src --cov-report=term-missing

# Rodar apenas os testes de funções puras (sem Excel)
pytest tests/core/ -v
```

### Resultado atual

```
61 passed in 0.30s
```

| Módulo | Testes | Cobertura |
|--------|--------|-----------|
| `src/core/converters.py` | 41 | Funções puras de conversão e parsing |
| `Carteira.py` (CarteiraBase) | 20 | Inicialização, validação, acesso a DFs |
| `src/services/excel_writer.py` | — | Mocking de xlwings |

> **Nota**: Os testes de `core/` rodam **sem Excel instalado** — usam DataFrames sintéticos como fixtures. Isso garante que a CI/CD pode rodar em qualquer ambiente.

---

## Camada `src/` — Nova Arquitetura

### `src/config/settings.py`

Singleton de configuração com `lru_cache`. Carrega `config.json` **uma única vez** por execução.

```python
from src.config.settings import configuracoes, resolver_path_carteira, resolver_path_relatorio

cfg = configuracoes()                           # dict do config.json (cacheado)
path = resolver_path_carteira("FIDARA")         # path absoluto da carteira
rel  = resolver_path_relatorio("FIDARA")        # path absoluto do relatório
```

### `src/core/converters.py`

Funções **puras e testáveis** de conversão e parsing. Única fonte de verdade — elimina duplicatas entre `Carteira.py` e `funcoes_uteis.py`.

```python
from src.core.converters import (
    converter_moeda,          # "1.234,56" → 1234.56, "(500,00)" → -500.0
    resetar_cabecalho,        # Promove 1ª linha como cabeçalho
    encontrar_linha_categoria, # Localiza marcador de seção
    extrair_secao,            # Fatia o DataFrame entre dois índices
    detectar_coluna,          # Localiza coluna por lista de candidatos
    classificar_contas,       # Classifica e agrupa contas a pagar/receber
    buscar_valor_em_dataframe, # Busca escalar por chave de linha
)
```

### `src/services/excel_writer.py`

Isola **toda** a lógica de xlwings. O `Protocol` `PersistenciaBackend` define o contrato de interface para suportar futura migração para banco de dados.

```python
from src.services.excel_writer import ExcelWriter

writer = ExcelWriter(visible=False, delay_abertura=1.0)
writer.salvar_carteira_diaria(path, mapeamento_cd, mapeamento_mec)
writer.salvar_mapeamento_em_aba(path, "CD", mapeamento)
writer.salvar_novos_codigos(path, df_novos_codigos)
```

### `src/services/report_builder.py`

Builders por fundo. Cada um implementa `ReportBuilderBase` e retorna listas de mapeamento `{"Categoria": ..., "Valor": ...}`.

```python
from src.services.report_builder import FidaraReportBuilder

builder = FidaraReportBuilder()
mapeamento_cd  = builder.construir_mapeamento_cd(carteira)
mapeamento_mec = builder.construir_mapeamento_mec(carteira)
```

### `src/registry.py`

Registro declarativo de fundos. Substitui o `MAPA_FUNCOES` manual de `carteira_apex.py`.

```python
REGISTRO = {
    "FIDARA": ConfiguracaoFundo(
        nome="FIDARA FIDC",
        chave_carteira="FIDARA",
        chave_gerencial="FIDARA",
        classe_carteira=CarteiraBRL,
        builder=FidaraReportBuilder,
    ),
    # ...
}
```

**Para adicionar um novo fundo**, basta:
1. Criar o `XyzReportBuilder` em `report_builder.py`
2. Adicionar a entrada no `REGISTRO`

Nenhum código existente é modificado.

---

## Migração Futura para Banco de Dados

A arquitetura atual foi projetada para facilitar esta transição:

### O que muda

```python
# Hoje:
writer = ExcelWriter()

# Futuro:
writer = DatabaseWriter(connection_string="postgresql://...")
```

### O que NÃO muda

- Todas as classes de carteira (`CarteiraBRL`, `CarteiraQI`, etc.)
- Todos os builders de relatório (`FidaraReportBuilder`, etc.)
- Toda a camada `src/core/converters.py`
- O `registry.py` e `processar_fundo_registrado()`

### Implementação mínima do `DatabaseWriter`

```python
class DatabaseWriter:
    """Implementa PersistenciaBackend para PostgreSQL/SQLite."""

    def salvar_carteira_diaria(self, path, mapeamento_cd, mapeamento_mec):
        # INSERT INTO carteira_diaria (fundo, aba, categoria, valor, data_referencia)
        # VALUES (%s, 'CD', %s, %s, %s)
        ...

    def salvar_mapeamento_em_aba(self, path, aba, mapeamento):
        ...
```

### Estrutura de tabela sugerida

```sql
CREATE TABLE carteira_diaria (
    id            SERIAL PRIMARY KEY,
    fundo         VARCHAR(50) NOT NULL,
    aba           VARCHAR(10) NOT NULL,   -- 'CD' ou 'MEC'
    categoria     VARCHAR(200) NOT NULL,
    valor         NUMERIC(18, 6),
    data_referencia DATE NOT NULL,
    criado_em     TIMESTAMP DEFAULT NOW()
);
```

---

## Débitos Técnicos

Ver `TODO.md` para a lista completa. Os itens mais relevantes:

| Prioridade | Item |
|-----------|------|
| 🟢 Concluído | Criar builders para os 11 fundos restantes (100% Concluído) |
| 🟢 Concluído | Consolidar atributos duplicados em `CarteiraAVANTI` |
| 🟡 Média | Remover arquivos legados (`brl.py`, `fidara.py`, `carteira_*.py`) |
| 🟡 Média | Substituir `print()` por logging estruturado |
| 🟢 Baixa | Migrar para banco de dados |
| 🟢 Baixa | Configurar CI/CD com GitHub Actions |

---

## Dependências

| Pacote | Uso |
|--------|-----|
| `pandas` | Manipulação de DataFrames |
| `xlwings` | Escrita em arquivos Excel abertos |
| `pyxlsb` | Leitura de arquivos `.xlsb` |
| `xlrd` | Leitura de arquivos `.xls` (engine Master) |
| `openpyxl` | Leitura de arquivos `.xlsx` |
| `pytest` | Framework de testes |
| `pytest-cov` | Cobertura de testes |

---

## Convenções de Código

- **Docstrings**: Padrão Google Style em todas as classes e métodos públicos
- **Type hints**: Aplicados em todos os módulos novos (`src/`)
- **Imports tardios**: `xlwings` e `xlrd` são importados dentro das funções que os usam (dependências opcionais)
- **Nomenclatura**: Português brasileiro para nomes de domínio; inglês para nomes técnicos genéricos
- **Funções puras**: Toda lógica de transformação de dados vive em `src/core/converters.py`

---

*Última atualização: Maio 2026 — Carmel Capital Asset Management*
