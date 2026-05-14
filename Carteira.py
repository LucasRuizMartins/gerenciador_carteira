"""
Módulo de ETL para carteiras de diferentes administradoras.

Hierarquia de classes:
    CarteiraBase (ABC)
    ├── Carteira           - Administradora padrão (processar_dataframes genérico)
    ├── CarteiraBRL        - Administradora BRL
    ├── CarteiraGenial     - Administradora Genial
    ├── CarteiraQI         - Administradora QI
    ├── CarteiraTERRA      - Administradora Terra
    ├── CarteiraMASTER     - Administradora Master (engine xlrd)
    ├── CarteiraAVANTI     - Administradora Avanti
    ├── CarteiraSingulareQI- Administradora Singulare / QI
    └── CarteiraPORTOFINO  - Administradora Portofino
"""

from __future__ import annotations
from src.core.logger import get_logger
logger = get_logger(__name__)

import locale
import re
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any
from zipfile import ZipFile

import pandas as pd

from funcoes_uteis import processar_dataframes, agrupar_dataframe_codigo

locale.setlocale(locale.LC_ALL, "pt_BR.UTF-8")

# ---------------------------------------------------------------------------
# Helpers reutilizáveis (funções puras, sem estado)
# ---------------------------------------------------------------------------

def _resetar_cabecalho(df: pd.DataFrame) -> pd.DataFrame:
    """Promove a primeira linha do DataFrame como cabeçalho."""
    if df.empty or len(df) < 1:
        return pd.DataFrame()
    try:
        df = df.copy()
        df.columns = df.iloc[0]
        return df.iloc[1:].reset_index(drop=True)
    except Exception as exc:
        logger.error(f"Erro ao resetar cabeçalho: {exc}")
        return df


def _encontrar_linha_categoria(
    df: pd.DataFrame, nome_categoria: str, coluna: str | None = None
) -> int | None:
    """Retorna o índice da primeira linha onde *nome_categoria* é encontrado."""
    col = df[coluna] if coluna else df.iloc[:, 0]
    linhas = df.index[col == nome_categoria].tolist()
    return linhas[0] if linhas else None


def _extrair_secao(
    df: pd.DataFrame, inicio: int, fim: int
) -> pd.DataFrame:
    """Fatia o DataFrame entre *inicio* e *fim*, remove linhas vazias iniciais e reseta o cabeçalho."""
    if inicio >= fim:
        return pd.DataFrame()
    
    secao = df.iloc[inicio:fim].reset_index(drop=True)
    
    # Remove linhas onde todos os valores são nulos (comum em layouts com espaços)
    secao = secao.dropna(how='all').reset_index(drop=True)
    
    return _resetar_cabecalho(secao)


def _converter_moeda(valor: Any) -> float:
    """Converte representações monetárias variadas (string, parênteses, vírgula) para float."""
    if pd.isna(valor) or str(valor).strip() == "":
        return 0.0
    if isinstance(valor, (float, int)):
        return float(valor)
    try:
        texto = str(valor).strip()
        negativo = "(" in texto and ")" in texto
        limpo = re.sub(r"[^\d,-]", "", texto)
        if not limpo or limpo == ",":
            return 0.0
        numero = float(limpo.replace(",", "."))
        return -abs(numero) if negativo else numero
    except Exception as exc:
        logger.error(f"Erro ao converter valor '{valor}': {exc}")
        return 0.0


def _classificar_contas(
    df: pd.DataFrame,
    coluna_descricao: str,
    coluna_valor: str,
    palavras_chave: list[str],
    normalizar: bool = True,
) -> pd.DataFrame:
    """
    Normaliza a coluna de descrição substituindo substrings que batem com
    *palavras_chave* pelo próprio termo, e classifica o restante em
    'Contas a pagar' ou 'Contas a receber' de acordo com o sinal do valor.
    Retorna o DataFrame agrupado e ordenado por valor.
    """
    df = df.copy()
    df[coluna_valor] = pd.to_numeric(df[coluna_valor], errors="coerce").fillna(0.0)

    if normalizar:
        descricoes = df[coluna_descricao].str.lower()
        chaves_lower = [p.lower() for p in palavras_chave]

        for chave in chaves_lower:
            mask = descricoes.str.contains(chave, na=False)
            df.loc[mask, coluna_descricao] = chave.capitalize()

        nao_substituido = ~df[coluna_descricao].str.lower().isin(chaves_lower)
        df.loc[nao_substituido, coluna_descricao] = df.loc[nao_substituido, coluna_valor].apply(
            lambda v: "Contas a receber" if v > 0 else "Contas a pagar"
        )

    return df.groupby(coluna_descricao, as_index=False)[coluna_valor].sum().sort_values(coluna_valor)


# ---------------------------------------------------------------------------
# Classe base abstrata
# ---------------------------------------------------------------------------

class CarteiraBase(ABC):
    """
    Contrato comum a todas as carteiras.

    Subclasses devem implementar:
        - carregar_dados()       → lê o arquivo e popula os atributos
        - _processar_planilha()  → parsing específico de cada administradora

    Atributos financeiros compartilhados são inicializados aqui para garantir
    que todas as subclasses possuam a mesma interface.
    """

    def __init__(self, path_carteira: str | None = None) -> None:
        self.path_carteira = path_carteira

        # --- Metadados ---
        self.data: datetime | None = None

        # --- Métricas financeiras ---
        self.patrimonio_total: float = 0.0
        self.saldo_tesouraria: float = 0.0
        self.pdd: float = 0.0

        # --- Contas a pagar / receber ---
        self.outros_valores_pagar: float = 0.0
        self.outros_valores_receber: float = 0.0

        # --- Taxas ---
        self.valor_administracao: float = 0.0
        self.valor_anbima: float = 0.0
        self.valor_anbima_a_receber: float = 0.0
        self.valor_taxa_auditoria: float = 0.0
        self.valor_taxa_custodia: float = 0.0
        self.valor_taxa_gestao: float = 0.0
        self.valor_taxa_cvm: float = 0.0
        self.valor_taxa_performance: float = 0.0

        # --- Liquidez ---
        self.valor_selic: float = 0.0
        self.valor_cetip: float = 0.0
        self.valor_liq_banco: float = 0.0
        self.valor_di: float = 0.0

        # --- Códigos de filtro ---
        self.codigos_contas_pagar: list[str] = []

        # --- DataFrames internos ---
        self._dataframes: dict[str, pd.DataFrame] = {}
        self.df_contas_filtrado: pd.DataFrame | None = None

    # ------------------------------------------------------------------
    # Interface pública obrigatória (polimorfismo)
    # ------------------------------------------------------------------

    @abstractmethod
    def carregar_dados(self, aba: str = "CD_ATUAL") -> None:
        """Lê o arquivo da carteira e popula todos os atributos."""

    @abstractmethod
    def _processar_planilha(self, aba="CD_ATUAL") -> dict[str, pd.DataFrame]:
        """
        Realiza o parsing específico da administradora.
        Deve retornar um dicionário com os DataFrames extraídos.
        """

    # ------------------------------------------------------------------
    # Métodos utilitários compartilhados
    # ------------------------------------------------------------------

    def _validar_path(self) -> None:
        if not self.path_carteira:
            raise ValueError("Caminho da carteira não definido.")

    def acrescentar_contas_pagar(self, *codigos: str) -> None:
        """Registra palavras-chave usadas para classificar contas a pagar."""
        self.codigos_contas_pagar.extend(codigos)

    def recuperar_valor_dataframe(
        self,
        df: pd.DataFrame,
        codigo: str,
        coluna_descricao: str,
        coluna_valor: int | str,
    ) -> float:
        """Recupera um valor escalar do DataFrame pelo código da linha."""
        try:
            filtro = df[coluna_descricao] == codigo
            if isinstance(coluna_valor, int):
                return df.loc[filtro].values[0, coluna_valor]
            return df.loc[filtro, coluna_valor].values[0]
        except Exception:
            logger.info(f"Valor '{codigo}' não encontrado.")
            return 0.0

    def _recuperar_taxa(
        self,
        categoria: str,
        df: pd.DataFrame,
        coluna_busca: str = "Histórico",  # Ajustado para o nome real
        coluna_valor: str = "Valor Total", # Ajustado para o nome real
    ) -> float:
        try:
            if df.empty or coluna_busca not in df.columns:
                return 0.0
            
            # Busca parcial (ex: 'gestão' encontra 'Taxa de Gestão')
            filtro = df[coluna_busca].str.contains(categoria, case=False, na=False)
            resultado = df.loc[filtro, coluna_valor]
            
            return float(resultado.iloc[0]) if not resultado.empty else 0.0
        except Exception as exc:
            # Remova o print depois de validar para não poluir o terminal
            logger.error(f"Erro ao recuperar taxa '{categoria}': {exc}")
            return 0.0

    def _popular_taxas(
        self,
        df_contas: pd.DataFrame,
        coluna: str = "Histórico", # Ajustado para o nome real
    ) -> None:
        if df_contas.empty:
            return

        # Passamos a coluna_valor explicitamente aqui se necessário
        def taxa(cat: str) -> float:
            return self._recuperar_taxa(cat, df_contas, coluna, "Valor Total")

        self.outros_valores_pagar = taxa("Contas a pagar")
        self.outros_valores_receber = taxa("Contas a receber")
        self.valor_administracao = taxa("administração")
        self.valor_anbima = taxa("anbima")
        self.valor_taxa_auditoria = taxa("auditoria")
        self.valor_taxa_custodia = taxa("custódia")
        self.valor_taxa_gestao = taxa("gestão")
        self.valor_taxa_cvm = taxa("cvm")
        self.valor_taxa_performance = taxa("performance")
        self.valor_selic = taxa("selic")
        self.valor_cetip = taxa("cetip")
        self.valor_liq_banco = taxa("banco liquidante")

    def df(self, nome: str) -> pd.DataFrame:
        """Acesso seguro a qualquer DataFrame interno pelo nome."""
        return self._dataframes.get(nome, pd.DataFrame())

    def __repr__(self) -> str:
        return (
            f"{self.__class__.__name__}("
            f"data={self.data}, "
            f"patrimônio={self.patrimonio_total:,.2f})"
        )


