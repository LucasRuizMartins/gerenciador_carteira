"""
Motor de resolução de mapeamentos declarativos.

O MappingEngine é o coração da Fase 1 do projeto de refatoração.
Ele interpreta listas de ItemMapeamento (lidas de JSON) e resolve
cada item contra um objeto carteira já carregado, retornando a lista
de dicionários {Categoria, Valor} que o ExcelWriter consome.

Design:
    - Cada "fonte" é implementada como um método _resolver_* privado.
    - Novos tipos de fonte podem ser adicionados sem alterar consumidores.
    - Funções custom são registradas explicitamente via register_custom_resolver().
    - Completamente testável com mocks simples.

Fontes suportadas:
    "atributo"       → lê atributo direto do objeto carteira
    "valor_carteira" → chama carteira.recuperar_valor_carteira(chave, coluna)
    "cotas"          → busca em df_cotas_superiores via obter_valor_ordem()
    "taxa"           → lê atributo de taxa do objeto carteira
    "contas"         → chama carteira.recuperar_contas(filtro, df)
    "fixo"           → valor constante definido no JSON
    "custom"         → delega para função Python registrada

Uso:
    from src.services.mapping_engine import MappingEngine
    from src.config.schemas import ItemMapeamento

    engine = MappingEngine()
    mapeamento_json = [
        ItemMapeamento(categoria="Data-Base", fonte="atributo", campo="data"),
        ItemMapeamento(categoria="PL", fonte="atributo", campo="patrimonio_total"),
    ]
    resultado = engine.resolver(carteira, mapeamento_json)
    # → [{"Categoria": "Data-Base", "Valor": ...}, {"Categoria": "PL", "Valor": ...}]
"""

from __future__ import annotations

from typing import Any, Callable
from src.core.logger import get_logger
from carteira_apex import obter_valor_ordem  # compatibilidade — migrar para src.core.converters na Fase 4

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Tipo auxiliar
# ---------------------------------------------------------------------------

MapeamentoExcel = list[dict[str, Any]]

# Assinatura esperada para resolvers custom:
#   def minha_funcao(carteira, item: ItemMapeamento) -> Any
CustomResolver = Callable[["Any", "Any"], Any]


# ---------------------------------------------------------------------------
# MappingEngine
# ---------------------------------------------------------------------------

