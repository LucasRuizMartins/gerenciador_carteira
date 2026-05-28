import pandas as pd
from typing import Any
from src.core.carteira_json_base import CarteiraJSONBase
from src.core.logger import get_logger

logger = get_logger(__name__)

def parse_float_br(val: Any) -> float:
    """Converte valores decimais da API que podem vir formatados como string (ex: '5.367.824,88')."""
    if val is None:
        return 0.0
    if isinstance(val, (int, float)):
        return float(val)
    if isinstance(val, str):
        val_str = val.strip()
        if not val_str:
            return 0.0
        # Se contiver vírgula, assume formato BR (ex: "5.367.824,88" ou "1234,56")
        if "," in val_str:
            val_str = val_str.replace(".", "").replace(",", ".")
        try:
            return float(val_str)
        except ValueError:
            return 0.0
    return 0.0

class CarteiraApexAPI(CarteiraJSONBase):
    """
    Classe concreta para processamento de carteiras da Apex via API JSON.
    Recebe o payload do endpoint composicaoCarteira e converte no formato interno.
    """

    @classmethod
    def criar_da_api(cls, doc_fundo: str, data_referencia: Any) -> "CarteiraApexAPI":
        from src.services.apex_api import ApexAPI
        from src.services.apex_api.services import ComposicaoCarteiraParams
        import json
        from pathlib import Path
        
        env_path = Path("docs/API_APEX/env.json").resolve()
        with open(env_path, 'r', encoding='utf-8') as f:
            configuracoes = json.load(f)
            
        api = ApexAPI.from_config(configuracoes)
        params = ComposicaoCarteiraParams(
            doc_fundo=doc_fundo,
            data=data_referencia,
        )
        dados = api.relatorios.get_composicao_carteira(params)
        
        instance = cls(raw_data=dados)
        # Prioriza a data selecionada pelo usuário para o relatório
        instance.data = data_referencia
        instance.carregar_dados()
        return instance

    def _processar_json(self) -> None:
        """
        Popula os atributos e DataFrames mapeados a partir do JSON da Apex.
        O payload esperado está em self.raw_data.
        """
        # A raiz costuma vir encapsulada em 'data' ou pode vir direto. 
        # Vamos tratar caso a chave raiz 'data' exista
        base = self.raw_data.get("data", self.raw_data)

        # 1. Atributos Simples
        # Só preenche do JSON se ainda não estiver definido (ex: via criar_da_api)
        if not self.data:
            self.data = self._json_get("dataPosicao")
            
        self.pdd = self._extrair_pdd(base)
        self.a_vencer = self._extrair_dc(base, "A VENCER")
        self.vencido = self._extrair_dc(base, "VENCIDO")
        
        # Tesouraria (Caixa)
        self.saldo_tesouraria = parse_float_br(self._json_get("data.posicaoCaixa.total.totalValorTotal", 0.0))
            
        self.valor_di = self._extrair_valor_di(base)
        self.outros_valores_pagar = 0.0
        self.outros_valores_receber = 0.0

        # 2. Construção de DataFrames para manter compatibilidade com MappingEngine
        self._construir_dfs_contas(base)
        self._construir_df_cotas_superiores(base)

        # 3. Extração específica da Cota Subordinada
        # Geralmente a 'posicaoRentabilidade' no topo do JSON da Apex refere-se à classe Subordinada
        self.valor_subordinada = parse_float_br(self._json_get("data.posicaoRentabilidade.valorTotal", 0.0))

        # 4. Cálculo do PL Total (Ativos + Passivos)
        self.patrimonio_total = self._calcular_pl(base)

        # 4. Taxas e Despesas Diretas (fallback para o mapping antigo)
        self._extrair_taxas_diretas()

    def _extrair_pdd(self, base: dict) -> float:
        try:
            return parse_float_br(base["posicaoOutros"]["posicaoPDD"]["total"]["totalValorTotal"])
        except (KeyError, TypeError):
            return 0.0

    def _extrair_dc(self, base: dict, papel: str) -> float:
        try:
            posicoes = base["posicaoOutros"]["posicaoDC"]["posicoes"]
            for p in posicoes:
                if isinstance(p, dict) and p.get("papel") == papel:
                    return parse_float_br(p.get("valorPresente", 0.0))
        except (KeyError, TypeError):
            pass
        return 0.0

    def _extrair_valor_di(self, base: dict) -> float:
        """Extrai o valor de cotas em outros fundos, como o FI BRL2314."""
        try:
            for tipo_fundo in base.get("posicaoCotas", {}).get("posicoesPorTipoFundo", []):
                for p in tipo_fundo.get("posicoes", []):
                    papel = str(p.get("papel", "")).upper()
                    if "BRL2314" in papel:
                        return float(p.get("valorTotal", 0.0))
        except (KeyError, TypeError, AttributeError):
            pass
        return 0.0

    def _construir_dfs_contas(self, base: dict) -> None:
        """
        Constrói self.df_contas_filtrado (A Pagar) e self.df_contas_receber_filtrado
        com as colunas 'Histórico' e 'Valor Total' para manter compatibilidade
        com o método recuperar_contas da CarteiraBase.
        """
        # Contas a Pagar
        pagar = []
        try:
            valores_pagar = base["valoresPagar"]["valoresPorHistorico"]
            for vp in valores_pagar:
                nome = vp.get("nome", "")
                valor_total = vp.get("total", {}).get("totalValorTotal", 0.0)
                pagar.append({"Histórico": nome, "Valor Total": valor_total})
        except (KeyError, TypeError):
            pass
        self.df_contas_filtrado = pd.DataFrame(pagar)

        # Contas a Receber
        receber = []
        try:
            valores_receber = base["valoresReceber"]["valoresPorHistorico"]
            for vr in valores_receber:
                nome = vr.get("nome", "")
                valor_total = vr.get("total", {}).get("totalValorTotal", 0.0)
                receber.append({"Histórico": nome, "Valor Total": valor_total})
        except (KeyError, TypeError):
            pass
        self.df_contas_receber_filtrado = pd.DataFrame(receber)

    def _construir_df_cotas_superiores(self, base: dict) -> None:
        """
        Constrói self.df_cotas_superiores com colunas Ordem, Valor Cota e Valor Total.
        """
        cotas = []
        try:
            posicoes = base["posicaoCotaSuperior"]["posicoes"]
            for c in posicoes:
                cotas.append({
                    "Ordem": c.get("ordem"),
                    "Valor Cota": c.get("valorCota", 0.0),
                    "Valor Total": c.get("valorTotal", 0.0),
                    "Qtde. Total": c.get("quantidadeTotal", 0.0)
                })
        except (KeyError, TypeError):
            pass
        self.df_cotas_superiores = pd.DataFrame(cotas)

    def _calcular_pl(self, base: dict) -> float:
        """
        Soma ativos e passivos para encontrar o PL (Patrimônio Líquido).
        """
        ativos = 0.0
        try:
            ativos += parse_float_br(base.get("posicaoOutros", {}).get("posicaoDC", {}).get("total", {}).get("totalValorPresente", 0.0))
            ativos += parse_float_br(base.get("posicaoCotas", {}).get("total", {}).get("totalValorTotal", 0.0))
            ativos += parse_float_br(base.get("valoresReceber", {}).get("total", {}).get("totalValorTotal", 0.0))
            ativos += parse_float_br(base.get("posicaoCaixa", {}).get("total", {}).get("totalValorTotal", 0.0))
        except (TypeError, ValueError):
            pass

        passivos = 0.0
        try:
            passivos += parse_float_br(base.get("posicaoOutros", {}).get("posicaoPDD", {}).get("total", {}).get("totalValorTotal", 0.0))
            passivos += parse_float_br(base.get("valoresPagar", {}).get("total", {}).get("totalValorTotal", 0.0))
        except (TypeError, ValueError):
            pass

        return ativos + passivos # PDD e Contas a Pagar já vêm negativos no JSON

    def _extrair_taxas_diretas(self) -> None:
        """
        Compatibilidade com fontes do tipo 'taxa' no mapping antigo, que buscam 
        atributos como valor_administracao, valor_taxa_auditoria, etc.
        """
        self.valor_administracao = 0.0
        self.valor_taxa_gestao = 0.0
        self.valor_taxa_consultoria = 0.0
        self.valor_taxa_auditoria = 0.0
        self.valor_taxa_custodia = 0.0
        self.valor_taxa_cvm = 0.0
        self.valor_anbima = 0.0
        self.recebiveis_credito = 0.0
        self.outros_valores_pagar = 0.0
        self.outros_valores_receber = 0.0
        
        # --- A PAGAR ---
        if self.df_contas_filtrado is not None and not self.df_contas_filtrado.empty:
            self.valor_administracao = self.recuperar_contas("TAXA DE ADMINISTRAÇÃO", self.df_contas_filtrado)
            self.valor_taxa_gestao = self.recuperar_contas("TAXA DE GESTÃO", self.df_contas_filtrado)
            self.valor_taxa_consultoria = self.recuperar_contas("TAXA DE CONSULTORIA", self.df_contas_filtrado)
            self.valor_taxa_auditoria = self.recuperar_contas("DESPESA DE AUDITORIA", self.df_contas_filtrado)
            self.valor_taxa_custodia = self.recuperar_contas("TAXA DE CUSTÓDIA", self.df_contas_filtrado)
            
            # Taxas que podem vir no A Pagar
            self.valor_taxa_cvm += self.recuperar_contas("TAXA CVM", self.df_contas_filtrado)
            self.valor_anbima += self.recuperar_contas("TAXA ANBIMA", self.df_contas_filtrado)
            self.valor_anbima += self.recuperar_contas("DESPESA - ANBIMA", self.df_contas_filtrado)
            
            # Calcula dinamicamente outros valores a pagar (tudo que sobrou nas contas a pagar)
            especificas_pagar = [
                "TAXA DE ADMINISTRAÇÃO", "TAXA DE GESTÃO", "TAXA DE CONSULTORIA", 
                "DESPESA DE AUDITORIA", "TAXA DE CUSTÓDIA", "TAXA CVM", "TAXA ANBIMA", "DESPESA - ANBIMA"
            ]
            total_pagar = self.df_contas_filtrado["Valor Total"].sum()
            total_especificas_pagar = sum(self.recuperar_contas(esp, self.df_contas_filtrado) for esp in especificas_pagar)
            self.outros_valores_pagar = total_pagar - total_especificas_pagar

        # --- A RECEBER ---
        if hasattr(self, 'df_contas_receber_filtrado') and self.df_contas_receber_filtrado is not None and not self.df_contas_receber_filtrado.empty:
            # Taxas que podem vir no A Receber
            self.valor_taxa_cvm += self.recuperar_contas("TAXA CVM", self.df_contas_receber_filtrado)
            self.valor_anbima += self.recuperar_contas("TAXA ANBIMA", self.df_contas_receber_filtrado)
            self.valor_anbima += self.recuperar_contas("DESPESA - ANBIMA", self.df_contas_receber_filtrado)
            
            # Recebíveis e outras específicas
            # Usando escape manual para parênteses no Regex
            self.recebiveis_credito += self.recuperar_contas("RECEBÍVEIS", self.df_contas_receber_filtrado)

            # Calcula dinamicamente outros valores a receber (tudo que sobrou nas contas a receber)
            especificas_receber = [
                "TAXA CVM", "TAXA ANBIMA", "DESPESA - ANBIMA", "RECEBÍVEIS"
            ]
            total_receber = self.df_contas_receber_filtrado["Valor Total"].sum()
            total_especificas_receber = sum(self.recuperar_contas(esp, self.df_contas_receber_filtrado) for esp in especificas_receber)
            self.outros_valores_receber = total_receber - total_especificas_receber

    def recuperar_contas(self, categoria: str, df: pd.DataFrame, coluna_descricao: str = "Histórico", coluna_valor: str = "Valor Total") -> float:
        """
        Retorna o valor da *categoria* no DataFrame de contas filtrado.
        Compatível com a interface original da _MixinParseBRL.
        """
        try:
            filtro = df[coluna_descricao].str.contains(categoria, case=False, na=False)
            resultado = df.loc[filtro, coluna_valor]
            return float(resultado.sum())
        except Exception:
            return 0.0

    def recuperar_valor_carteira(self, codigo: str, coluna: int) -> float:
        """
        Retorna o valor da cota para MEC, mas API JSON não tem isso estruturado assim.
        Implementação stub para não quebrar. Para a Virtus, MEC usa cotas (99, 98) 
        que não batem neste método, ou usa valor_carteira para Subordinada que precisará 
        de lógica específica se houver.
        """
        try:
            base = self.raw_data.get("data", self.raw_data)
            rentabilidade = base.get("posicaoRentabilidade", {})
            
            # Caso especial: Subordinada na MEC usa esse método originalmente.
            if codigo == "Qtde. Cota":
                return float(rentabilidade.get("cotas", 0.0))
                
            if codigo == "Valor da Cota Líquida":
                val_cota = rentabilidade.get("valorCota") or rentabilidade.get("valorCotaFechamento")
                if val_cota is not None:
                    return float(val_cota)
                
                # Fallback: calcula valorTotal / cotas
                valor_total = float(rentabilidade.get("valorTotal", 0.0))
                cotas = float(rentabilidade.get("cotas", 0.0))
                if cotas > 0:
                    return valor_total / cotas
                return 0.0
        except Exception:
            pass
        return 0.0