# ---------------------------------------------------------------------------
# Mixin: administradoras com planilha "CD_ATUAL" e coluna "Unnamed: 0"
# ---------------------------------------------------------------------------

class _MixinCdAtual:
    """
    Comportamentos comuns a administradoras cujo Excel segue o padrão
    'CD_ATUAL' com coluna-chave 'Unnamed: 0'.
    """

    dataframe: pd.DataFrame  # declarado para o type-checker; populado em subclasse

    def buscar_valor_por_descricao(self, categoria: str, coluna: int = 1) -> float:
        try:
            resultado = self.dataframe.loc[self.dataframe["Unnamed: 0"] == categoria]
            if not resultado.empty:
                return resultado.iloc[0, coluna]
            logger.info(f"Não foi possível encontrar '{categoria}'.")
            return 0.0
        except Exception as exc:
            logger.error(f"Erro ao converter valores: {exc}")
            return 0.0

    def recuperar_valor_carteira(self, codigo: str, coluna: int) -> float:
        try:
            return self.dataframe[self.dataframe["Unnamed: 0"] == codigo].values[0, coluna]
        except Exception:
            logger.info(f"'{codigo}' não encontrado.")
            return 0.0

    def recuperar_valor_carteira_coluna(
        self,
        codigo: str,
        coluna_valor: int,
        coluna_descricao: str = "Unnamed: 0",
    ) -> float:
        try:
            return self.dataframe[
                self.dataframe[coluna_descricao] == codigo
            ].values[0, coluna_valor]
        except Exception:
            logger.info(f"'{codigo}' não encontrado.")
            return 0.0


# ---------------------------------------------------------------------------
# Carteira – administradora padrão (processamento via funcoes_uteis)
# ---------------------------------------------------------------------------

class Carteira(CarteiraBase):
    """Carteira padrão baseada em processar_dataframes() de funcoes_uteis."""

    _CHAVES_DATAFRAME = [
        "renda_fixa",
        "fundos_invest",
        "conta_corrente",
        "contas_pagar",
        "tesouraria",
        "outros_ativos",
        "patrimonio",
        "rentabilidade_acumulada",
    ]

    def __init__(self, path_carteira: str | None = None) -> None:
        super().__init__(path_carteira)
        self.codigos_renda_fixa: list[str] = []
        self.codigos_fundos_investimento: list[str] = []
        self.codigos_outros_ativos: list[str] = []

    # --- Interface obrigatória ---

    def carregar_dados(self, aba: str = "CD_ATUAL") -> None:
        self._validar_path()
        try:
            dados = processar_dataframes(self.path_carteira)
            self._dataframes = {k: dados.get(k, pd.DataFrame()) for k in self._CHAVES_DATAFRAME}
            self.data = dados.get("data_arquivo")
            self._atualizar_metricas()
            self._carregar_contas()
        except Exception as exc:
            raise RuntimeError(f"Erro ao carregar dados da carteira: {exc}") from exc

    def _processar_planilha(self, aba: str = "CD_ATUAL") -> dict[str, pd.DataFrame]:
        """Delegado ao utilitário externo; retorna os dataframes brutos."""
        return processar_dataframes(self.path_carteira, aba)

    # --- Helpers privados ---

    def _atualizar_metricas(self) -> None:
        try:
            if not self.df("tesouraria").empty:
                self.saldo_tesouraria = self.df("tesouraria").iloc[0, 1]
            if not self.df("patrimonio").empty:
                self.patrimonio_total = self.df("patrimonio").iloc[0, 2]
            if not self.df("outros_ativos").empty:
                df_oa = self.df("outros_ativos")
                pdd_rows = df_oa[df_oa["Código"] == "PDD"]
                if not pdd_rows.empty:
                    self.pdd = pdd_rows.iloc[0, 2]
        except Exception as exc:
            logger.warning(f"Aviso: métricas não atualizadas – {exc}")
            self.saldo_tesouraria = 0.0
            self.patrimonio_total = 0.0
            self.pdd = 0.0

    def _carregar_contas(self) -> None:
        df_cp = self.df("contas_pagar")
        if df_cp.empty:
            return

        df_filtrado = agrupar_dataframe_codigo(df_cp, self.codigos_contas_pagar)
        self.df_contas_filtrado = df_filtrado

        def recup(cat: str) -> float:
            return recuperar_contas(cat, df_filtrado) if not df_filtrado.empty else 0.0

        self.outros_valores_pagar = recup("Contas a pagar")
        self.outros_valores_receber = recup("Contas a receber")
        self.valor_administracao = recup("administração")
        self.valor_anbima = recup("anbima")
        self.valor_taxa_auditoria = recup("auditoria")
        self.valor_taxa_custodia = recup("custódia")
        self.valor_taxa_gestao = recup("gestão")
        self.valor_taxa_cvm = recup("cvm")
        self.valor_cetip = recup("cetip")
        self.valor_selic = recup("selic")
        self.valor_liq_banco = recup("banco liquidante")

    # --- Métodos de registro de códigos ---

    def acrescentar_cod_renda_fixa(self, *codigos: str) -> None:
        self.codigos_renda_fixa.extend(codigos)

    def acrescentar_fundos_investimento(self, *codigos: str) -> None:
        self.codigos_fundos_investimento.extend(codigos)

    def acrescentar_cod_outros_ativos(self, *codigos: str) -> None:
        self.codigos_outros_ativos.extend(codigos)

    # --- Properties de acesso aos DataFrames ---

    @property
    def df_renda_fixa(self) -> pd.DataFrame:
        return self.df("renda_fixa")

    @property
    def df_fundos_invest(self) -> pd.DataFrame:
        return self.df("fundos_invest")

    @property
    def df_conta_corrente(self) -> pd.DataFrame:
        return self.df("conta_corrente")

    @property
    def df_tesouraria(self) -> pd.DataFrame:
        return self.df("tesouraria")

    @property
    def df_outros_ativos(self) -> pd.DataFrame:
        return self.df("outros_ativos")

    @property
    def df_patrimonio(self) -> pd.DataFrame:
        return self.df("patrimonio")

    @property
    def df_rentabilidade_acumulada(self) -> pd.DataFrame:
        return self.df("rentabilidade_acumulada")