class MappingEngine:
    """Resolve mapeamentos declarativos contra um objeto carteira.

    Interpreta cada ItemMapeamento e extrai o valor correspondente
    do objeto carteira, aplicando o multiplicador e retornando
    a lista final no formato que o ExcelWriter espera.

    Attributes:
        _custom_resolvers: Registro de funções Python para fonte="custom".
    """

    def __init__(self) -> None:
        self._custom_resolvers: dict[str, CustomResolver] = {}

    # ------------------------------------------------------------------
    # API pública
    # ------------------------------------------------------------------

    def resolver(self, carteira: Any, itens: list) -> MapeamentoExcel:
        """Resolve uma lista de ItemMapeamento contra a carteira.
        
        Se houver múltiplas regras para a mesma Categoria, os valores são SOMADOS.
        """
        # Inicializa lista de warnings na carteira caso não exista
        if not hasattr(carteira, "warnings"):
            carteira.warnings = []

        # Dicionário temporário para acumular somas por categoria
        acumulador: dict[str, float] = {}
        
        for item in itens:
            try:
                valor = self._resolver_item(carteira, item)
                
                # Registra aviso se o campo for nulo/zero para fontes que deveriam conter dados
                if (valor is None or valor == 0.0) and item.fonte in ["api_json", "contas", "valor_carteira", "atributo", "taxa"]:
                    msg = f"Campo '{item.categoria}' não foi recuperado (retornou {valor}) usando a fonte '{item.fonte}'."
                    if msg not in carteira.warnings:
                        carteira.warnings.append(msg)

                # Aplica multiplicador
                if isinstance(valor, (int, float)) and item.multiplicador != 1.0:
                    valor = valor * item.multiplicador
                
                # Acumula o valor (garante que seja numérico para soma)
                cat = item.categoria
                try:
                    num_valor = float(valor)
                except (ValueError, TypeError):
                    num_valor = 0.0 if valor is None else valor # Mantém original se não for número (ex: strings)

                if isinstance(num_valor, (int, float)):
                    acumulador[cat] = acumulador.get(cat, 0.0) + num_valor
                else:
                    # Se for string (ex: Data-Base), apenas atribui (último vence)
                    acumulador[cat] = valor
                    
            except Exception as exc:
                logger.error(f"Erro ao resolver item '{item.categoria}': {exc}")
                msg = f"Erro crítico ao resolver campo '{item.categoria}': {exc}"
                if msg not in carteira.warnings:
                    carteira.warnings.append(msg)
                if item.categoria not in acumulador:
                    acumulador[item.categoria] = 0.0

        # Converte o dicionário de volta para a lista [{"Categoria": ..., "Valor": ...}]
        return [{"Categoria": cat, "Valor": val} for cat, val in acumulador.items()]

    def register_custom_resolver(self, nome: str, funcao: CustomResolver) -> None:
        """Registra uma função Python para ser usada com fonte='custom'.

        Args:
            nome: Identificador da função (deve coincidir com 'nome_funcao' no JSON).
            funcao: Callable com assinatura (carteira, item) -> Any.

        Exemplo:
            def calcular_avanti_especial(carteira, item):
                return carteira.dataframe.iloc[5, 38]

            engine.register_custom_resolver("calcular_avanti_especial", calcular_avanti_especial)
        """
        self._custom_resolvers[nome] = funcao
        logger.info(f"Resolver custom registrado: '{nome}'")

    # ------------------------------------------------------------------
    # Dispatcher
    # ------------------------------------------------------------------

    def _resolver_item(self, carteira: Any, item: Any) -> Any:
        """Despacha para o resolver correto baseado em item.fonte."""
        dispatch = {
            "atributo":       self._resolver_atributo,
            "valor_carteira": self._resolver_valor_carteira,
            "cotas":          self._resolver_cotas,
            "taxa":           self._resolver_taxa,
            "contas":         self._resolver_contas,
            "fixo":           self._resolver_fixo,
            "custom":         self._resolver_custom,
            "api_json":       self._resolver_api_json,
        }
        resolver_fn = dispatch.get(item.fonte)
        if resolver_fn is None:
            raise ValueError(f"Fonte desconhecida: '{item.fonte}'")
        return resolver_fn(carteira, item)

    # ------------------------------------------------------------------
    # Resolvers individuais
    # ------------------------------------------------------------------

    def _resolver_atributo(self, carteira: Any, item: Any) -> Any:
        """Lê um atributo direto do objeto carteira.

        Exemplos de campo: "data", "patrimonio_total", "saldo_tesouraria",
        "a_vencer", "vencido", "pdd", "valor_di".
        """
        valor = getattr(carteira, item.campo, None)
        if valor is None:
            logger.info(
                f"Atributo '{item.campo}' não encontrado na carteira. Retornando 0.0."
            )
            return 0.0
        return valor

    def _resolver_taxa(self, carteira: Any, item: Any) -> Any:
        """Lê um atributo de taxa do objeto carteira.

        Internamente idêntico a _resolver_atributo — separado por semântica
        e para facilitar futuras extensões (ex: conversão de sinal padrão).

        Exemplos de campo: "valor_administracao", "valor_taxa_gestao",
        "valor_taxa_cvm", "valor_anbima", "valor_taxa_auditoria",
        "valor_taxa_custodia", "valor_taxa_performance",
        "valor_selic", "valor_cetip", "valor_liq_banco".
        """
        valor = getattr(carteira, item.campo, None)
        if valor is None:
            logger.info(
                f"Taxa '{item.campo}' não encontrada na carteira. Retornando 0.0."
            )
            return 0.0
        return valor

    def _resolver_valor_carteira(self, carteira: Any, item: Any) -> float:
        """Chama carteira.recuperar_valor_carteira(chave_etl, coluna).

        Usado para buscar ativos específicos pelo texto identificador na
        planilha da administradora e pelo índice numérico da coluna de valor.

        Se o valor retornado for uma string no formato brasileiro (ex: "1,234567"),
        aplica conversão automática via limpar_valor_monetario.

        Exemplo:
            chave_etl: "GV CASH RENDA FIXA REFERENCIADO DI LONGO PRAZO..."
            coluna: 5
        """
        from src.core.converters import limpar_valor_monetario
        try:
            valor = carteira.recuperar_valor_carteira(item.chave_etl, item.coluna)
            return limpar_valor_monetario(valor)
        except Exception as exc:
            logger.info(
                f"valor_carteira: '{item.chave_etl}' col={item.coluna} → {exc}"
            )
            return 0.0

    def _resolver_cotas(self, carteira: Any, item: Any) -> float:
        """Busca valor em df_cotas_superiores usando a coluna 'Ordem'.

        Importa obter_valor_ordem de src.core.converters (migrado de carteira_apex).
        Se 'agregacao' for 'soma', soma o resultado de todas as ordens.
        Se for 'primeiro', retorna apenas o da primeira ordem da lista.

        Exemplo:
            ordens: [99, 98, 97]
            coluna_valor: "Valor Total"
            agregacao: "soma"
            → obter_valor_ordem(df, 99, "Valor Total")
              + obter_valor_ordem(df, 98, "Valor Total")
              + obter_valor_ordem(df, 97, "Valor Total")
        """
        df_cotas = getattr(carteira, "df_cotas_superiores", None)
        if df_cotas is None or df_cotas.empty:
            logger.info(
                f"df_cotas_superiores vazio ou inexistente para '{item.categoria}'."
            )
            return 0.0

        # Por padrão, soma se houver uma lista. Só retorna o primeiro se explicitamente pedido.
        agregacao = getattr(item, "agregacao", "soma") or "soma"
        
        if agregacao == "soma":
            return sum(
                obter_valor_ordem(df_cotas, ordem, item.coluna_valor)
                for ordem in item.ordens
            )
        else:  # "primeiro"
            return obter_valor_ordem(df_cotas, item.ordens[0], item.coluna_valor)

    def _resolver_contas(self, carteira: Any, item: Any) -> float:
        """Chama carteira.recuperar_contas(filtro, df).

        Resolve valores de taxas/despesas a partir dos DataFrames
        de contas a pagar ou receber já processados.

        dataframe pode ser:
            "df_contas_filtrado"         → contas a pagar (padrão)
            "df_contas_receber_filtrado" → contas a receber / diferimentos
        """
        nome_df = item.dataframe or "df_contas_filtrado"
        df = getattr(carteira, nome_df, None)

        if df is None or df.empty:
            return 0.0

        try:
            return float(carteira.recuperar_contas(item.filtro, df))
        except Exception as exc:
            logger.info(
                f"contas: filtro='{item.filtro}' df='{nome_df}' → {exc}"
            )
            return 0.0

    def _resolver_fixo(self, carteira: Any, item: Any) -> Any:
        """Retorna o valor constante definido no JSON.

        Usado para zeros estruturais, constantes financeiras
        (ex: subordinação mínima = 0.5) ou valores placeholder.
        """
        return item.valor_fixo

    def _resolver_custom(self, carteira: Any, item: Any) -> Any:
        """Delega para função Python registrada via register_custom_resolver().

        Usado para lógica que não pode ser expressada de forma declarativa
        (ex: cálculos do Avanti que percorrem intervalos de colunas,
        SB II que lê arquivo externo de códigos).
        """
        nome = item.nome_funcao
        if nome not in self._custom_resolvers:
            raise ValueError(
                f"Resolver custom '{nome}' não registrado. "
                f"Use engine.register_custom_resolver('{nome}', sua_funcao)."
            )
        return self._custom_resolvers[nome](carteira, item)

    def _resolver_api_json(self, carteira: Any, item: Any) -> Any:
        """Extrai um valor do JSON da API (carteira.raw_data) usando caminho de pontos e filtros.

        Suporta notação de ponto para caminhos aninhados e busca com filtros em listas de objetos.
        Agora também suporta atravessar listas intermediárias (ex: posicaoCotas...posicoes) de forma transparente.
        """
        raw_data = getattr(carteira, "raw_data", None)
        if not raw_data:
            logger.warning(f"Objeto carteira não possui raw_data para resolver {item.categoria}.")
            return 0.0

        # O ponto de partida é raw_data["data"] se existir, senão raw_data
        val = raw_data.get("data", raw_data) if isinstance(raw_data, dict) else raw_data
        
        keys = item.caminho_json.split(".")
        
        for key in keys:
            if key == "data" and val is raw_data.get("data"):
                continue # ignora o primeiro "data." se já estamos dentro dele
            
            if isinstance(val, list):
                # Achata (flatten) as chaves de todos os dicionários na lista
                nova_val = []
                for elem in val:
                    if isinstance(elem, dict) and key in elem:
                        item_val = elem[key]
                        if isinstance(item_val, list):
                            nova_val.extend(item_val)
                        else:
                            nova_val.append(item_val)
                val = nova_val
            elif isinstance(val, dict):
                if key in val:
                    val = val[key]
                else:
                    logger.info(f"Caminho JSON '{item.caminho_json}' (chave '{key}') não encontrado para {item.categoria}.")
                    return 0.0
            else:
                return 0.0

        # Se val for uma lista e filtros foram definidos
        if isinstance(val, list) and item.chave_filtro_json and item.valor_filtro_json:
            for elem in val:
                if isinstance(elem, dict) and str(elem.get(item.chave_filtro_json)).upper() == str(item.valor_filtro_json).upper():
                    if item.campo_valor_json:
                        # Processa chaves aninhadas separadas por ponto
                        v = elem
                        for k in item.campo_valor_json.split("."):
                            if isinstance(v, dict):
                                v = v.get(k, 0.0)
                            elif isinstance(v, list):
                                # Se encontrar uma lista intermediária (ex: "valores.valorTotal")
                                # soma os valores da chave dentro de todos os itens da lista
                                v = sum(float(x.get(k, 0.0)) for x in v if isinstance(x, dict) and k in x)
                            else:
                                v = 0.0
                                break
                        return v
                    return elem
            return 0.0

        return val
