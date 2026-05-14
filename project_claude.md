# Project Claude — Evolução do Sistema de Consolidação de Fundos

> Documento vivo de referência para desenvolvimento incremental.  
> Última atualização: 2026-05-14  
> Status: **Fase 1 — Planejamento aprovado, execução pendente**

---

## Decisões Arquiteturais Travadas

| Decisão | Escolha | Justificativa |
|---------|---------|---------------|
| GUI Desktop | **PySide6 (Qt6)** | Visual moderno, QTableWidget nativo, melhor ecossistema |
| Banco de Dados | **PostgreSQL** | Relacional robusto, suporte a JSON, versionamento |
| Configuração de mapeamentos | **JSON externo → DB** | Elimina hardcoding em Python |
| Padrão de parsing | **Strategy per admin** | Cada administradora tem layout próprio — inevitável |
| Migração | **Strangler Fig** | Sistema nunca para de funcionar |

---

## Diagnóstico do Sistema Atual

### Arquitetura Existente

```
executar_carteira.py (tkinter GUI)
  └── src/registry.py (REGISTRO dict)
        └── processar_fundo_registrado()
              ├── Carteira.py → CarteiraBase / CarteiraBRL / CarteiraAVANTI / ...
              │     └── carregar_dados() → _processar_planilha()
              ├── src/services/report_builder.py → *ReportBuilder (15 classes)
              │     └── construir_mapeamento_cd() / construir_mapeamento_mec()
              └── src/services/excel_writer.py → ExcelWriter
                    └── salvar_carteira_diaria()
```

### Inventário de Código

| Arquivo | Linhas | Responsabilidade | Problema |
|---------|--------|------------------|----------|
| `Carteira.py` | 1393 | Parsing de planilhas por administradora | 9 classes, muita duplicação entre elas |
| `report_builder.py` | 1356 | Mapeamento de dados para relatório | 15 builders com strings hardcoded |
| `funcoes_uteis.py` | 628 | Funções legadas variadas | Mistura de responsabilidades, deprecações |
| `excel_writer.py` | 265 | Persistência via xlwings | Bem isolado, já tem Protocol |
| `registry.py` | 295 | Registro de fundos | Bem estruturado, extensível |
| `settings.py` | 139 | Config centralizada | Pydantic já implementado |
| `converters.py` | 361 | Funções puras de conversão | Bem documentado, testável |
| `executar_carteira.py` | 237 | Entry point + GUI tkinter | GUI acoplada à execução |

### Administradoras e seus Padrões

| Classe | Admin | Engine | Aba | Coluna-chave | Fundos |
|--------|-------|--------|-----|-------------|--------|
| `CarteiraBRL` | BRL Trust | pyxlsb/openpyxl | CD_ATUAL | Detectada dinamicamente | FIDARA, CDC, CARMEL II, GERAR, ENEL, HOUSI, INFRA, MOOVPAY, RESIDENCE, SB II, ZULU, VIRTUS, CRED.COLAT. |
| `Carteira` | Cobuccio | openpyxl | CD_ATUAL | "Código" | Cobuccio fundos |
| `CarteiraGenial` | Genial | openpyxl | CD_ATUAL | "Unnamed: 0" | — |
| `CarteiraQI` | QI | openpyxl | CD_ATUAL | "Unnamed: 0" | — |
| `CarteiraTERRA` | Terra | openpyxl | CD_ATUAL_CLASSE + SUBCLASSE | "DESCRIÇÃO" | — |
| `CarteiraMASTER` | Master | xlrd | Page 1/2/3 | "Unnamed: 1" | — |
| `CarteiraAVANTI` | Avanti | openpyxl | CD_ATUAL | "Unnamed: 1" | AVANTI |
| `CarteiraSingulareQI` | Singulare | openpyxl | CD_ATUAL | "Carteira Diária" | — |
| `CarteiraPORTOFINO` | Portofino | openpyxl | Page 1/2/3 | "Unnamed: 1" | — |

### Padrão Comum a TODAS as Administradoras