# ---------------------------------------------------------------------------
# Mixin: parsing BRL – administradoras com estrutura similar (BRL / Genial / QI)
# ---------------------------------------------------------------------------

class _MixinParseBRL:
    """
    Fornece o método genérico de parsing de seções de um Excel estruturado
    com marcadores de linha para cada categoria.
    """

    codigos_contas_pagar: list[str]

    @staticmethod
    def _resetar(df: pd.DataFrame) -> pd.DataFrame:
        return _resetar_cabecalho(df)

    @staticmethod
    def _localizar_linha(df: pd.DataFrame, categoria: str, coluna: str) -> int | None:
        return _encontrar_linha_categoria(df, categoria, coluna)

    def _encontrar_linhas(
        self, df: pd.DataFrame, categorias: dict[str, str], coluna: str
    ) -> dict[str, int]:
        resultado: dict[str, int] = {}
        for chave, nome in categorias.items():
            linha = self._localizar_linha(df, nome, coluna)
            if linha is None:
                logger.warning(f"Aviso: '{nome}' não encontrado. Usando fim do DataFrame.")
                linha = len(df)
            resultado[chave] = linha
        return resultado

    def _agrupar_contas(
        self,
        df: pd.DataFrame,
        coluna_descricao: str,
        coluna_valor: str,
    ) -> pd.DataFrame:
        return _classificar_contas(
            df, coluna_descricao, coluna_valor, self.codigos_contas_pagar
        )


# ---------------------------------------------------------------------------
# CarteiraBRL
# ---------------------------------------------------------------------------

