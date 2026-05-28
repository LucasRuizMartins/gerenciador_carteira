# Plano de Refatoração: Ingestão de Dados via API (MVP Apex)

## Objetivo
Criar uma arquitetura de Orientação a Objetos (POO) escalável, baseada nos princípios SOLID, para consumir dados de carteiras via API. O sistema deve manter a compatibilidade com a leitura atual de arquivos (Excel/CSV), respeitar a arquitetura Spec-Driven Development (JSONs de mapeamento) e começar com a API da Apex como Produto Mínimo Viável (MVP).

---

## Estrutura Arquitetural Proposta

Para garantir escalabilidade (Open/Closed Principle) e separação de responsabilidades (Single Responsibility Principle):

1.  **`APIClient`**: Responsável apenas por requisições HTTP e autenticação.
2.  **`CarteiraJSONBase`**: Classe base para todas as carteiras via API. Define o contrato para carregar dicionários/JSONs, herdando os atributos padrão de `CarteiraBase`.
3.  **`CarteiraApexAPI`**: Especialização (MVP) que entende o formato específico do JSON da Apex e popula os atributos e DataFrames comuns.
4.  **`MappingEngine` (Evolução)**: Opcionalmente introduzir suporte a buscas diretas em estruturas JSON, caso a conversão para DataFrame não seja ideal para certos campos.

---

## Tarefas e Passos (Roadmap MVP)

### Fase 1: Fundação OOP e Abstrações
*O objetivo desta fase é criar as fundações sem quebrar o código existente.*

- [ ] **Passo 1.1**: Criar o módulo `src/services/api_client.py`.
  - Implementar uma classe base para requests HTTP com tratamento de erros.
- [ ] **Passo 1.2**: Criar `CarteiraJSONBase` em `Carteira.py` (ou em um novo módulo).
  - Herdar de `CarteiraBase` para manter a assinatura dos atributos (PL, PDD, taxas).
  - Implementar o método `carregar_dados()` para aceitar um payload JSON (dicionário).

### Fase 2: Implementação do MVP (Apex Group)
*Focando na primeira administradora.*

- [ ] **Passo 2.1**: Criar a classe `CarteiraApexAPI`.
  - Herdar de `CarteiraJSONBase`.
- [ ] **Passo 2.2**: Implementar o Parser de Atributos.
  - Extrair PL, PDD, Tesouraria, Direitos Creditórios usando a lógica de cálculo validada (ex: `PL = Ativos - Passivos`).
- [ ] **Passo 2.3**: Implementar o Adapter de DataFrames (Bridge).
  - Para manter compatibilidade com o `MappingEngine` existente, converter blocos do JSON (ex: `valoresPagar.valoresPorHistorico`) em DataFrames compatíveis (`df_contas_filtrado`), permitindo que a especificação atual (`fontes: contas`) continue funcionando sem alterações profundas.

### Fase 3: Evolução Spec-Driven (MappingEngine)
*Ajustes finos no motor de mapeamento.*

- [ ] **Passo 3.1**: Adaptar o `MappingEngine`.
  - Se necessário, criar o resolver `json_path` em `src/services/mapping_engine.py` para acessar dados profundamente aninhados.
- [ ] **Passo 3.2**: Criar o arquivo de mapeamento teste (`mapeamentos/VIRTUS_API.json`).
  - Utilizar a nova especificação apontando para a `CarteiraApexAPI`.

### Fase 4: Integração com o Registry
*Conectando a nova engine ao fluxo principal.*

- [ ] **Passo 4.1**: Atualizar `src/registry.py`.
  - Configurar a entrada do fundo "VIRTUS" (ou uma cópia de teste) para instanciar `CarteiraApexAPI` em vez de `CarteiraBRL`.
- [ ] **Passo 4.2**: Gerenciar Parâmetros e Credenciais.
  - Atualizar `config.json` e `.env` com endpoints e credenciais da API da Apex.

### Fase 5: Testes e Validação
*Garantindo a estabilidade e a corretude.*

- [ ] **Passo 5.1**: Testes Unitários.
  - Mockar o JSON da Apex e garantir que a `CarteiraApexAPI` popula os atributos corretamente.
- [ ] **Passo 5.2**: Teste de Integração (Ponta-a-ponta).
  - Executar a geração do relatório Excel para o fundo Virtus usando o payload JSON e comparar com o relatório gerado pela planilha original.

---
*Escopo definido para a implementação da Feature de Ingestão de API.*
