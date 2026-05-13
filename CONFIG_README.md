# Documentação do config.json

Este arquivo centraliza a configuração dos fundos e caminhos do sistema.

## Estrutura do Arquivo

### `paths` (Caminhos Base)
*   `relatorio_diario`: Caminho (relativo à raiz do OneDrive) onde os relatórios gerenciais (.xlsb) são salvos.
*   `estoque`: Caminho das lâminas de estoque.
*   `feriados`: Caminho para o arquivo Excel de feriados.
*   *Nota: O `root_dir` (raiz do OneDrive) agora deve ser configurado no arquivo `.env` para maior segurança.*

### `arquivo_gerencial`
Mapeia a sigla do fundo para o nome exato do arquivo Excel Gerencial.
Exemplo: `"FIDARA": "FIDARA FIDC.xlsb"`

### `carteiras`
Mapeia a sigla do fundo para o caminho relativo do arquivo de Carteira Diária fornecido pela administradora.

### `configuracoes_fundos`
Contém regras de negócio específicas para o processamento de cada fundo.
*   `contas_pagar`: Lista de palavras-chave usadas para identificar despesas no extrato (ex: "Gestão", "Auditoria").

### `destinatarios`
Lista de e-mails para os quais o sistema pode enviar notificações (funcionalidade futura).

## Validação
O sistema utiliza **Pydantic** para validar este arquivo na inicialização. Se algum campo obrigatório estiver faltando ou se o JSON estiver malformado, o sistema emitirá um erro claro e interromperá a execução para evitar dados corrompidos.
