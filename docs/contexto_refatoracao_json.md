# Contexto de Refatoração: Excel para API/JSON

Este documento consolida o entendimento da arquitetura atual do Sistema de Carteiras da Carmel Capital e as premissas para a transição do processo de ETL de planilhas para consumo de dados via API/JSON (Apex Group).

## 1. Visão Geral da Arquitetura Atual

O sistema opera como um pipeline de ETL modular, projetado para lidar com a heterogeneidade das planilhas de administradoras.

### Fluxo de Dados Atual
1.  **Ingestão (EL)**: Classes em `Carteira.py` (ex: `CarteiraBRL`, `CarteiraAVANTI`) utilizam `pandas` e engines específicas (`pyxlsb`, `openpyxl`) para ler arquivos físicos.
2.  **Extração de Atributos**: O parser localiza seções dinâmicas (ex: "Valores a Pagar") e popula atributos da classe base (`CarteiraBase`) e DataFrames internos.
3.  **Mapeamento (T)**: O `ConfigDrivenBuilder` lê um arquivo de especificação JSON em `mapeamentos/` e usa o `MappingEngine` para traduzir os dados brutos da "Carteira" para o formato do relatório gerencial.
4.  **Carga (L)**: O `ExcelWriter` (via `xlwings`) escreve os dados nos arquivos `.xlsb` gerenciais.

## 2. Componentes Chave

| Componente | Responsabilidade |
| :--- | :--- |
| `src/registry.py` | Registro centralizado que associa cada fundo a uma classe de carteira e um builder (especificação). |
| `src/services/config_driven_builder.py` | Implementa o **Spec-Driven Development**, eliminando lógica hardcoded em Python a favor de definições JSON. |
| `src/services/mapping_engine.py` | Motor que resolve as regras definidas nos JSONs de mapeamento contra os dados carregados na memória. |
| `mapeamentos/*.json` | As "specs" que definem como cada campo do input deve ser transformado para o output. |
| `Carteira.py` | Contém a lógica de parsing de planilhas (o componente que será majoritariamente substituído/complementado). |

## 3. O Caso "CarteiraApex" (BRL Trust)

Os fundos administrados pela Apex Group atualmente utilizam a classe `CarteiraBRL`. 
- **Desafio Atual**: Dependência de marcadores de texto em planilhas (ex: `"VALORES A LIQUIDAR"`, `"RESUMO DA CARTEIRA"`). Mudanças mínimas no layout da administradora quebram o parser.
- **Vantagem da Refatoração**: Ao migrar para JSON/API, eliminamos a fragilidade do parsing visual (coordenadas de células e nomes de abas) por uma estrutura de dados consistente.

## 4. Premissas para a Refatoração JSON

A transição seguirá os princípios de **Spec-Driven Development**:

1.  **Imutabilidade da Lógica Core**: O `MappingEngine` e o `ExcelWriter` não devem sofrer alterações drásticas; eles continuarão consumindo um objeto que forneça os dados.
2.  **Novo Ingestor**: Criaremos uma nova classe de "Carteira" (ex: `CarteiraApexJSON`) que, em vez de ler Excel, fará o parsing do JSON da API da Apex para popular os mesmos atributos/DataFrames esperados pelo motor de mapeamento.
3.  **Mapeamento Unificado**: Os arquivos em `mapeamentos/` poderão ser atualizados para apontar para chaves do JSON da API em vez de índices de colunas do Excel.
4.  **Paridade de Dados**: Garantir que as métricas calculadas via API (PDD, Patrimônio, Cotas) batam com as lógicas históricas extraídas das planilhas.

## 5. Próximos Passos

1.  **Análise do Schema JSON**: Avaliar a estrutura do arquivo enviado pela Apex.
2.  **Protótipo de Parser**: Implementar a extração dos campos principais (PL, Tesouraria, Direitos Creditórios) para o novo formato.
3.  **Validação de Spec**: Atualizar ou criar um novo arquivo de mapeamento em `mapeamentos/` que utilize o JSON como fonte primária.

## 6. Mapeamento API Virtus (Análise Preliminar)

Após analisar o JSON da API fornecido para o fundo Virtus, foram estabelecidas as seguintes relações com os campos exigidos pelo relatório gerencial:

### 6.1 Atributos e Métricas Principais

| Campo Gerencial | Caminho no JSON API | Valor no Exemplo |
| :--- | :--- | :--- |
| **Direitos Creditórios a Vencer** | `posicaoOutros.posicaoDC.posicoes` (papel: "A VENCER") → `valorPresente` | 14.211.446,25 |
| **Direitos Creditórios Vencidos** | `posicaoOutros.posicaoDC.posicoes` (papel: "VENCIDO") → `valorPresente` | 104.954,34 |
| **PDD - Prov. de Perdas** | `posicaoOutros.posicaoPDD.total.totalValorTotal` | -11.645,04 |
| **Saldo em Tesouraria** | `posicaoCaixa.total.totalValorTotal` | 0,00 |
| **FI BRL2314 (Valor DI)** | `posicaoCotas.posicoesPorTipoFundo` (papel contém "BRL2314") → `valorTotal` | 47.657,61 |
| **Cota Sênior (Valor Total)** | `posicaoCotaSuperior.posicoes` (ordem: 99) → `valorTotal` | 5.816.351,43 |
| **Cota Mezanino (Valor Total)** | `posicaoCotaSuperior.posicoes` (ordem: 98) → `valorTotal` | 1.702.875,88 |

### 6.2 Taxas e Despesas (valoresPagar)

As taxas são resolvidas buscando pelo `nome` dentro da lista `valoresPagar.valoresPorHistorico`.

| Taxa / Despesa | Nome no JSON API | Valor Total |
| :--- | :--- | :--- |
| **Taxa de Administração** | `"DESPESA COM TAXA DE ADMINISTRAÇÃO"` ou `"TAXA DE ADMINISTRAÇÃO"` | -29.000,00 (soma) |
| **Taxa de Gestão** | `"TAXA DE GESTÃO"` | -16.666,60 |
| **Taxa de Auditoria** | `"DESPESA DE AUDITORIA"` | -20.000,00 |
| **Taxa Consultoria** | `"TAXA DE CONSULTORIA"` | -19.393,09 |
| **Taxa ANBIMA** | `"TAXA ANBIMA"` | -163,00 |
| **Taxa CVM** | `"TAXA CVM"` | -942,81 |

### 6.3 Valores a Receber (valoresReceber)

| Categoria | Nome no JSON API | Valor Total |
| :--- | :--- | :--- |
| **Outros Recebíveis** | `"RECEBÍVEIS (CRÉDITO)"` | 167.889,32 |
| **Diferimento ANBIMA** | `"TAXA ANBIMA"` | 342,76 |

### 6.4 Campos Não Identificados / Pendentes

Não foi possível estabelecer uma relação direta para os seguintes campos no snippet fornecido:

1.  **Data-Base**: Não foi encontrado um campo de data de referência global (ex: `dataPosicao`) no nível raiz do JSON enviado.
2.  **Patrimônio Líquido Total**: Embora existam campos de `percentualPL`, o valor nominal do PL Total do fundo não aparece explicitamente rotulado.
3.  **Cota Subordinada (Quantidade/Preço)**: A seção `posicaoCotaSuperior` lista apenas as ordens 98 (Mez) e 99 (Sr). Os dados da cota Subordinada não foram localizados nesta seção.
4.  **Taxa de Custódia**: Não aparece como um item separado na lista de `valoresPagar` neste exemplo.

---
*Documento atualizado com mapeamento da API Virtus - Maio 2026.*