class CarteiraBRL(_MixinParseBRL, CarteiraBase):
    """
    Administradora BRL – planilha 'CD_ATUAL', coluna-chave 'Carteira'.

    Suporta arquivos .xlsb (pyxlsb) e .xlsx/.xls (openpyxl/xlrd).
    A coluna de índice é detectada dinamicamente para evitar erros com
    nomes como 'Unnamed: 0' que variam por engine.
    """

    # Textos-marcador usados para delimitar cada seção da planilha
    _MARCADORES = {
        "contas_pagar": "VALORES A LIQUIDAR",
        "saldo_conta": "SALDOS EM CONTA CORRENTE",
        "contas_receber": "Valores a Receber",
        "cotas_superiores": "COTAS DE INVESTIMENTO",
        "resumo_carteira": "RESUMO DA CARTEIRA",
    }

    def __init__(self, path_carteira: str | None = None) -> None:
        super().__init__(path_carteira)
        self.a_vencer: float = 0.0
        self.vencido: float = 0.0
        self.dataframe: pd.DataFrame | None = None
        self.df_contas_receber_filtrado: pd.DataFrame | None = None
        self.df_cotas_superiores: pd.DataFrame | None = None

    # ------------------------------------------------------------------
    # Interface obrigatória
    # ------------------------------------------------------------------

    def carregar_dados(self, aba: str = "CD_ATUAL") -> None:
        self._validar_path()
        try:
            self.dataframe = self._ler_planilha(aba)
            self._col_chave = self.dataframe.columns[0]   # detecta "Carteira" ou o que vier
            self._carregar_metricas_principais()
            self._dataframes = self._processar_planilha()
            
            # Popula os atributos específicos para facilitar o acesso
            self.df_cotas_superiores = self._dataframes.get("cotas_superiores", pd.DataFrame())
            self.df_contas_receber_filtrado = self._dataframes.get("contas_receber", pd.DataFrame())
            
            self._carregar_contas_brl()
        except Exception as exc:
            raise RuntimeError(f"Erro ao carregar CarteiraBRL: {exc}") from exc

    # Textos-marcador com variantes — serão testados até o primeiro que bater
    _VARIANTES_MARCADORES = {
        "contas_pagar":     ["Valores a Pagar", "VALORES A LIQUIDAR", "Valores a Liquidar",
                             "VALORES A PAGAR"],
        "fim_contas_pagar": ["Caixa", "SALDOS EM CONTA CORRENTE", "Saldos em Conta Corrente",
                             "SALDO EM CONTA CORRENTE", "Saldo em Conta Corrente"],
        "contas_receber":   ["Valores a Receber", "VALORES A RECEBER", "Contas a Receber"],
        "cotas_superiores": ["COTAS SUPERIORES", "Cotas Superiores", "COTAS DE INVESTIMENTO", "Cotas de Investimento", "Cotas de Fundos"],
        "resumo_carteira":  ["RESUMO DA CARTEIRA", "Resumo da Carteira", "RESUMO CARTEIRA"],
    }

    def _processar_planilha(self, aba="CD_ATUAL") -> dict[str, pd.DataFrame]:
        # Reutiliza o dataframe já lido em vez de abrir o arquivo novamente
        df = self.dataframe.reset_index(drop=True)
        col = self._col_chave

        # Detecta os marcadores reais presentes na planilha
        valores_col = df[col].dropna().astype(str).str.strip().tolist()
        marcadores_encontrados: dict[str, str] = {}
        for chave, variantes in self._VARIANTES_MARCADORES.items():
            for v in variantes:
                if v in valores_col:
                    marcadores_encontrados[chave] = v
                    break
            else:
                # Fallback: busca case-insensitive parcial
                for v in variantes:
                    matches = [x for x in valores_col if v.lower() in x.lower()]
                    if matches:
                        marcadores_encontrados[chave] = matches[0]
                        break

        # Marcadores opcionais (ausentes em alguns relatórios) — só avisa os obrigatórios
        _obrigatorios = {"contas_pagar", "fim_contas_pagar"}
        faltando_obrig = _obrigatorios - marcadores_encontrados.keys()
        if faltando_obrig:
            logger.info(
                f"Aviso CarteiraBRL._processar_planilha: marcadores obrigatórios não encontrados: {faltando_obrig}\n"
                f"  Valores únicos na coluna '{col}':\n"
                f"  {[v for v in valores_col if not v.startswith('Unnamed')][:60]}"
            )

        linhas = {
            chave: df.index[df[col].astype(str).str.strip() == texto].tolist()[0]
            for chave, texto in marcadores_encontrados.items()
        }

        # Ordena os marcadores pela linha em que aparecem
        linhas_ordenadas = sorted([(nome, idx) for nome, idx in linhas.items()], key=lambda x: x[1])
        
        def _proxima_linha(linha_atual: int) -> int:
            """Retorna a linha do próximo marcador, ou o final do arquivo."""
            for _, idx in linhas_ordenadas:
                if idx > linha_atual:
                    return idx
            return len(df)

        secoes_carteira: dict[str, pd.DataFrame] = {}

        if "contas_pagar" in linhas:
            secoes_carteira["contas_pagar"] = _extrair_secao(df, linhas["contas_pagar"] + 1, _proxima_linha(linhas["contas_pagar"]))

        if "contas_receber" in linhas:
            secoes_carteira["contas_receber"] = _extrair_secao(df, linhas["contas_receber"] + 1, _proxima_linha(linhas["contas_receber"]))

        if "cotas_superiores" in linhas:
            secoes_carteira["cotas_superiores"] = _extrair_secao(df, linhas["cotas_superiores"] + 1, _proxima_linha(linhas["cotas_superiores"]))

        if "resumo_carteira" in linhas:
            secoes_carteira["resumo_carteira"] = _extrair_secao(df, linhas["resumo_carteira"] + 1, linhas["resumo_carteira"] + 6)
            
        # Debug para ajudar a identificar o erro 'Ordem' se cotas_superiores existir
        if "cotas_superiores" in secoes_carteira:
            df_cotas = secoes_carteira["cotas_superiores"]
            # Debug para ajudar a identificar o erro 'Ordem'
            if "Ordem" not in df_cotas.columns and not df_cotas.empty:
                logger.info(f"DEBUG CDC/BRL: Coluna 'Ordem' não encontrada em 'cotas_superiores'.")
                logger.info(f"Colunas detectadas: {list(df_cotas.columns)}")
                
        return secoes_carteira

    # ------------------------------------------------------------------
    # Helpers privados
    # ------------------------------------------------------------------

    def _ler_planilha(self, aba: str) -> pd.DataFrame:
        """Lê o Excel escolhendo o engine correto pelo nome do arquivo."""
        path = self.path_carteira
        if path.endswith(".xlsb"):
            return pd.read_excel(path, sheet_name=aba, engine="pyxlsb")
        return pd.read_excel(path, sheet_name=aba)

    def _buscar_valor_por_descricao(self, categoria: str, coluna: int = 1) -> float:
        """Busca um valor escalar pelo texto da coluna-chave e índice de coluna."""
        try:
            col = self._col_chave
            resultado = self.dataframe.loc[self.dataframe[col] == categoria]
            return resultado.iloc[0, coluna] if not resultado.empty else 0.0
        except Exception as exc:
            logger.error(f"Erro ao ler '{categoria}': {exc}")
            return 0.0

    def _carregar_metricas_principais(self) -> None:
        col = self._col_chave
        self.data = pd.to_datetime(
            self.dataframe.loc[self.dataframe[col] == "Data Posição"].iloc[0, 1],
            format="%d/%m/%Y",
        )
        self.a_vencer = self._buscar_valor_por_descricao("A VENCER", 2)
        self.vencido = self._buscar_valor_por_descricao("VENCIDO", 2)
        self.pdd = self._buscar_valor_por_descricao("PDD", 1)
        self.saldo_tesouraria = self._buscar_valor_por_descricao("C/C", 1)
        self.patrimonio_total = self._buscar_valor_por_descricao("PL Posição", 1)
        self.valor_di = self._buscar_valor_por_descricao("Total RENDA FIXA:", 5)

    # Candidatos de nome para coluna de descrição e de valor no bloco contas_pagar
    _CANDIDATOS_DESCRICAO = ["Historico", "Histórico", "Segmento", "Descrição", "Descricao", "DESCRIÇÃO"]
    _CANDIDATOS_VALOR     = ["Valor Total", "Valor", "Valor Mov", "Vlr Mov",
                              "Valor Financeiro", "Vlr Financeiro", "VALOR"]

    def _carregar_contas_brl(self) -> None:
        # Processa Contas a Pagar
        df_cp = self._dataframes.get("contas_pagar", pd.DataFrame())
        if not df_cp.empty:
            df_cp = self._limpar_df_contas(df_cp)
            col_desc = self._detectar_coluna(df_cp, self._CANDIDATOS_DESCRICAO)
            col_val  = self._detectar_coluna(df_cp, self._CANDIDATOS_VALOR)
            if col_desc and col_val:
                self.df_contas_filtrado = _classificar_contas(df_cp, col_desc, col_val, self.codigos_contas_pagar)
                self._popular_taxas(self.df_contas_filtrado, coluna=col_desc)

        # Processa Contas a Receber
        df_cr = self._dataframes.get("contas_receber", pd.DataFrame())
        if not df_cr.empty:
            df_cr = self._limpar_df_contas(df_cr)
            col_desc = self._detectar_coluna(df_cr, self._CANDIDATOS_DESCRICAO)
            col_val  = self._detectar_coluna(df_cr, self._CANDIDATOS_VALOR)
            if col_desc and col_val:
                self.df_contas_receber_filtrado = _classificar_contas(
                    df_cr, col_desc, col_val, self.codigos_contas_pagar, normalizar=False
                )

    def _limpar_df_contas(self, df: pd.DataFrame) -> pd.DataFrame:
        """Remove linhas de subtotal e total de um bloco de contas."""
        df_limpo = df.copy()
        for col_seg in ("Segmento", "segmento", "Código", "Codigo"):
            if col_seg in df_limpo.columns:
                df_limpo = df_limpo[~df_limpo[col_seg].astype(str).str.contains("total", case=False, na=False)]
        return df_limpo

    @staticmethod
    def _detectar_coluna(df: pd.DataFrame, candidatos: list[str]) -> str | None:
        """Retorna o primeiro candidato que existe como coluna em *df* (case-insensitive)."""
        colunas = list(df.columns)
        # Passagem exata
        for c in candidatos:
            if c in colunas:
                return c
        # Passagem case-insensitive (cobre acentuação variada)
        colunas_lower = [str(c).lower() for c in colunas]
        for c in candidatos:
            try:
                idx = colunas_lower.index(c.lower())
                return colunas[idx]
            except ValueError:
                continue
        return None

    # ------------------------------------------------------------------
    # API pública que o código consumidor já usa
    # ------------------------------------------------------------------

    def recuperar_valor_carteira(self, codigo: str, coluna: int) -> float:
        """Retorna o valor na posição *coluna* da linha identificada por *codigo*."""
        try:
            col = self._col_chave
            return self.dataframe[self.dataframe[col] == codigo].values[0, coluna]
        except Exception:
            logger.info(f"recuperar_valor_carteira: '{codigo}' não encontrado.")
            return 0.0

    def recuperar_contas(
        self,
        categoria: str,
        df: pd.DataFrame,
        coluna_descricao: str = "Histórico", # Verifique se tem acento!
        coluna_valor: str = "Valor Total",   # Alterado para o nome real
    ) -> float:
        """
        Retorna o valor da *categoria* no DataFrame de contas filtrado.
        Compatível com a chamada:
            carteira_fidara.recuperar_contas('Cvm', carteira_fidara.df_contas_filtrado)
        """
        try:
            filtro = df[coluna_descricao].str.contains(categoria, case=False, na=False)
            resultado = df.loc[filtro, coluna_valor]
            return float(resultado.sum())
        except Exception:
            return 0.0



# CarteiraGenial


