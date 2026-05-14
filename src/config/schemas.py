"""
Schemas Pydantic para validação de mapeamentos declarativos.

Cada arquivo JSON em `mapeamentos/*.json` segue o schema definido aqui.
A validação garante que o JSON seja consistente antes de ser processado
pelo MappingEngine, prevenindo erros em tempo de execução.

Exemplo de JSON válido:
    {
        "versao": "1.0",
        "fundo": "ZULU",
        "administradora": "BRL",
        "mapeamento_cd": [
            {
                "categoria": "Data-Base",
                "fonte": "atributo",
                "campo": "data"
            },
            {
                "categoria": "Saldo em Tesouraria",
                "fonte": "atributo",
                "campo": "saldo_tesouraria"
            },
            {
                "categoria": "Senior (-)",
                "fonte": "fixo",
                "valor_fixo": 0
            },
            {
                "categoria": "GV Cash",
                "fonte": "valor_carteira",
                "chave_etl": "GV CASH RENDA FIXA...",
                "coluna": 5
            }
        ],
        "mapeamento_mec": [...]
    }
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator


# ---------------------------------------------------------------------------
# Tipos de fonte suportados pelo MappingEngine
# ---------------------------------------------------------------------------

FonteTipo = Literal[
    "atributo",       # Lê atributo direto do objeto carteira (ex: carteira.data)
    "valor_carteira", # Chama carteira.recuperar_valor_carteira(chave, coluna)
    "cotas",          # Busca valor em df_cotas_superiores via obter_valor_ordem()
    "taxa",           # Lê atributo de taxa do objeto carteira
    "contas",         # Chama carteira.recuperar_contas(filtro, df)
    "fixo",           # Valor constante definido no JSON
    "custom",         # Delega para função Python registrada no engine
]

FonteDF = Literal[
    "df_contas_filtrado",          # Contas a pagar processadas
    "df_contas_receber_filtrado",  # Contas a receber processadas
]

AgregacaoTipo = Literal["soma", "primeiro"]


# ---------------------------------------------------------------------------
# Schema de um item de mapeamento
# ---------------------------------------------------------------------------

class ItemMapeamento(BaseModel):
    """Representa uma linha do mapeamento declarativo.

    Cada item define COMO obter um valor da carteira e em qual
    categoria do relatório ele deve ser gravado.

    Campos obrigatórios:
        categoria: Nome da coluna no arquivo de relatório (Excel gerencial).
        fonte: Estratégia de resolução do valor.

    Campos condicionais por fonte:
        - "atributo"       → campo (ex: "data", "patrimonio_total")
        - "valor_carteira" → chave_etl + coluna
        - "cotas"          → ordens + coluna_valor (+ opcional: agregacao, multiplicador)
        - "taxa"           → campo (ex: "valor_administracao")
        - "contas"         → filtro + dataframe
        - "fixo"           → valor_fixo
        - "custom"         → nome_funcao
    """

    categoria: str = Field(
        description="Nome da categoria/coluna no relatório de destino."
    )
    fonte: FonteTipo = Field(
        description="Estratégia de resolução do valor."
    )

    # --- Campos para fonte="atributo" ou fonte="taxa" ---
    campo: str | None = Field(
        default=None,
        description=(
            "Nome do atributo no objeto carteira. "
            "Exemplos: 'data', 'patrimonio_total', 'valor_administracao'."
        ),
    )

    # --- Campos para fonte="valor_carteira" ---
    chave_etl: str | None = Field(
        default=None,
        description=(
            "Texto identificador da linha na planilha da administradora. "
            "Exemplo: 'FIDC BRL2954 - RESIDENCE CLUB FIDC : ... - SR 03'."
        ),
    )
    coluna: int | None = Field(
        default=None,
        description="Índice numérico da coluna de valor (0-based) na planilha.",
    )

    # --- Campos para fonte="cotas" ---
    ordens: list[int] | None = Field(
        default=None,
        description=(
            "Lista de valores da coluna 'Ordem' em df_cotas_superiores. "
            "Exemplo: [99, 98, 97] para somar 3 cotas sênior."
        ),
    )
    coluna_valor: str | None = Field(
        default=None,
        description=(
            "Nome da coluna no df_cotas a extrair. "
            "Exemplos: 'Valor Total', 'Qtde. Total', 'Valor Cota'."
        ),
    )
    agregacao: AgregacaoTipo = Field(
        default="primeiro",
        description=(
            "'soma' para somar múltiplas ordens; "
            "'primeiro' para retornar apenas a primeira. "
            "Padrão: 'primeiro'."
        ),
    )

    # --- Campo para fonte="contas" ---
    filtro: str | None = Field(
        default=None,
        description=(
            "Texto de filtro passado para recuperar_contas(). "
            "Exemplos: 'Anbima', 'Cvm', 'Contas a pagar', 'Consultoria'."
        ),
    )
    dataframe: FonteDF | None = Field(
        default=None,
        description=(
            "Qual DataFrame de contas usar. "
            "Padrão: 'df_contas_filtrado' (contas a pagar). "
            "Use 'df_contas_receber_filtrado' para diferimentos."
        ),
    )

    # --- Campo para fonte="fixo" ---
    valor_fixo: Any | None = Field(
        default=None,
        description="Valor constante a inserir (ex: 0, 0.5, 0.1).",
    )

    # --- Campo para fonte="custom" ---
    nome_funcao: str | None = Field(
        default=None,
        description=(
            "Nome da função Python registrada no MappingEngine via "
            "register_custom_resolver(). Para lógica não-declarativa."
        ),
    )

    # --- Modificadores universais ---
    multiplicador: float = Field(
        default=1.0,
        description=(
            "Multiplicador aplicado sobre o valor resolvido. "
            "Use -1 para inverter sinal (ex: cotas sênior que são passivo)."
        ),
    )

    # --- Validação de consistência ---

    @model_validator(mode="after")
    def validar_campos_obrigatorios_por_fonte(self) -> "ItemMapeamento":
        """Garante que os campos necessários para cada fonte estejam presentes."""
        erros = []

        if self.fonte == "atributo" and not self.campo:
            erros.append("fonte='atributo' requer o campo 'campo'.")

        if self.fonte == "taxa" and not self.campo:
            erros.append("fonte='taxa' requer o campo 'campo'.")

        if self.fonte == "valor_carteira":
            if not self.chave_etl:
                erros.append("fonte='valor_carteira' requer 'chave_etl'.")
            if self.coluna is None:
                erros.append("fonte='valor_carteira' requer 'coluna'.")

        if self.fonte == "cotas":
            if not self.ordens:
                erros.append("fonte='cotas' requer 'ordens' (lista de inteiros).")
            if not self.coluna_valor:
                erros.append("fonte='cotas' requer 'coluna_valor'.")

        if self.fonte == "contas":
            if not self.filtro:
                erros.append("fonte='contas' requer 'filtro'.")

        if self.fonte == "fixo" and self.valor_fixo is None:
            erros.append("fonte='fixo' requer 'valor_fixo'.")

        if self.fonte == "custom" and not self.nome_funcao:
            erros.append("fonte='custom' requer 'nome_funcao'.")

        if erros:
            raise ValueError(
                f"Mapeamento inválido para categoria '{self.categoria}': "
                + " | ".join(erros)
            )

        return self


# ---------------------------------------------------------------------------
# Schema do arquivo completo de mapeamento
# ---------------------------------------------------------------------------

class MapeamentoFundo(BaseModel):
    """Schema do arquivo JSON completo de mapeamento de um fundo.

    Representa o conteúdo de `mapeamentos/{FUNDO}.json`.
    """

    versao: str = Field(
        default="1.0",
        description="Versão do schema do arquivo (controle de compatibilidade).",
    )
    fundo: str = Field(
        description="Chave do fundo conforme definida no REGISTRO (ex: 'CDC', 'FIDARA')."
    )
    administradora: str = Field(
        description="Nome da administradora (ex: 'BRL', 'Genial', 'Avanti')."
    )
    mapeamento_cd: list[ItemMapeamento] = Field(
        description="Lista de itens para a aba CD (Carteira Diária)."
    )
    mapeamento_mec: list[ItemMapeamento] = Field(
        description="Lista de itens para a aba MEC (Movimentação e Cota)."
    )

    @model_validator(mode="after")
    def validar_categorias_unicas(self) -> "MapeamentoFundo":
        """Alerta sobre categorias duplicadas dentro de cada aba."""
        for aba, itens in [("CD", self.mapeamento_cd), ("MEC", self.mapeamento_mec)]:
            categorias = [item.categoria for item in itens]
            vistos: set[str] = set()
            duplicados = []
            for c in categorias:
                if c in vistos:
                    duplicados.append(c)
                vistos.add(c)
            if duplicados:
                raise ValueError(
                    f"Aba {aba} do fundo '{self.fundo}' possui categorias duplicadas: "
                    f"{duplicados}"
                )
        return self