Apesar das diferenças de layout, **todas** seguem o mesmo fluxo:

```
1. Abrir arquivo Excel/CSV
2. Detectar seções por marcadores de texto (ex: "VALORES A PAGAR", "COTAS DE INVESTIMENTO")
3. Extrair blocos de dados entre marcadores
4. Converter valores monetários
5. Classificar contas (pagar/receber) por palavras-chave
6. Popular atributos padronizados (patrimonio_total, saldo_tesouraria, taxas, etc.)
```

A diferença está em: **engine, nomes de aba, nomes de coluna, textos dos marcadores e posições**.

---

## Roadmap de Execução

### FASE 1 — Config-Driven Builders (Semanas 1-3)

**Objetivo**: Eliminar 100% dos mapeamentos hardcoded dos ReportBuilders.

#### Sprint 1.1 — Infraestrutura (Semana 1)

- [x] Criar diretório `mapeamentos/` na raiz do projeto
- [x] Criar schema Pydantic `ItemMapeamento` em `src/config/schemas.py`
- [x] Implementar `src/services/mapping_engine.py` com resolvers:
  - `atributo` → lê `carteira.data`, `carteira.patrimonio_total`, etc.
  - `valor_carteira` → chama `carteira.recuperar_valor_carteira(chave, coluna)`
  - `cotas` → chama `obter_valor_ordem(df_cotas, ordem, coluna)`
  - `taxa` → lê atributos de taxa (`valor_administracao`, etc.)
  - `contas` → chama `carteira.recuperar_contas(filtro, df)`
  - `fixo` → valor constante (ex: `0`, `0.5`)
  - `custom` → chama função Python registrada (para Avanti, SB II)
- [x] Criar `ConfigDrivenBuilder` genérico que usa o engine
- [x] Testes unitários para `MappingEngine` com mocks

#### Sprint 1.2 — Migração Piloto (Semana 2)

- [x] Exportar mapeamento do `ZuluReportBuilder` para `mapeamentos/ZULU.json`
- [x] Exportar mapeamento do `CreditosColateralizadosReportBuilder` para JSON
- [x] Validar: resultado config-driven == resultado hardcoded (teste de regressão)
- [x] Se OK: remover builders legados migrados
- [x] Exportar `FidaraReportBuilder` → JSON
- [x] Exportar `CdcReportBuilder` → JSON (inclui lógica de cotas sênior)

#### Sprint 1.3 — Migração Completa (Semana 3)

- [ ] Migrar todos os 15 builders restantes para JSON
- [ ] Tratar casos especiais:
  - `AvantiReportBuilder` → registrar funções custom no engine
  - `SbIIReportBuilder` → generalizar leitura de arquivo externo
  - `ResidenceReportBuilder` → loops de NC_ILHADOSOL
- [ ] Remover `report_builder.py` legado (manter apenas `ConfigDrivenBuilder`)
- [ ] Mover `obter_valor_ordem` de `carteira_apex.py` para `src/core/converters.py`
- [ ] Atualizar `registry.py` para usar `ConfigDrivenBuilder`

#### Entregável Fase 1
- Todo mapeamento em arquivos JSON editáveis
- Usuário pode alterar nomes de ativos/colunas sem abrir Python
- Zero regressão funcional

---

### FASE 2 — GUI de Mapeamento com PySide6 (Semanas 4-7)

**Objetivo**: Interface gráfica para criar/editar/validar mapeamentos.

#### Sprint 2.1 — Fundação GUI (Semana 4)

- [ ] Adicionar `PySide6` ao `requirements.txt`
- [ ] Criar `src/gui/__init__.py`
- [ ] Criar `src/gui/main_window.py` — janela principal com menu:
  - Menu "Lançamentos" → abre a tela de execução (migra do tkinter)
  - Menu "Mapeamentos" → abre o editor de mapeamentos
  - Menu "Configurações" → paths, destinatários
- [ ] Criar `src/gui/fund_selector.py` — lista de fundos com busca

#### Sprint 2.2 — Editor de Mapeamento (Semanas 5-6)