class CarteiraGenial(_MixinCdAtual, _MixinParseBRL, CarteiraBase):
    """Administradora Genial – planilha 'CD_ATUAL' com coluna-chave 'Unnamed: 0'."""

    def __init__(self, path_carteira: str | None = None) -> None:
        super().__init__(path_carteira)
        self.dataframe: pd.DataFrame | None = None
        self.df_contas_receber_filtrado: pd.DataFrame | None = None
        self.df_cotas_superiores: pd.DataFrame | None = None

    # --- Interface obrigatória ---

    def carregar_dados(self, aba="CD_ATUAL") -> None:
        self._validar_path()
        try:
            self.dataframe = pd.read_excel(self.path_carteira, sheet_name=aba)
            self.data = pd.to_datetime(self.dataframe.iloc[3, 0], format="%d/%m/%Y")
            self.saldo_tesouraria = self.buscar_valor_por_descricao("Total Saldos em Conta Corrente", 2)
            self.patrimonio_total = self.buscar_valor_por_descricao("PATRIMÔNIO LIQUIDO", 1)
            self._dataframes = self._processar_planilha()
            self._carregar_contas_genial()
        except Exception as exc:
            raise RuntimeError(f"Erro ao carregar dados da carteira Genial: {exc}") from exc

    def _processar_planilha(self, aba="CD_ATUAL") -> dict[str, pd.DataFrame]:
        df = self.dataframe.reset_index(drop=True)
        categorias = {
            "contas_pagar": "VALORES A LIQUIDAR",
            "saldo_conta": "SALDOS EM CONTA CORRENTE",
            "cotas_superiores": "COTAS DE INVESTIMENTO",
            "resumo_carteira": "RESUMO DA CARTEIRA",
        }
        linhas = self._encontrar_linhas(df, categorias, "Unnamed: 0")
        secoes_carteira: dict[str, pd.DataFrame] = {}
        secoes_carteira["contas_pagar"] = _extrair_secao(df, linhas["contas_pagar"] + 1, linhas["saldo_conta"])
        secoes_carteira["resumo_carteira"] = _extrair_secao(
            df, linhas["resumo_carteira"] + 1, linhas["resumo_carteira"] + 6
        )
        secoes_carteira["cotas_superiores"] = _extrair_secao(
            df, linhas["cotas_superiores"] + 1, linhas["contas_pagar"]
        )
        return secoes_carteira

    # --- Helper de agrupamento específico Genial ---

    def _agrupar_contas_genial(self) -> pd.DataFrame:
        """Extrai e normaliza o bloco 'Valores a Liquidar' direto do self.dataframe."""
        df = self.dataframe
        inicio = df.query("`Unnamed: 1` == 'Valores a Liquidar'").index[0]
        fim = df.query("`Unnamed: 1` == 'Total Liquidação:'").index[0]
        df_contas = df[inicio:fim].copy()
        df_contas.columns = df[inicio + 2:fim].iloc[0]
        df_contas = df_contas[3:].dropna(axis=1, how="all").dropna(axis=0, how="all")
        return self._agrupar_contas(df_contas, "Descricão", "Valor")

    def _carregar_contas_genial(self) -> None:
        self.df_contas_filtrado = self._agrupar_contas_genial()
        self._popular_taxas(self.df_contas_filtrado, coluna="Descricão")
        self.valor_taxa_performance = self._recuperar_taxa("performance", self.df_contas_filtrado, "Descricão")


# ---------------------------------------------------------------------------
# CarteiraQI
# ---------------------------------------------------------------------------

class CarteiraQI(_MixinCdAtual, _MixinParseBRL, CarteiraBase):
    """Administradora QI – planilha 'CD_ATUAL', categorias em maiúsculo."""

    def __init__(self, path_carteira: str | None = None) -> None:
        super().__init__(path_carteira)
        self.dataframe: pd.DataFrame | None = None
        self.df_cotas_superiores: pd.DataFrame | None = None
        self.df_contas_receber: pd.DataFrame | None = None
        self.df_serie_emissao: pd.DataFrame | None = None
        self.df_cotas: pd.DataFrame | None = None
        self.codigos_cotas: list[str] = []

    # --- Interface obrigatória ---

    def carregar_dados(self, aba="CD_ATUAL") -> None:
        self._validar_path()
        try:
            self.dataframe = pd.read_excel(self.path_carteira, sheet_name=aba)
            self.data = pd.to_datetime(
                self.dataframe.loc[
                    self.dataframe["Unnamed: 0"] == "Data de referência", "Unnamed: 1"
                ].values[0]
            )
            self.saldo_tesouraria = self.buscar_valor_por_descricao("SALDO TOTAL", 5)
            self.valor_di = self.buscar_valor_por_descricao("TOTAL DE RENDA FIXA", 11)
            self.patrimonio_total = self.buscar_valor_por_descricao("PATRIMÔNIO LIQUIDO", 1)
            self._dataframes = self._processar_planilha()
            self._carregar_referencias_dataframes()
            self._carregar_contas_qi()
        except Exception as exc:
            raise RuntimeError(f"Erro ao carregar dados da carteira QI: {exc}") from exc

    def _processar_planilha(self, aba="CD_ATUAL") -> dict[str, pd.DataFrame]:
        df = self.dataframe.reset_index(drop=True)
        categorias = {
            "serie_emissao": "SÉRIES DE EMISSÃO",
            "titulos_publicos": "TÍTULOS PÚBLICOS",
            "contas_pagar": "VALORES A PAGAR",
            "cotas_superiores": "COTAS DE FUNDOS",
            "contas_receber": "VALORES A RECEBER",
            "linha_final_pagar": "TOTAL A PAGAR",
        }
        linhas = self._encontrar_linhas(df, categorias, "Unnamed: 0")
        secoes_carteira: dict[str, pd.DataFrame] = {}
        secoes_carteira["serie_emissao"] = _extrair_secao(df, linhas["serie_emissao"] + 1, linhas["titulos_publicos"])
        secoes_carteira["titulos_publicos"] = _extrair_secao(df, linhas["titulos_publicos"] + 1, linhas["contas_pagar"])
        secoes_carteira["contas_pagar"] = _extrair_secao(df, linhas["contas_pagar"] + 1, linhas["linha_final_pagar"])
        secoes_carteira["cotas_superiores"] = _extrair_secao(df, linhas["cotas_superiores"] + 1, linhas["contas_receber"])
        secoes_carteira["contas_receber"] = _extrair_secao(df, linhas["contas_receber"] + 1, linhas["contas_receber"] + 10)
        return secoes_carteira

    # --- Helpers privados ---

    def _carregar_referencias_dataframes(self) -> None:
        self.df_contas_receber = self._dataframes.get("contas_receber", pd.DataFrame())
        self.df_cotas_superiores = self._dataframes.get("cotas_superiores", pd.DataFrame())
        self.df_serie_emissao = self._dataframes.get("serie_emissao", pd.DataFrame())

    def _carregar_contas_qi(self) -> None:
        df_cp = self._dataframes.get("contas_pagar", pd.DataFrame())
        if df_cp.empty:
            return
        idx_cat = df_cp.columns.get_loc("CATEGORIA") if "CATEGORIA" in df_cp.columns else 3
        idx_val = df_cp.columns.get_loc("Valor") if "Valor" in df_cp.columns else 9
        df_cp = df_cp.rename(columns={df_cp.columns[idx_cat]: "CATEGORIA", df_cp.columns[idx_val]: "Valor"})
        self.df_contas_filtrado = self._agrupar_contas(df_cp, "CATEGORIA", "Valor")
        self._popular_taxas(self.df_contas_filtrado)

    def acrescentar_contas_cotas(self, *codigos: str) -> None:
        self.codigos_cotas.extend(codigos)

    def agrupar_valor_carteira_coluna(
        self, codigo: str, coluna_valor: str, coluna_descricao: str = "Unnamed: 0"
    ) -> float:
        try:
            df = self.dataframe[self.dataframe[coluna_descricao] == codigo]
            df = df.groupby("Unnamed: 2")[[coluna_valor]].sum()
            return df.values[0, 0]
        except Exception as exc:
            logger.error(f"Erro ao somar valores: {exc}")
            return 0.0


