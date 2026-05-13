# TODO — Débitos Técnicos e Melhorias Futuras

## 🔴 Alta Prioridade (corrigir antes do próximo release)

### Builders de Relatório Faltando
Os fundos abaixo ainda não possuem `ReportBuilder` em `src/services/report_builder.py`.
Continuam usando as funções legadas em `carteira_apex.py`:

- [x] `GerarReportBuilder` — GERAR CAPITAL FIDC
- [x] `EnelReportBuilder` — ENEL II FIDC
- [x] `HousiReportBuilder` — HOUSI FIDC
- [x] `InfraReportBuilder` — INFRA PORTFOLIO I
- [x] `MoovpayReportBuilder` — MOOVPAY
- [x] `ResidenceReportBuilder` — RESIDENCE CLUB FIDC
- [x] `SbIIReportBuilder` — SB MULTIESTRATEGIA II
- [x] `ZuluReportBuilder` — ZULU FIP
- [x] `VirtusReportBuilder` — VIRTUS CAPITAL
- [x] `CreditosColateralizadosReportBuilder` — CRÉDITOS COLATERALIZADOS I
- [x] `AvantiReportBuilder` — AVANTI FIDC (usa `CarteiraAVANTI` — requer atenção especial)

### Atributos Duplicados em CarteiraAVANTI
- [x] `CarteiraAVANTI` declara `taxa_*` (ex: `taxa_administracao`) que duplicam `valor_*` definidos em `CarteiraBase` (ex: `valor_administracao`). Consolidar para usar apenas os atributos da base.

---

## 🟡 Média Prioridade (próximas sprints)

### Completar Registro de Fundos
- [x] Adicionar os 9 fundos restantes ao `REGISTRO` em `src/registry.py` após criar os respectivos builders.

### Banco de Dados (Melhoria Futura)
- [ ] Criar interface abstrata `DataWriter` (ou `PersistenciaBase`) para substituir a dependência direta de `ExcelWriter`.
- [ ] Implementar `DatabaseWriter` (ex: PostgreSQL/SQL Server) para mapear a saída de `MapeamentoExcel` para tabelas relacionais em banco de dados.

### Remover Arquivos Legados
- [x] `brl.py` — cópia de fidara com paths hardcoded. Deletado.
- [x] `fidara.py` — wrapper redundante de `executar_carteira.py`. Deletado.
- [x] `refactor.py` / `refactor_aba.py` — scripts de migração pontuais. Deletados.
- [x] `carteira_avanti.py`, `carteira_genial.py`, `carteira_master.py`,
  `carteira_qi.py`, `carteira_terra.py`, `carteiras_singulari.py` — deletados.

### Nomenclatura Pendente
- [x] Renomear `validar_valor()` em `_MixinCdAtual` → `buscar_valor_por_descricao()`
- [x] Renomear `recuperar_fund_investimento()` em `funcoes_uteis.py` → `extrair_valor_fundo_investimento()`
- [x] Padronizar uso de `secoes_carteira` em vez de `dfs` como nome de variável local

### Typing Completo
- [x] Adicionar type hints a todos os métodos de `funcoes_uteis.py`
- [x] Adicionar `py.typed` marker para suporte a mypy

---

## 🟢 Baixa Prioridade / Melhorias Futuras

### Performance
- [x] `processar_dataframes()` lê o arquivo Excel duas vezes (linhas 22-23). Consolidado.
- [x] Avaliada e removida leitura dupla nas classes filhas (`CarteiraQI`, `CarteiraGenial`, `CarteiraSingulareQI`, `CarteiraMASTER`, `CarteiraPORTOFINO`), reutilizando os DFs já instanciados.

### Migração para Banco de Dados
> A arquitetura atual já está preparada para esta mudança.
> O `ExcelWriter` implementa o `PersistenciaBackend` Protocol.
> Para migrar:

- [ ] Criar `DatabaseWriter` implementando `PersistenciaBackend`
  (PostgreSQL/SQLite com SQLAlchemy).
- [ ] Criar tabela de mapeamentos: `carteira_diaria(fundo, data, categoria, valor)`.
- [ ] Substituir `ExcelWriter` por `DatabaseWriter` no `registry.py` (injeção de dependência).
- [ ] Manter `ExcelWriter` como exportador secundário opcional.

### Observabilidade
- [x] Substituir `print()` por logging estruturado (`logging.getLogger(__name__)`).
- [x] Adicionar métricas de tempo de execução por fundo.
- [x] Implementar relatório de erros consolidado ao final do batch.

### Testes
- [x] Adicionar testes unitários com mocks para ReportBuilders (Fidara e CDC concluídos como prova de conceito).
- [x] Adicionar testes de integração com um arquivo Excel sintético de teste.
- [x] Configurar CI/CD (GitHub Actions) para rodar pytest automaticamente.
- [x] Atingir >80% de cobertura de testes nas funções puras (Atualmente 100% em `converters.py`).

### Configuração
- [x] Migrar senhas/tokens sensíveis de `config.json` para variáveis de ambiente (`.env`).
- [x] Adicionar schema de validação do `config.json` (Pydantic).
- [x] Documentar campos obrigatórios e opcionais do `config.json` (`CONFIG_README.md`).

---

## ✅ Concluído

- [x] Corrigido bug `except e:` → `except Exception as exc:` em `funcoes_uteis.py`
- [x] Corrigido bug variável `aba` inexistente em `processar_dataframes()`
- [x] Removido código morto inacessível após `return` em `criar_df_entre_linhas_unico`
- [x] Removidas funções com dependência em global inexistente (`df_dict_despesas`)
- [x] Criado `src/config/settings.py` — configuração centralizada com cache
- [x] Criado `src/core/converters.py` — única fonte de verdade para parsing/conversão
- [x] Criado `src/services/excel_writer.py` — isolamento completo do xlwings com Protocol
- [x] Criado `src/services/report_builder.py` — builders por fundo (FIDARA, CDC, CARMEL II)
- [x] Criado `src/registry.py` — registro declarativo substituindo MAPA_FUNCOES
- [x] Criado `tests/` com suite pytest completa (30+ casos de teste)
- [x] Docstrings Google Style adicionadas aos módulos novos e corrigidos