- [ ] Criar `src/gui/mapping_editor.py`:
  - QTableWidget editável com colunas: Categoria | Fonte | Chave ETL | Coluna | Multiplicador
  - Botões: Adicionar Linha | Remover Linha | Mover ↑↓
  - ComboBox para "Fonte" com opções do engine
  - Validação inline (célula vermelha se inválida)
- [ ] Criar `src/gui/preview_panel.py`:
  - Botão "Preview" carrega uma carteira real e mostra resultado simulado
  - Tabela lado-a-lado: Categoria | Valor Calculado
- [ ] Criar `src/gui/validators.py`:
  - Verifica se chaves ETL existem na carteira
  - Verifica se colunas numéricas são válidas
  - Alerta sobre categorias duplicadas

#### Sprint 2.3 — Versionamento e Polish (Semana 7)

- [ ] Criar `src/gui/version_history.py`:
  - Ao salvar, cria backup em `mapeamentos/historico/{FUNDO}_v{N}_{DATA}.json`
  - Lista de versões com botão "Reverter"
  - Diff visual entre versões (highlight de mudanças)
- [ ] Migrar a tela de execução do tkinter para PySide6
- [ ] Criar `src/gui/styles.py` — tema visual consistente
- [ ] Entry point: `python -m src.gui` ou `executar_carteira.py` detecta e usa PySide6

#### Entregável Fase 2
- Aplicação desktop PySide6 completa
- Editor visual de mapeamentos com validação
- Versionamento local de configurações
- Substituição completa do tkinter

---

### FASE 3 — Banco de Dados PostgreSQL (Semanas 8-11)

**Objetivo**: Persistir mapeamentos, histórico e metadados em banco relacional.

#### Sprint 3.1 — Modelagem e ORM (Semana 8)

- [ ] Adicionar `sqlalchemy`, `alembic`, `psycopg2-binary` ao requirements
- [ ] Criar `src/database/__init__.py`
- [ ] Criar `src/database/models.py`:

```python
# Tabelas principais
class Administradora(Base):      # BRL, Genial, QI, Terra, etc.
class Fundo(Base):               # CDC, FIDARA, CARMEL II, etc.
class CategoriaFinanceira(Base): # Hierarquia de categorias
class Mapeamento(Base):          # Versão de config por fundo/aba
class ItemMapeamento(Base):      # Cada linha do mapeamento
class HistoricoConsolidacao(Base): # Log de execuções
class AliasCategoria(Base):      # De-para de nomenclaturas
```

- [ ] Criar `src/database/connection.py` — engine + session factory
- [ ] Configurar Alembic em `src/database/migrations/`
- [ ] Criar migration inicial

#### Sprint 3.2 — Repository Layer (Semana 9)

- [ ] Criar `src/database/repositories.py`:

```python
class FundoRepository:
    def listar_ativos(self) -> list[Fundo]
    def obter_por_chave(self, chave: str) -> Fundo | None

class MapeamentoRepository:
    def obter_ativo(self, fundo_id: int, aba: str) -> Mapeamento
    def criar_versao(self, fundo_id: int, aba: str, itens: list) -> Mapeamento
    def listar_versoes(self, fundo_id: int) -> list[Mapeamento]
    def reverter(self, mapeamento_id: int) -> None

class HistoricoRepository:
    def registrar(self, fundo_id: int, resultado: dict) -> None
    def listar_por_fundo(self, fundo_id: int, limit: int) -> list
```

- [ ] Adaptar `MappingEngine` para aceitar tanto JSON quanto DB como fonte
- [ ] Criar `src/database/seed.py` — importa JSONs existentes para o banco

#### Sprint 3.3 — Migração de Dados e Integração (Semanas 10-11)

- [ ] Script de migração: `mapeamentos/*.json` → PostgreSQL
- [ ] Adaptar `registry.py` para consultar DB (com fallback para JSON)
- [ ] Adaptar GUI para ler/salvar no banco em vez de JSON
- [ ] Implementar histórico de consolidações (log de cada execução)
- [ ] Testes de integração com banco de teste