# ---------------------------------------------------------------------------
# CarteiraTERRA
# ---------------------------------------------------------------------------

class CarteiraTERRA(_MixinParseBRL, CarteiraBase):
    """Administradora Terra – duas planilhas: 'CD_ATUAL_CLASSE' e 'CD_ATUAL_SUBCLASSE'."""

    def __init__(self, path_carteira: str | None = None) -> None:
        super().__init__(path_carteira)
        self.dataframe_1: pd.DataFrame | None = None
        self.dataframe_2: pd.DataFrame | None = None
        self.df_contas_receber_filtrado: pd.DataFrame | None = None

    # --- Interface obrigatória ---

    def carregar_dados(self, aba="CD_ATUAL") -> None:
        self._validar_path()
        try:
            self.dataframe_1 = pd.read_excel(self.path_carteira, sheet_name="CD_ATUAL_CLASSE")
            self.dataframe_2 = pd.read_excel(self.path_carteira, sheet_name="CD_ATUAL_SUBCLASSE")
            self._buscar_data()
            self.df_contas_receber_filtrado = self._agrupar_contas_terra("receber")
            self.df_contas_filtrado = self._agrupar_contas_terra("pagar")
            self._popular_taxas(self.df_contas_filtrado, coluna="DESCRIÇÃO")
            self.saldo_tesouraria = self._recuperar_taxa("N/c", self.df_contas_receber_filtrado, "DESCRIÇÃO")
        except Exception as exc:
            raise RuntimeError(f"Erro ao carregar dados da carteira Terra: {exc}") from exc

    def _processar_planilha(self, aba="CD_ATUAL") -> dict[str, pd.DataFrame]:
        # Terra não usa um dict de DataFrames padronizado; retorna vazio.
        return {}

    # --- Helpers privados ---

    def _buscar_data(self) -> None:
        for i in range(1, 15):
            try:
                self.data = pd.to_datetime(
                    self.dataframe_2.iloc[5, i], format="%d/%m/%Y", errors="raise"
                ).strftime("%d/%m/%Y")
                break
            except (ValueError, TypeError):
                continue

    def _agrupar_contas_terra(self, tipo: str = "receber") -> pd.DataFrame:
        df = self.dataframe_1.copy()
        df = df.rename(columns={df.columns[28]: "Valor"})

        if tipo == "receber":
            df_filtrado = df[df["Valor"] >= 0]
            padrao = "Contas a receber"
        elif tipo == "pagar":
            df_filtrado = df[df["Valor"] < 0]
            padrao = "Contas a pagar"
        else:
            raise ValueError("Tipo inválido. Use 'receber' ou 'pagar'.")

        df_filtrado = df_filtrado.copy()
        descricoes = df_filtrado["DESCRIÇÃO"].str.lower()
        chaves = [p.lower() for p in self.codigos_contas_pagar]

        for chave in chaves:
            mask = descricoes.str.contains(chave, na=False)
            df_filtrado.loc[mask, "DESCRIÇÃO"] = chave.capitalize()

        nao_sub = ~df_filtrado["DESCRIÇÃO"].str.lower().isin(chaves)
        df_filtrado.loc[nao_sub, "DESCRIÇÃO"] = padrao

        return df_filtrado.groupby("DESCRIÇÃO", as_index=False)["Valor"].sum().sort_values(
            "Valor", ascending=(tipo == "receber")
        )

    def recuperar_valor_descricao(self, col_codigo: str, descricao: str, col_valor: int) -> float:
        try:
            return self.dataframe_1[self.dataframe_1[col_codigo] == descricao].values[0, col_valor]
        except Exception:
            return 0.0


# ---------------------------------------------------------------------------
# CarteiraMASTER
# ---------------------------------------------------------------------------

class CarteiraMASTER(_MixinParseBRL, CarteiraBase):
    """Administradora Master – planilhas 'Page 1/2/3', engine xlrd."""

    def __init__(self, path_carteira: str | None = None) -> None:
        super().__init__(path_carteira)
        self.dataframe_1: pd.DataFrame | None = None
        self.dataframe_2: pd.DataFrame | None = None
        self.dataframe_3: pd.DataFrame | None = None
        self.df_contas_receber: pd.DataFrame | None = None
        self.df_contas_receber_filtrado: pd.DataFrame | None = None

    # --- Interface obrigatória ---

    def carregar_dados(self, aba="CD_ATUAL") -> None:
        self._validar_path()
        try:
            self.dataframe_1 = pd.read_excel(self.path_carteira, sheet_name="Page 1", engine="xlrd")
            self.dataframe_2 = pd.read_excel(self.path_carteira, sheet_name="Page 2", engine="xlrd")
            try:
                self.dataframe_3 = pd.read_excel(self.path_carteira, sheet_name="Page 3", engine="xlrd")
            except Exception:
                self.dataframe_3 = self.dataframe_2.copy()

            self._carregar_data()
            self._dataframes = self._processar_planilha()
            self._carregar_contas_master()
        except Exception as exc:
            raise RuntimeError(f"Erro ao carregar dados da carteira Master: {exc}") from exc

    def _processar_planilha(self, aba="CD_ATUAL") -> dict[str, pd.DataFrame]:
        return self._processar_pagina(self.dataframe_2, "Unnamed: 1")

    # --- Helpers privados ---

    def _carregar_data(self) -> None:
        try:
            self.data = datetime.strptime(self.dataframe_2.iloc[4, 9], "%d/%m/%Y").date()
        except Exception:
            self.data = None

    def _processar_pagina(
        self, df_origem: pd.DataFrame, coluna: str
    ) -> dict[str, pd.DataFrame]:
        df = df_origem.reset_index(drop=True)
        categorias = {
            "contas_pagar": "Contas a Pagar",
            "contas_receber": "Contas a Receber",
            "fim_contas_receber": "Total Contas a Receber",
        }
        linhas = self._encontrar_linhas(df, categorias, coluna)
        secoes_carteira: dict[str, pd.DataFrame] = {}
        secoes_carteira["contas_pagar"] = _extrair_secao(df, linhas["contas_pagar"] + 1, linhas["contas_receber"] - 1)
        secoes_carteira["contas_receber"] = _extrair_secao(df, linhas["contas_receber"], linhas["fim_contas_receber"] + 1)
        return secoes_carteira

    def _carregar_contas_master(self) -> None:
        df_cp = self._dataframes.get("contas_pagar", pd.DataFrame())
        if df_cp.empty:
            return
        df_cp = df_cp.rename(columns={df_cp.columns[26]: "Valor", df_cp.columns[1]: "DESCRIÇÃO"})
        df_cp["Valor"] = df_cp["Valor"].apply(_converter_moeda)
        self.df_contas_filtrado = self._agrupar_contas(df_cp, "DESCRIÇÃO", "Valor")
        self._popular_taxas(self.df_contas_filtrado, coluna="DESCRIÇÃO")

    def recuperar_valor_carteira(self, df: pd.DataFrame, codigo: str, coluna: int) -> float:
        try:
            return df[df["Unnamed: 1"] == codigo].values[0, coluna]
        except Exception:
            logger.info(f"'{codigo}' não encontrado.")
            return 0.0

    def recuperar_valor_por_coluna(
        self, df: pd.DataFrame, codigo: str, coluna_codigo: str, coluna_valor: int
    ) -> float:
        try:
            return df[df[coluna_codigo] == codigo].values[0, coluna_valor]
        except Exception:
            logger.info(f"'{codigo}' não encontrado.")
            return 0.0

    def recuperar_valor_descricao(self, col_codigo: str, descricao: str, col_valor: int) -> float:
        try:
            return self.dataframe_1[self.dataframe_1[col_codigo] == descricao].values[0, col_valor]
        except Exception:
            return 0.0


