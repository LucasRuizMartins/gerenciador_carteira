# Skill: Cadastrar ou Atualizar um Fundo

> **Versão:** 2.0 — Config-Driven (ConfigDrivenBuilder + JSON)
> **Para agentes e programadores.** Use este documento como checklist completo sempre que um novo fundo precisar ser adicionado ou um fundo existente atualizado.

---

## Visão Geral da Arquitetura

```
config.json                  → caminhos dos arquivos e taxas esperadas
   ↓
src/registry.py (REGISTRO)   → qual classe + qual mapeamento JSON usar
   ↓
mapeamentos/{FUNDO}.json     → como montar o relatório CD e MEC (declarativo)
   ↓
src/services/mapping_engine  → executa o mapeamento contra o objeto carteira
   ↓
src/services/excel_writer    → escreve o Excel gerencial final
```

**Princípio DRY:** Nenhuma função Python de geração é criada por fundo. Tudo é declarado em JSON. Funções custom (`fonte: "custom"`) só são criadas quando a lógica é impossível de expressar declarativamente.

---

## Checklist Completo — Novo Fundo

### ✅ Passo 1 — `config.json`

**Arquivo:** [`config.json`](file:///c:/Users/Nowtek/Carmel%20Capital/TECNOLOGIA%20-%20Documentos/Geral/DESENVOLVIMENTO/PYTHON/CARTEIRA/config.json)

São **3 seções** obrigatórias para qualquer fundo:

#### 1.1 `carteiras` — caminho do arquivo de entrada (CD)

```json
"carteiras": {
    "NOME_FUNDO": "01 - OPERACIONAL/CONTROLADORIA/01 - Relatorios Diarios/Carteira Diaria/Fundos Ativos/PASTA_FUNDO/ARQUIVO_CD.xlsb"
}
```

> ⚠️ O caminho é **relativo** à raiz do OneDrive (`ROOT_DIR` no `.env`). Use `/` mesmo no Windows.

#### 1.2 `arquivo_gerencial` — caminho do arquivo Excel de saída (relatório)

```json
"arquivo_gerencial": {
    "NOME_FUNDO": "NOME DO FUNDO GERENCIAL.xlsb"
}
```

> O arquivo gerencial fica em `ROOT_DIR / paths.relatorio_diario / NOME_ARQUIVO`.

#### 1.3 `configuracoes_fundos` — taxas que serão classificadas como "contas a pagar"

```json
"configuracoes_fundos": {
    "NOME_FUNDO": {
        "contas_pagar": [
            "Administração", "ANBIMA", "Auditoria",
            "Custódia", "Gestão", "CVM", "SELIC",
            "CETIP", "Banco Liquidante"
        ]
    }
}
```

> ⚠️ **Crítico!** Se esta seção faltar, `obter_contas_pagar_fundo()` retorna `[]` e **todas as taxas ficam zeradas** no relatório. As palavras-chave são buscadas por `str.contains(case=False)` no `df_contas_filtrado`.

> 💡 As palavras-chave devem casar com as descrições reais no arquivo Excel do administrador (ex: "Gestão" casa com "TAXA DE GESTÃO").

---

### ✅ Passo 2 — `mapeamentos/{NOME_FUNDO}.json`

**Diretório:** [`mapeamentos/`](file:///c:/Users/Nowtek/Carmel%20Capital/TECNOLOGIA%20-%20Documentos/Geral/DESENVOLVIMENTO/PYTHON/CARTEIRA/mapeamentos/)

Crie o arquivo JSON de mapeamento. A estrutura obrigatória é:

```json
{
  "versao": "1.0",
  "fundo": "NOME_FUNDO",
  "administradora": "BRL",
  "mapeamento_cd": [ ... ],
  "mapeamento_mec": [ ... ]
}
```

**Administradoras reconhecidas:** `"BRL"`, `"AVANTI"`, `"GENIAL"`, `"TERRA"`, `"SINGULARE"`, `"APEX"`.

#### Fontes disponíveis para cada item

| `fonte`         | Campos adicionais obrigatórios | Descrição |
|-----------------|-------------------------------|-----------|
| `"atributo"`    | `"campo"` (ex: `"data"`, `"patrimonio_total"`, `"pdd"`) | Lê atributo direto do objeto carteira |
| `"taxa"`        | `"campo"` (ex: `"valor_administracao"`, `"valor_taxa_gestao"`) | Lê atributo de taxa (populado por `_popular_taxas`) |
| `"valor_carteira"` | `"chave_etl"` (código da linha), `"coluna"` (int ou nome) | Chama `carteira.recuperar_valor_carteira(chave, coluna)` |
| `"soma_secao"`  | `"secao"` (chave em `_dataframes`), `"coluna"` (nome) | Soma coluna inteira de uma seção. **Uso principal: Singulare/QI** |
| `"cotas"`       | `"ordens"` (lista de int), `"coluna_valor"` | Busca em `df_cotas_superiores` |
| `"contas"`      | `"filtro"` (ex: `"Contas a pagar"`), `"dataframe"` | Chama `carteira.recuperar_contas(filtro, df)` |
| `"fixo"`        | `"valor_fixo"` (float) | Valor constante (ex: `0.0`) |
| `"custom"`      | `"nome_funcao"` (str), + campos extras livres | Delega para função Python registrada no engine. Usar apenas quando os outros não bastam |
| `"api_json"`    | `"caminho_json"`, `"filtros"`, `"campo_valor"` | Extrai de `carteira.raw_data` (fundos API Apex) |

#### Atributos de taxa disponíveis (`fonte: "taxa"`)

| Campo | Descrição |
|-------|-----------|
| `valor_administracao` | Taxa de Administração |
| `valor_taxa_gestao` | Taxa de Gestão |
| `valor_taxa_custodia` | Taxa de Custódia |
| `valor_taxa_auditoria` | Taxa de Auditoria |
| `valor_taxa_cvm` | Taxa CVM |
| `valor_anbima` | Taxa ANBIMA |
| `valor_taxa_performance` | Taxa de Performance |
| `valor_selic` | SELIC |
| `valor_cetip` | CETIP |
| `valor_liq_banco` | Banco Liquidante |

#### Atributos diretos disponíveis (`fonte: "atributo"`)

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `data` | `date` | Data-base da carteira |
| `patrimonio_total` | `float` | Patrimônio Líquido total |
| `saldo_tesouraria` | `float` | Saldo em tesouraria |
| `pdd` | `float` | PDD (Provisão de Devedores Duvidosos) |
| `outros_valores_pagar` | `float` | Outras despesas |
| `outros_valores_receber` | `float` | Outros recebimentos |

#### Modificadores opcionais

```json
{
  "categoria": "Nome",
  "fonte": "atributo",
  "campo": "patrimonio_total",
  "multiplicador": -1.0    ← inverte o sinal (ex: passivo)
}
```

#### Itens acumulados (mesma categoria, múltiplas fontes)

Quando dois itens têm a **mesma `categoria`**, o engine **soma automaticamente** os valores. Use isso para Over = ltno + ntn_o + lfto:

```json
{ "categoria": "Over/Compromissada", "fonte": "soma_secao", "secao": "ltno", "coluna": "Valor Líquido" },
{ "categoria": "Over/Compromissada", "fonte": "soma_secao", "secao": "ntn o", "coluna": "Valor Líquido" },
{ "categoria": "Over/Compromissada", "fonte": "soma_secao", "secao": "lfto", "coluna": "Valor Líquido" }
```

#### Exemplos por tipo de administradora

**BRL (padrão — maioria dos fundos):**
```json
{ "categoria": "Data-Base", "fonte": "atributo", "campo": "data" },
{ "categoria": "Saldo em Tesouraria", "fonte": "atributo", "campo": "saldo_tesouraria" },
{ "categoria": "GV Cash", "fonte": "valor_carteira", "chave_etl": "GV CASH RENDA FIXA", "coluna": 5 },
{ "categoria": "Taxa de Administração", "fonte": "taxa", "campo": "valor_administracao" },
{ "categoria": "Outras despesas (-)", "fonte": "contas", "filtro": "Contas a pagar", "dataframe": "df_contas_filtrado" }
```

**Singulare/QI (COBUCCIO):**
```json
{ "categoria": "Direitos a Vencer", "fonte": "soma_secao", "secao": "ccven", "coluna": "Valor Líquido" },
{ "categoria": "NTN-B", "fonte": "soma_secao", "secao": "ntn", "coluna": "Valor Líquido" },
{ "categoria": "PDD - Prov. de Perdas", "fonte": "atributo", "campo": "pdd" }
```

---

### ✅ Passo 3 — `src/registry.py`

**Arquivo:** [`src/registry.py`](file:///c:/Users/Nowtek/Carmel%20Capital/TECNOLOGIA%20-%20Documentos/Geral/DESENVOLVIMENTO/PYTHON/CARTEIRA/src/registry.py)

Adicione uma entrada no dicionário `REGISTRO`:

```python
"NOME_FUNDO": ConfiguracaoFundo(
    nome="Nome Completo do Fundo",
    chave_carteira="NOME_FUNDO",          # deve bater com config.json["carteiras"]
    chave_gerencial="NOME_FUNDO",         # deve bater com config.json["arquivo_gerencial"]
    classe_carteira=CarteiraBRL,           # ver tabela abaixo
    builder=lambda: ConfigDrivenBuilder.de_arquivo("NOME_FUNDO.json"),
    # Opcional — só se a chave em configuracoes_fundos for diferente da chave_gerencial:
    chave_config_fundo="NOME FUNDO COM ESPAÇOS",
    # Opcional — forçar nome do administrador:
    administrador="BRL",
),
```

#### Classes de carteira disponíveis

| Classe | Administradora | Quando usar |
|--------|---------------|-------------|
| `CarteiraBRL` | BRL Trust | Maioria dos FIDCs (FIDARA, CDC, GERAR, etc.) |
| `CarteiraAVANTI` | Avanti | Fundos administrados pela Avanti |
| `CarteiraSingulareQI` | Singulare / QI | COBUCCIO e similares |
| `CarteiraGenial` | Genial | Fundos Genial |
| `CarteiraTERRA` | Terra | Fundos Terra |
| `CarteiraApexAPI` | Apex (API) | Fundos com dados via API Prisma |

> ⚠️ **Import obrigatório:** verifique que a classe está importada no topo de `registry.py`:
> ```python
> from Carteira import CarteiraBRL, CarteiraAVANTI, CarteiraSingulareQI, CarteiraGenial, CarteiraTERRA
> ```

---

### ✅ Passo 4 — Testes

**Diretório:** [`tests/services/`](file:///c:/Users/Nowtek/Carmel%20Capital/TECNOLOGIA%20-%20Documentos/Geral/DESENVOLVIMENTO/PYTHON/CARTEIRA/tests/services/)

Crie o arquivo `tests/services/test_{nome_fundo_lower}.py`.

#### Template mínimo de teste

```python
"""
Testes para o mapeamento {NOME_FUNDO}.json.
"""
import sys, os
from datetime import date
from unittest.mock import MagicMock
import pandas as pd
import pytest

_RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _RAIZ not in sys.path: sys.path.insert(0, _RAIZ)

from src.services.config_driven_builder import ConfigDrivenBuilder

@pytest.fixture
def carteira():
    m = MagicMock()
    m.data = date(2025, 1, 31)
    m.patrimonio_total = 10_000_000.0
    m.saldo_tesouraria = 500_000.0
    m.pdd = -50_000.0
    m.valor_administracao = -10_000.0
    m.valor_taxa_gestao = -20_000.0
    m.valor_taxa_custodia = -5_000.0
    m.valor_taxa_auditoria = -3_000.0
    m.valor_taxa_cvm = -1_000.0
    m.valor_anbima = 0.0
    m.valor_taxa_performance = 0.0
    m.valor_selic = 0.0
    m.valor_cetip = 0.0
    m.valor_liq_banco = 0.0
    m.df_contas_filtrado = pd.DataFrame({
        "Histórico": ["Administração", "Contas a pagar"],
        "Valor Total": [-10_000.0, -5_000.0]
    })
    m.recuperar_valor_carteira.return_value = 0.0
    m.recuperar_contas.return_value = 0.0
    return m

class TestNomeFundoJson:
    def test_json_carregavel(self):
        builder = ConfigDrivenBuilder.de_arquivo("NOME_FUNDO.json")
        assert builder.fundo == "NOME_FUNDO"

    def test_cd_tem_data_base(self, carteira):
        builder = ConfigDrivenBuilder.de_arquivo("NOME_FUNDO.json")
        resultado = builder.construir_mapeamento_cd(carteira)
        assert any(r["Categoria"] == "Data-Base" for r in resultado)

    def test_taxa_administracao(self, carteira):
        builder = ConfigDrivenBuilder.de_arquivo("NOME_FUNDO.json")
        resultado = builder.construir_mapeamento_cd(carteira)
        adm = next((r["Valor"] for r in resultado if "Administr" in r["Categoria"]), None)
        assert adm == -10_000.0
```

#### Rodar testes

```bash
python -m pytest tests/services/test_nome_fundo.py -v
python -m pytest tests/ -v  # suite completa
```

---

### ✅ Passo 5 — Nova Administradora (somente se necessário)

Execute este passo **apenas se a administradora ainda não existir** em `MAPA_CLASSES_ADMINISTRADOR` no `registry.py`.

#### 5.1 Criar a classe em `Carteira.py`

```python
class CarteiraNovaAdmin(CarteiraBase):
    """Leitor de planilhas da administradora NovaAdmin."""

    def __init__(self, path_carteira=None):
        super().__init__(path_carteira)
        # Atributos específicos da estrutura do Excel desta admin
        self.dataframe: pd.DataFrame | None = None

    def carregar_dados(self, aba="CD_ATUAL") -> None:
        self._validar_path()
        self.dataframe = pd.read_excel(self.path_carteira, sheet_name=aba)
        self._dataframes = self._processar_planilha(aba)
        self._carregar_contas()

    def _processar_planilha(self, aba="CD_ATUAL") -> dict[str, pd.DataFrame]:
        # Retornar dict com seções nomeadas (ex: {"contas_pagar": df, "renda_fixa": df2})
        return {}

    def _carregar_contas(self) -> None:
        # Popular df_contas_filtrado e chamar _popular_taxas()
        pass
```

#### 5.2 Registrar em `MAPA_CLASSES_ADMINISTRADOR` (registry.py)

```python
MAPA_CLASSES_ADMINISTRADOR: dict[str, type[CarteiraBase]] = {
    "APEX": CarteiraApexAPI,
    "AVANTI": CarteiraAVANTI,
    "GENIAL": CarteiraGenial,
    "TERRA": CarteiraTERRA,
    "SINGULARE": CarteiraSingulareQI,
    "NOVA_ADMIN": CarteiraNovaAdmin,  # ← adicionar aqui
}
```

#### 5.3 Registrar no import de `registry.py`

```python
from Carteira import (
    CarteiraBase, CarteiraBRL, CarteiraAVANTI,
    CarteiraGenial, CarteiraTERRA, CarteiraSingulareQI,
    CarteiraNovaAdmin,  # ← adicionar
)
```

---

### ✅ Passo 6 — Funções Custom (somente se necessário)

Use `fonte: "custom"` apenas quando a lógica **não puder ser expressa** com as fontes declarativas disponíveis.

#### 6.1 Implementar no `config_driven_builder.py`

**Arquivo:** [`src/services/config_driven_builder.py`](file:///c:/Users/Nowtek/Carmel%20Capital/TECNOLOGIA%20-%20Documentos/Geral/DESENVOLVIMENTO/PYTHON/CARTEIRA/src/services/config_driven_builder.py)

Adicione dentro do método `_registrar_resolvers_cobuccio()` ou crie um novo método de registro:

```python
def _registrar_resolvers_meu_fundo(self) -> None:
    reg = self._engine.register_custom_resolver

    def resolver_meu_caso(carteira, item):
        # item.filtro, item.chave_etl e outros campos do JSON estão disponíveis
        return carteira.algum_metodo_especifico(item.filtro)

    reg("resolver_meu_caso", resolver_meu_caso)
```

Chame este método no `__init__` do `ConfigDrivenBuilder`.

#### 6.2 Usar no JSON

```json
{
  "categoria": "Categoria Especial",
  "fonte": "custom",
  "nome_funcao": "resolver_meu_caso",
  "filtro": "Senior 1"
}
```

---

### ✅ Passo 7 — Fundos via API (opcional)

Para fundos cujos dados vêm de uma API externa (ex: Apex/Prisma), use `fundos_api.json`.

**Arquivo:** [`fundos_api.json`](file:///c:/Users/Nowtek/Carmel%20Capital/TECNOLOGIA%20-%20Documentos/Geral/DESENVOLVIMENTO/PYTHON/CARTEIRA/fundos_api.json)

```json
{
  "chave": "NOME_FUNDO_API",
  "nome": "Nome Completo do Fundo",
  "administrador": "Apex",
  "tipo_api": "apex",
  "doc_fundo_api": "00000000000000",
  "chave_gerencial": "NOME_FUNDO",
  "caminho_carteira": "01 - OPERACIONAL/.../ARQUIVO_CD.xlsx"
}
```

> Fundos API são carregados dinamicamente pelo `registry.py` na inicialização. Não precisam de entrada em `REGISTRO`, mas **precisam** de `config.json["arquivo_gerencial"]` e `config.json["configuracoes_fundos"]`.

---

## Checklist Final — Deploy

```
[ ] 1. config.json atualizado:
       [ ] carteiras[NOME_FUNDO] → caminho do CD
       [ ] arquivo_gerencial[NOME_FUNDO] → nome do Excel gerencial
       [ ] configuracoes_fundos[NOME_FUNDO] → lista de contas_pagar

[ ] 2. mapeamentos/NOME_FUNDO.json criado:
       [ ] Estrutura válida (fundo, administradora, mapeamento_cd, mapeamento_mec)
       [ ] Todos os campos validados pelo Pydantic (rodar o teste JSON)
       [ ] Categorias da planilha gerencial cobertas

[ ] 3. src/registry.py atualizado:
       [ ] Entrada adicionada ao dict REGISTRO
       [ ] Classe de carteira importada
       [ ] chave_config_fundo definida se necessário (chave com espaços)

[ ] 4. Testes criados:
       [ ] tests/services/test_{fundo}.py
       [ ] JSON carregável sem exceção
       [ ] Taxa de Administração populada corretamente
       [ ] Pelo menos 1 teste de CD e 1 de MEC

[ ] 5. (Se nova admin) Carteira.py:
       [ ] Classe criada com carregar_dados() e _processar_planilha()
       [ ] _popular_taxas() chamado com as colunas corretas
       [ ] _dataframes populado com as seções nomeadas

[ ] 6. (Se custom) config_driven_builder.py:
       [ ] Função registrada em _registrar_resolvers_*
       [ ] Método de registro chamado no __init__

[ ] 7. Validação:
       [ ] python -m pytest tests/services/test_{fundo}.py -v
       [ ] python -m pytest tests/ -v (suite completa — 0 failures)
       [ ] Executar o fundo manualmente e verificar o Excel gerado
```

---

## Referências Rápidas

| Arquivo | Responsabilidade |
|---------|-----------------|
| [`config.json`](file:///c:/Users/Nowtek/Carmel%20Capital/TECNOLOGIA%20-%20Documentos/Geral/DESENVOLVIMENTO/PYTHON/CARTEIRA/config.json) | Caminhos de entrada/saída e taxas esperadas |
| [`src/registry.py`](file:///c:/Users/Nowtek/Carmel%20Capital/TECNOLOGIA%20-%20Documentos/Geral/DESENVOLVIMENTO/PYTHON/CARTEIRA/src/registry.py) | Registro central de fundos |
| [`mapeamentos/`](file:///c:/Users/Nowtek/Carmel%20Capital/TECNOLOGIA%20-%20Documentos/Geral/DESENVOLVIMENTO/PYTHON/CARTEIRA/mapeamentos/) | JSONs declarativos (um por fundo) |
| [`src/config/schemas.py`](file:///c:/Users/Nowtek/Carmel%20Capital/TECNOLOGIA%20-%20Documentos/Geral/DESENVOLVIMENTO/PYTHON/CARTEIRA/src/config/schemas.py) | Schema Pydantic dos JSONs |
| [`src/services/mapping_engine.py`](file:///c:/Users/Nowtek/Carmel%20Capital/TECNOLOGIA%20-%20Documentos/Geral\DESENVOLVIMENTO/PYTHON/CARTEIRA/src/services/mapping_engine.py) | Motor que executa os mapeamentos |
| [`src/services/config_driven_builder.py`](file:///c:/Users/Nowtek/Carmel%20Capital/TECNOLOGIA%20-%20Documentos/Geral/DESENVOLVIMENTO/PYTHON/CARTEIRA/src/services/config_driven_builder.py) | Orquestra engine + resolvers custom |
| [`src/config/settings.py`](file:///c:/Users/Nowtek/Carmel%20Capital/TECNOLOGIA%20-%20Documentos/Geral/DESENVOLVIMENTO/PYTHON/CARTEIRA/src/config/settings.py) | Lê e valida config.json |
| [`Carteira.py`](file:///c:/Users/Nowtek/Carmel%20Capital/TECNOLOGIA%20-%20Documentos/Geral/DESENVOLVIMENTO/PYTHON/CARTEIRA/Carteira.py) | Classes de carteira por administradora |
| [`fundos_api.json`](file:///c:/Users/Nowtek/Carmel%20Capital/TECNOLOGIA%20-%20Documentos/Geral/DESENVOLVIMENTO/PYTHON/CARTEIRA/fundos_api.json) | Fundos via API (Apex/Prisma) |
| [`tests/services/`](file:///c:/Users/Nowtek/Carmel%20Capital/TECNOLOGIA%20-%20Documentos/Geral/DESENVOLVIMENTO/PYTHON/CARTEIRA/tests/services/) | Testes por fundo |

---

## Armadilhas Frequentes

> [!WARNING]
> **`configuracoes_fundos` faltando** → todas as taxas (Adm, Gestão, SELIC...) ficam `0.0` no relatório. A chave no JSON deve bater **exatamente** com `chave_config_fundo` (ou `chave_gerencial` se não definido).

> [!WARNING]
> **Chave com espaços** (ex: `"COBUCCIO FIDC"`) → use `chave_config_fundo="COBUCCIO FIDC"` no `ConfiguracaoFundo`. A chave no `REGISTRO` deve ser sem espaços (ex: `"COBUCCIO_FIDC"`).

> [!CAUTION]
> **`fonte: "soma_secao"`** → exige que `carteira._dataframes` contenha a chave `secao`. Verifique com `scratch/find_section_names.py` quais seções o arquivo Excel gera para a administradora.

> [!NOTE]
> **Over/NTN/LFTO (Singulare)** → use `soma_secao` com 3 itens de mesma `categoria`. O engine acumula automaticamente. Não crie funções custom para isso.

> [!TIP]
> **Coluna int vs string** → `"coluna": 5` (índice posicional) vs `"coluna": "Valor Líquido"` (nome). Use nome quando o layout pode mudar. Use índice para BRL padrão onde a coluna é estável.