#### Entregável Fase 3
- Todas as configurações no PostgreSQL
- Versionamento completo com autor/data
- Histórico de consolidações consultável
- Fallback para JSON se DB indisponível

---

### FASE 4 — ETL Integrado e Simplificação de Parsing (Semanas 12-17)

**Objetivo**: Unificar o parsing das administradoras em um pipeline declarativo.

#### Sprint 4.1 — Abstração de Extractors (Semanas 12-13)

O insight chave: todas as administradoras seguem o **mesmo padrão** com **parâmetros diferentes**.

- [ ] Criar `src/etl/extractors/base.py`:

```python
@dataclass
class ConfigExtractor:
    engine: str                          # "pyxlsb", "openpyxl", "xlrd"
    abas: list[str]                      # ["CD_ATUAL"] ou ["Page 1", "Page 2"]
    coluna_chave: str                    # "Carteira", "Unnamed: 0", etc.
    marcadores_secao: dict[str, list[str]]  # {"contas_pagar": ["VALORES A PAGAR", ...]}
    campos_metadados: dict[str, dict]    # {"data": {"chave": "Data Posição", "coluna": 1}}
    campos_metricas: dict[str, dict]     # {"patrimonio_total": {"chave": "PL Posição", "coluna": 1}}
```

- [ ] Criar `src/etl/extractors/excel_extractor.py`:

```python
class GenericExcelExtractor:
    """Substitui TODAS as 9 classes de Carteira.py"""
    def __init__(self, config: ConfigExtractor): ...
    def extrair(self, path: str) -> DadosCarteira: ...
```

- [ ] Externalizar configs de cada admin para `configs/extractors/brl.json`, `genial.json`, etc.

#### Sprint 4.2 — Pipeline Unificado (Semanas 14-15)

- [ ] Criar `src/etl/pipeline.py`:

```python
class Pipeline:
    def executar(self, fundo: ConfiguracaoFundo) -> Resultado:
        dados = self.extractor.extrair(fundo.path)
        mapeamento = self.resolver.resolver(dados, fundo.config_mapeamento)
        self.writer.salvar(fundo.path_relatorio, mapeamento)
```

- [ ] Refatorar `registry.py` para usar Pipeline
- [ ] Testes de regressão: saída nova == saída legada para cada fundo

#### Sprint 4.3 — Web Scraping e Automação (Semanas 16-17)

- [ ] Criar `src/scrapers/base.py` — ScraperBase com retry, logging, auth
- [ ] Implementar scrapers por administradora conforme necessidade
- [ ] Criar `src/scrapers/auth/credential_store.py` — keyring para senhas
- [ ] Agendamento básico com APScheduler

#### Entregável Fase 4
- `Carteira.py` (1393 linhas) substituído por configs JSON + 1 extractor genérico
- Pipeline E→T→L unificado
- Download automático de arquivos

---

### FASE 5 — Dashboard Web (Semanas 18-24)

**Objetivo**: Plataforma web para monitoramento e operação.

#### Sprint 5.1 — API Backend (Semanas 18-20)

- [ ] Criar `src/api/app.py` com FastAPI
- [ ] Routers: `/fundos`, `/mapeamentos`, `/consolidacoes`, `/execucao`
- [ ] Autenticação básica (JWT)
- [ ] Documentação automática (Swagger)

#### Sprint 5.2 — Frontend React (Semanas 21-24)

- [ ] Dashboard com KPIs por fundo
- [ ] Editor de mapeamentos web (substitui PySide6 para uso remoto)
- [ ] Monitor de ETL em tempo real
- [ ] Histórico de consolidações com drill-down

#### Entregável Fase 5
- Sistema acessível via browser
- API REST documentada
- Dashboard operacional

---

## Taxonomia Financeira

### Hierarquia de Categorias (Base para modelagem relacional)