# ---------------------------------------------------------------------------
# CarteiraAVANTI
# ---------------------------------------------------------------------------

class CarteiraAVANTI(_MixinParseBRL, CarteiraBase):
    """Administradora Avanti – planilha 'CD_ATUAL', engine openpyxl."""

    def __init__(self, path_carteira: str | None = None) -> None:
        super().__init__(path_carteira)
        self.dataframe: pd.DataFrame | None = None
        self.df_contas: pd.DataFrame | None = None
        self.df_contas_pagar: pd.DataFrame | None = None
        self.df_contas_receber: pd.DataFrame | None = None

    # --- Interface obrigatória ---

    def carregar_dados(self, aba="CD_ATUAL") -> None:
        self._validar_path()
        try:
            self.dataframe = pd.read_excel(self.path_carteira, sheet_name=aba, engine="openpyxl")
            self._dataframes = self._processar_planilha()
            self._carregar_data_avanti()
            self._carregar_contas_avanti()
            self.patrimonio_total = self._recuperar_por_coluna("PATRIMÔNIO FECHAMENTO", "Unnamed: 1", 38)
        except Exception as exc:
            raise RuntimeError(f"Erro ao carregar dados da carteira Avanti: {exc}") from exc

    def _processar_planilha(self, aba="CD_ATUAL") -> dict[str, pd.DataFrame]:
        df = self.dataframe.copy()
        categorias = {
            "valores_liquidar": "Valores a Liquidar",
            "valores_liquidar_fim": "Total Liquidação:",
        }
        linhas = self._encontrar_linhas(df, categorias, "Unnamed: 1")
        secoes_carteira: dict[str, pd.DataFrame] = {}
        start = linhas["valores_liquidar"] + 1
        end = linhas["valores_liquidar_fim"] - 2
        secoes_carteira["valores_liquidar"] = df.iloc[start:end].reset_index(drop=True) if start < end else pd.DataFrame()
        return secoes_carteira

    # --- Helpers privados ---

    def _carregar_data_avanti(self) -> None:
        try:
            valor = self._recuperar_por_coluna("Data Posição: ", "Unnamed: 1", 5)
            self.data = datetime.strptime(valor, "%d/%m/%Y").date()
        except Exception:
            try:
                self.data = self._recuperar_por_coluna("Data Posição: ", "Unnamed: 1", 10)
            except Exception:
                self.data = None

    def _carregar_contas_avanti(self) -> None:
        df_raw = self._dataframes.get("valores_liquidar", pd.DataFrame())
        df_contas = self._resetar_cabecalho_avanti(df_raw)
        self.df_contas = df_contas
        self.df_contas_pagar = self._agrupar_contas(
            df_contas[df_contas["Valor"] < 0], "Descrição", "Valor"
        )
        self.df_contas_receber = self._agrupar_contas(
            df_contas[df_contas["Valor"] > 0], "Descrição", "Valor"
        )
        # Avanti usa nomes de coluna "Historico"
        self.valor_administracao = self._recup_avanti(self.df_contas_pagar, "Adm")
        self.valor_taxa_cvm = self._recup_avanti(self.df_contas_pagar, "Cvm")
        self.valor_taxa_custodia = self._recup_avanti(self.df_contas_pagar, "Custódia")
        self.valor_taxa_gestao = self._recup_avanti(self.df_contas_pagar, "Gestão")
        self.valor_cetip = self._recup_avanti(self.df_contas_pagar, "Cetip")
        self.outros_valores_pagar = self._recup_avanti(self.df_contas_pagar, "Contas a pagar")
        self.outros_valores_receber = self._recup_avanti(self.df_contas_receber, "Contas a receber")

    def _recup_avanti(self, df: pd.DataFrame, taxa: str) -> float:
        try:
            return df[df["Historico"] == taxa].iloc[0, 1]
        except Exception:
            return 0.0

    @staticmethod
    def _resetar_cabecalho_avanti(df: pd.DataFrame) -> pd.DataFrame:
        if df.empty:
            return pd.DataFrame()
        try:
            df = df.iloc[1:]
            df.columns = df.iloc[0]
            df = df.iloc[1:].reset_index(drop=True)
            df = df.loc[:, ~df.columns.astype(str).str.lower().isin(["nan", ""])]
            return df[df["Descrição"].notna()]
        except Exception as exc:
            logger.error(f"Erro ao resetar cabeçalho Avanti: {exc}")
            return df

    def _recuperar_por_coluna(self, codigo: str, coluna_codigo: str, coluna_valor: int) -> Any:
        try:
            return self.dataframe[self.dataframe[coluna_codigo] == codigo].values[0, coluna_valor]
        except Exception:
            logger.info(f"'{codigo}' não encontrado.")
            return 0


# ---------------------------------------------------------------------------
# CarteiraSingulareQI
# ---------------------------------------------------------------------------

