"""Exemplo de uso do pacote apex."""
from datetime import date
from apex import ApexAPI, ExtratoParams

# 1. Configurações (normalmente vindas de .env ou arquivo seguro)
cfg = {
    "base_url_apex_dev": "https://a8pl78rvme.execute-api.sa-east-1.amazonaws.com/dev",
    "clientId": "SEU_CLIENT_ID",
    "clientSecret": "SEU_CLIENT_SECRET",
    "x_api": "SUA_X_API_KEY",
}

# 2. Instancia UMA vez — o token é gerenciado automaticamente
api = ApexAPI.from_config(cfg)

# 3. Chama o serviço desejado
params = ExtratoParams(
    doc_fundo="12345678000199",
    dt_inicio=date(2024, 1, 1),
    dt_fim=date(2024, 1, 31),
)

dados = api.relatorios.get_extrato(params)
print(dados)