```
ATIVOS
├── Direitos Creditórios
│   ├── A Vencer
│   ├── Vencidos
│   ├── Nota Comercial (NC)
│   └── PDD (Provisão de Devedores Duvidosos)
├── Títulos de Liquidez
│   ├── Fundo DI / Zeragem
│   ├── Compromissada / Over
│   └── CDB / LCI / LCA
├── Títulos Públicos
│   ├── NTN-B
│   ├── LFT
│   └── LTN
├── Fundos de Investimento
│   ├── FIC FIDC
│   ├── FI RF
│   └── FIP
├── Tesouraria
│   ├── Conta Corrente
│   └── Saldo Bloqueado
└── Outros Ativos
    ├── CRI / CRA
    ├── Debêntures
    └── Precatórios

PASSIVOS / COTAS
├── Cota Subordinada
├── Cota Mezanino (A, B, ...)
└── Cota Sênior (1, 2, 3, ...)

DESPESAS
├── Taxas Regulatórias
│   ├── Administração
│   ├── Gestão
│   ├── Custódia
│   ├── Auditoria
│   ├── Performance
│   └── Consultoria
├── Taxas de Mercado
│   ├── CVM
│   ├── ANBIMA
│   ├── CETIP / SELIC
│   └── Banco Liquidante
├── Diferimentos
│   ├── Diferimento CVM
│   └── Diferimento ANBIMA
└── Contas
    ├── Contas a Pagar
    └── Contas a Receber

INDICADORES
├── Patrimônio Líquido
├── Subordinação Mínima
├── Razão de Garantia
└── Rentabilidade Acumulada
```

### Padronização de Nomenclatura

Cada categoria terá um **nome canônico** no banco e uma tabela de **aliases**:

| Nome Canônico | Aliases encontrados no código atual |
|--------------|-------------------------------------|
| `taxa_administracao` | "Taxa de Administração", "Taxa Adm" |
| `taxa_cvm` | "Taxa Fisc. CVM", "TAXA CVM", "Dif. Despesa Fisc. CVM", "Despesa CVM" |
| `taxa_anbima` | "Taxa ANBIMA", "Taxa Anbima (-)", "Despesa ANBIMA" |
| `taxa_gestao` | "Taxa de Gestão" |
| `taxa_custodia` | "Taxa de Custódia" |
| `taxa_auditoria` | "Taxa de Auditoria", "Despesa de Auditoria" |
| `taxa_performance` | "Taxa de Performance" |
| `taxa_consultoria` | "Taxa de Consultoria", "Taxa Consultoria" |
| `contas_pagar` | "Outras despesas (-)", "Outras despesas operacionais (-)" |
| `contas_receber` | "Outros valores a receber (+)", "Outros valores (+)" |

---

## Estrutura de Pastas — Visão Final

```
CARTEIRA/
├── project_claude.md              ← Este documento
├── config.json                    # Config global (paths, destinatários)
├── requirements.txt
├── executar_carteira.py           # Entry point (migra para PySide6 na Fase 2)
│
├── mapeamentos/                   # [FASE 1] JSONs editáveis por fundo
│   ├── CDC.json
│   ├── FIDARA.json
│   ├── CARMEL_II.json
│   ├── ...
│   └── historico/                 # Backups versionados
│
├── configs/                       # [FASE 4] Configs de extractors por admin
│   └── extractors/
│       ├── brl.json
│       ├── genial.json
│       └── avanti.json
│
├── src/
│   ├── config/
│   │   ├── settings.py            # Pydantic config loader
│   │   └── schemas.py             # [FASE 1] Schemas de mapeamento
│   ├── core/
│   │   ├── converters.py          # Funções puras de conversão
│   │   ├── logger.py
│   │   └── taxonomy.py            # [FASE 1] Enum/constantes de categorias
│   ├── services/
│   │   ├── mapping_engine.py      # [FASE 1] Motor de resolução
│   │   ├── report_builder.py      # ConfigDrivenBuilder (substitui 15 builders)
│   │   └── excel_writer.py        # Persistência Excel
│   ├── gui/                       # [FASE 2] PySide6
│   │   ├── main_window.py
│   │   ├── mapping_editor.py
│   │   ├── fund_selector.py
│   │   ├── preview_panel.py
│   │   ├── version_history.py
│   │   └── styles.py
│   ├── database/                  # [FASE 3] PostgreSQL
│   │   ├── models.py
│   │   ├── connection.py
│   │   ├── repositories.py
│   │   ├── seed.py
│   │   └── migrations/
│   ├── etl/                       # [FASE 4]
│   │   ├── extractors/
│   │   │   ├── base.py
│   │   │   └── excel_extractor.py
│   │   ├── transformers/
│   │   ├── loaders/
│   │   ├── pipeline.py
│   │   └── scheduler.py
│   ├── scrapers/                  # [FASE 4]
│   │   ├── base.py
│   │   └── auth/
│   ├── api/                       # [FASE 5]
│   │   ├── app.py
│   │   └── routers/
│   └── registry.py
│
├── tests/
│   ├── unit/
│   ├── integration/
│   └── fixtures/
│
├── Carteira.py                    # Legado → substituído na Fase 4
├── carteira_apex.py               # Legado → funções migram para core
└── funcoes_uteis.py               # Legado → deprecado progressivamente
```