class CarteiraSingulareQI(_MixinCdAtual, _MixinParseBRL, CarteiraBase):
    """Administradora Singulare/QI – planilha 'CD_ATUAL' com coluna 'Unnamed: 0'."""

    def __init__(self, path_carteira: str | None = None) -> None:
        super().__init__(path_carteira)
        self.dataframe: pd.DataFrame | None = None
        self.df_contas_receber: pd.DataFrame | None = None
        self.df_cotas_superiores: pd.DataFrame | None = None
        self.df_serie_emissao: pd.DataFrame | None = None
        self.df_outros_ativos: pd.DataFrame | None = None
        self.df_outros_fundos: pd.DataFrame | None = None
        self.df_mezanino: pd.DataFrame | None = None
        self.df_senior: pd.DataFrame | None = None
        self.df_over_ntn: pd.DataFrame | None = None
        self.df_over_ltn: pd.DataFrame | None = None
        self.df_nc: pd.DataFrame | None = None
        self.df_vencidos: pd.DataFrame | None = None
        self.pdd_cri: pd.DataFrame | None = None
        self.df_tesouraria: pd.DataFrame | None = None
        self.codigos_cotas: list[str] = []

    # --- Interface obrigatória ---

    def carregar_dados(self, aba="CD_ATUAL") -> None:
        self._validar_path()
        try:
            self.dataframe = pd.read_excel(self.path_carteira, sheet_name=aba)
            self.dataframe = self.dataframe.rename(
                columns={self.dataframe.columns[0]: "Carteira Diária"}
            )
            self.data = pd.to_datetime(
                self.recuperar_valor_carteira_coluna("Saldo em Tesouraria", 2, "Unnamed: 3"),
                dayfirst=True,
            )
            self.patrimonio_total = self.recuperar_valor_carteira_coluna("PATRIMON", 12)
            self._dataframes = self._processar_planilha()
            self._carregar_referencias()
            self._carregar_contas_singulare()
        except Exception as exc:
            raise RuntimeError(f"Erro ao carregar CarteiraSingulareQI: {exc}") from exc

    def _processar_planilha(self, aba="CD_ATUAL") -> dict[str, pd.DataFrame]:
        df = self.dataframe.reset_index(drop=True)
        categorias_codigo = {
            "contas_pagar": "CPR",
            "outros_ativos": "OutrosAtivos",
            "outros_fundos": "OutrosFundos",
            "mezanino": "MEZAN",
            "senior": "SRP",
            "ntn": "NTN-B",
            "ltno": "LTNO",
            "nc": "NCPX",
            "vccri": "VCCRI",
            "pddcri": "PDCRI",
            "tesouraria": "Tesouraria",
        }
        linhas: dict[str, int] = {}
        for chave, nome in categorias_codigo.items():
            idx = df.index[df.iloc[:, 0] == nome].tolist()
            linhas[chave] = idx[0] if idx else len(df)

        def extrair(linha: int) -> pd.DataFrame:
            start = linha + 1
            mask = df.iloc[start:, 0].astype(str).str.contains(r"^Totais:$", na=False)
            end = mask.idxmax() if mask.any() else len(df)
            return _extrair_secao(df, start, end)

        return {nome: extrair(linha) for nome, linha in linhas.items()}

    # --- Helpers privados ---

    def _carregar_referencias(self) -> None:
        nomes = [
            "outros_ativos", "outros_fundos", "mezanino", "senior",
            "ntn", "ltno", "nc", "vccri", "pddcri", "tesouraria",
        ]
        for nome in nomes:
            setattr(self, f"df_{nome}", self._dataframes.get(nome, pd.DataFrame()))

        df_tes = self._dataframes.get("tesouraria", pd.DataFrame())
        if not df_tes.empty:
            self.saldo_tesouraria = df_tes["Valor"].values[0]

    def _carregar_contas_singulare(self) -> None:
        df_cp = self._dataframes.get("contas_pagar", pd.DataFrame())
        if df_cp.empty:
            return
        idx_cat = df_cp.columns.get_loc("Descrição") if "Descrição" in df_cp.columns else 3
        idx_val = df_cp.columns.get_loc("Valor") if "Valor" in df_cp.columns else 9
        df_cp = df_cp.rename(
            columns={df_cp.columns[idx_cat]: "CATEGORIA", df_cp.columns[idx_val]: "Valor"}
        )
        self.df_contas_filtrado = self._agrupar_contas(df_cp, "CATEGORIA", "Valor")
        self._popular_taxas(self.df_contas_filtrado)
        self.pdd = self.recuperar_valor_carteira_coluna("PDD", 11)

    def acrescentar_contas_cotas(self, *codigos: str) -> None:
        self.codigos_cotas.extend(codigos)

    def recuperar_valor_carteira_coluna(
        self,
        codigo: str,
        coluna_valor: int,
        coluna_descricao: str = "Carteira Diária",
        df: pd.DataFrame | None = None,
    ) -> Any:
        df = df if df is not None else self.dataframe
        try:
            return df[df[coluna_descricao] == codigo].values[0, coluna_valor]
        except Exception:
            logger.info(f"'{codigo}' não encontrado.")
            return 0

    def somar_coluna_dataframe(self, codigo: str, coluna: str) -> float:
        try:
            return self._dataframes[codigo][coluna].sum()
        except Exception:
            logger.info(f"'{codigo}' não encontrado.")
            return 0.0

    def salvar_novos_codigos(
        self, path: str, novos_codigos: pd.DataFrame, nome_planilha: str = "DICIONARIO_CATEGORIA"
    ) -> None:
        import xlwings as xw  # import tardio – dependência opcional

        if novos_codigos.empty:
            return
        app = xw.App(visible=False)
        try:
            wb = xw.Book(path)
            ws = wb.sheets[nome_planilha]
            ultima_linha = ws.range("A" + str(ws.cells.last_cell.row)).end("up").row + 1
            dados = novos_codigos[["Código"]].copy()
            dados["CATEGORIA"] = "VALIDAR"
            ws.range(f"A{ultima_linha}").options(index=False, header=False).value = dados.values
            wb.save()
            logger.info(f"{len(novos_codigos)} novos códigos adicionados.")
        finally:
            app.quit()


# ---------------------------------------------------------------------------
# CarteiraPORTOFINO
# ---------------------------------------------------------------------------

class CarteiraPORTOFINO(_MixinParseBRL, CarteiraBase):
    """Administradora Portofino – planilhas 'Page 1/2/3', engine openpyxl."""

    def __init__(self, path_carteira: str | None = None) -> None:
        super().__init__(path_carteira)
        self.dataframe_1: pd.DataFrame | None = None
        self.dataframe_2: pd.DataFrame | None = None
        self.dataframe_3: pd.DataFrame | None = None
        self.df_contas_receber: pd.DataFrame | None = None
        self.df_contas_receber_filtrado: pd.DataFrame | None = None

    # --- Interface obrigatória ---

    def carregar_dados(self, aba="CD_ATUAL") -> None:
        self._validar_path()
        try:
            self.dataframe_1 = pd.read_excel(self.path_carteira, sheet_name="Page 1", engine="openpyxl")
            self.dataframe_2 = pd.read_excel(self.path_carteira, sheet_name="Page 2", engine="openpyxl")
            try:
                self.dataframe_3 = pd.read_excel(self.path_carteira, sheet_name="Page 3", engine="openpyxl")
            except Exception:
                self.dataframe_3 = self.dataframe_2.copy()

            self._carregar_data_portofino()
            self._dataframes = self._processar_planilha()
            self._carregar_contas_portofino()
        except Exception as exc:
            raise RuntimeError(f"Erro ao carregar CarteiraPORTOFINO: {exc}") from exc

    def _processar_planilha(self, aba="CD_ATUAL") -> dict[str, pd.DataFrame]:
        df = self.dataframe_2.reset_index(drop=True)
        categorias = {
            "contas_pagar": "Contas a Pagar",
            "contas_receber": "Contas a Receber",
            "fim_contas_receber": "Total Contas a Receber",
        }
        linhas = self._encontrar_linhas(df, categorias, "Unnamed: 1")
        secoes_carteira: dict[str, pd.DataFrame] = {}
        secoes_carteira["contas_pagar"] = _extrair_secao(df, linhas["contas_pagar"] + 1, linhas["contas_receber"] - 1)
        secoes_carteira["contas_receber"] = _extrair_secao(df, linhas["contas_receber"], linhas["fim_contas_receber"] + 1)
        return secoes_carteira

    # --- Helpers privados ---

    def _carregar_data_portofino(self) -> None:
        try:
            self.data = datetime.strptime(self.dataframe_2.iloc[4, 8], "%d/%m/%Y").date()
        except Exception:
            self.data = None

    def _carregar_contas_portofino(self) -> None:
        df_cp = self._dataframes.get("contas_pagar", pd.DataFrame())
        if df_cp.empty:
            return
        df_cp = df_cp.rename(columns={df_cp.columns[26]: "Valor", df_cp.columns[1]: "DESCRIÇÃO"})
        df_cp["Valor"] = df_cp["Valor"].apply(_converter_moeda)
        self.df_contas_filtrado = self._agrupar_contas(df_cp, "DESCRIÇÃO", "Valor")
        self._popular_taxas(self.df_contas_filtrado, coluna="DESCRIÇÃO")

    def recuperar_valor_carteira(
        self, df: pd.DataFrame, codigo: str, coluna: int
    ) -> float:
        try:
            return df[df["Unnamed: 1"] == codigo].values[0, coluna]
        except Exception:
            logger.info(f"'{codigo}' não encontrado.")
            return 0.0

    def recuperar_valor_por_coluna(
        self, df: pd.DataFrame, codigo: str, coluna_codigo: str, coluna_valor: int
    ) -> float:
        try:
            return df[df[coluna_codigo] == codigo].values[0, coluna_valor]
        except Exception:
            logger.info(f"'{codigo}' não encontrado.")
            return 0.0

    def recuperar_valor_descricao(self, col_codigo: str, descricao: str, col_valor: int) -> float:
        try:
            return self.dataframe_1[self.dataframe_1[col_codigo] == descricao].values[0, col_valor]
        except Exception:
            return 0.0
