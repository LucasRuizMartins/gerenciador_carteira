# Documentação de Testes e Qualidade (QA)

Este documento descreve a estratégia de testes, a arquitetura da suíte de testes e as melhores práticas de QA aplicadas ao projeto de Gerenciamento de Carteiras.

## 🎯 Filosofia de QA

Seguimos o princípio da **Pirâmide de Testes**, priorizando testes unitários rápidos e isolados, complementados por testes de integração que validam o fluxo completo.

### Princípios Aplicados (F.I.R.S.T)
- **Fast (Rápido):** Os testes rodam em menos de 2 segundos, permitindo feedback instantâneo.
- **Independent (Independente):** Um teste não depende do resultado de outro. O estado é resetado em cada execução.
- **Repeatable (Repetível):** Resultados idênticos em qualquer máquina (Windows/Linux/CI).
- **Self-Validating (Auto-validável):** O teste falha ou passa de forma clara, sem necessidade de interpretação manual de logs.
- **Timely (Oportuno):** Cobertura de 100% nas funções críticas de conversão.

---

## 🏗️ Arquitetura dos Testes

A estrutura de testes está localizada no diretório `/tests` e espelha a estrutura do código-fonte (`/src`).

### 1. Testes Unitários (`tests/core` e `tests/services`)
Focam em componentes isolados.
- **Módulos Puros:** Testamos exaustivamente o `src/core/converters.py` para garantir que o parsing de valores monetários e datas seja infalível.
- **Mocks & Patches:** Utilizamos a biblioteca `unittest.mock` para simular dependências externas.
    - **Mock de Classes:** Criamos a `MockCarteira` em `tests/services/test_report_builder.py` para injetar dados falsos nos `ReportBuilders`. Isso permite testar a lógica de geração de relatórios sem precisar de arquivos Excel em disco.

### 2. Testes de Integração (`tests/integration`)
Validam a comunicação entre diferentes partes do sistema.
- **DataFrames Sintéticos:** Em vez de depender de arquivos `.xlsx` reais que podem mudar de local ou conteúdo, o teste de integração gera um `pd.DataFrame` em memória que imita a estrutura de uma administradora.
- **Registry & Registry Injection:** Validamos se o sistema de registro (`src/registry.py`) consegue instanciar corretamente a classe de carteira e o builder apropriado.

---

## 🛠️ Como Executar os Testes

### Pré-requisitos
Certifique-se de que as dependências de desenvolvimento estão instaladas:
```powershell
pip install pytest pytest-cov
```

### Execução Completa
Para rodar todos os testes com relatório de cobertura no terminal:
```powershell
python -m pytest tests/ --cov=src --cov-report=term-missing
```

### Execução por Módulo
Se estiver trabalhando em um módulo específico:
```powershell
python -m pytest tests/core/test_converters.py
```

---

## 📊 Cobertura (Code Coverage)

Nossa meta é manter as funções puras com **100% de cobertura**.
- **Coverage Atual:** 
    - `src/core/converters.py`: 100%
    - `src/services/excel_writer.py`: ~50% (foco em I/O)
    - `src/registry.py`: Validado via integração.

---

## 🚀 Integração Contínua (CI/CD)

Configuramos o **GitHub Actions** (`.github/workflows/python-tests.yml`) para garantir a qualidade em cada contribuição:
1. **Trigger:** Ativado em cada `push` ou `pull_request` para as branches `main` e `master`.
2. **Ambiente:** Roda em `windows-latest` para máxima compatibilidade com o ambiente de produção.
3. **Check:** O pipeline falha se qualquer teste falhar ou se a sintaxe Python estiver incorreta.

---

## 📝 Guia para Novos Desenvolvedores

Ao adicionar um novo fundo ao sistema:
1. **Adicione ao Registro:** Inclua a configuração em `src/registry.py`.
2. **Crie o Builder:** Implemente a lógica em `src/services/report_builder.py`.
3. **Crie o Teste:** 
   - Abra `tests/services/test_report_builder.py`.
   - Adicione uma nova classe `TestNovoFundoReportBuilder`.
   - Use a `MockCarteira` para validar se o mapeamento gerado contém as chaves e valores esperados.

---
> Documentação gerada seguindo os padrões de excelência em Engenharia de Software e QA.