---

## Riscos e Mitigações

| Risco | Prob. | Mitigação |
|-------|-------|-----------|
| Avanti/SB II têm lógica não-declarativa | Alta | Tipo `"custom"` no engine chama função Python registrada |
| Admin muda layout da planilha | Alta | Config externalizada permite correção sem deploy |
| Regressão ao migrar builder | Média | Teste automatizado: saída nova == saída legada |
| PostgreSQL indisponível em prod | Baixa | Fallback para JSON local (Fase 3 mantém dual-source) |
| PySide6 conflito com xlwings | Baixa | Testar coexistência; xlwings roda em thread separada |

---

## Convenções de Desenvolvimento

1. **Commits**: `fase1: descrição`, `fase2: descrição`, etc.
2. **Branches**: `feature/fase1-mapping-engine`, `feature/fase2-gui`, etc.
3. **Testes**: Todo código novo deve ter teste unitário antes de merge
4. **Migração**: Nunca remover código legado antes de validar o substituto
5. **JSON de mapeamento**: UTF-8, indentação 2 espaços, ordenado por `categoria`

---

## Registro de Progresso

### Fase 1 — Config-Driven Builders
| Task | Status | Data |
|------|--------|------|
| Schema Pydantic `ItemMapeamento` | ⬜ Pendente | — |
| `MappingEngine` com resolvers | ⬜ Pendente | — |
| `ConfigDrivenBuilder` genérico | ⬜ Pendente | — |
| Migração ZULU (piloto) | ⬜ Pendente | — |
| Migração CDC | ⬜ Pendente | — |
| Migração todos os builders | ⬜ Pendente | — |
| Remoção do `report_builder.py` legado | ⬜ Pendente | — |

### Fase 2 — GUI PySide6
| Task | Status | Data |
|------|--------|------|
| Janela principal + menu | ⬜ Pendente | — |
| Editor de mapeamento | ⬜ Pendente | — |
| Preview panel | ⬜ Pendente | — |
| Versionamento local | ⬜ Pendente | — |
| Migração do tkinter | ⬜ Pendente | — |

### Fase 3 — PostgreSQL
| Task | Status | Data |
|------|--------|------|
| Modelagem + ORM | ⬜ Pendente | — |
| Repository layer | ⬜ Pendente | — |
| Migração JSON → DB | ⬜ Pendente | — |
| Histórico de consolidações | ⬜ Pendente | — |

### Fase 4 — ETL Integrado
| Task | Status | Data |
|------|--------|------|
| GenericExcelExtractor | ⬜ Pendente | — |
| Pipeline unificado | ⬜ Pendente | — |
| Scrapers | ⬜ Pendente | — |

### Fase 5 — Dashboard Web
| Task | Status | Data |
|------|--------|------|
| FastAPI backend | ⬜ Pendente | — |
| React frontend | ⬜ Pendente | — |
