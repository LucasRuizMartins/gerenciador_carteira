"""
FileMappingViewModel — lógica de negócio para a página de mapeamento de arquivos locais (CSV/XLSX).

Responsabilidades:
  1. Listar todos os fundos do registro.
  2. Consultar o caminho do arquivo local e carregá-lo em segundo plano usando a classe de Carteira correta.
  3. Extrair variáveis (linhas, colunas, cotas, contas, atributos) do arquivo carregado.
  4. Carregar e salvar os mapeamentos JSON em mapeamentos/*.json.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal, Slot
import pandas as pd

from src.core.logger import get_logger

logger = get_logger(__name__)

MAPEAMENTOS_DIR = Path(__file__).resolve().parents[3] / "mapeamentos"


# ---------------------------------------------------------------------------
# Worker assíncrono para carregamento da Carteira local
# ---------------------------------------------------------------------------

class _FileLoadSignals(QObject):
    concluido = Signal(list)    # lista de variáveis extraídas
    erro      = Signal(str)


class _FileLoadWorker(QRunnable):
    def __init__(self, fundo: str, signals: _FileLoadSignals) -> None:
        super().__init__()
        self._fundo = fundo  # chave no REGISTRO
        self.signals = signals
        self.setAutoDelete(True)

    @staticmethod
    def _resolver_path_carteira_com_fallback(chave_registro: str, cfg) -> str | None:
        """
        Resolve o caminho da carteira, usando múltiplas estratégias:
        1. Pelo campo 'carteiras' do config.json (via resolver_path_carteira)
        2. Pelo campo 'caminho_carteira' do fundos_api.json usando resolver_path()
        3. Como caminho absoluto direto (se o valor já for absoluto e existir)
        """
        from src.config.settings import resolver_path_carteira, resolver_path
        from pathlib import Path as _Path
        
        # Estratégia 1: Pelo config.json['carteiras']
        try:
            p = resolver_path_carteira(cfg.chave_carteira)
            if p and _Path(p).exists():
                return p
        except Exception:
            pass
        
        # Estratégia 2 e 3: Pelo fundos_api.json (campo caminho_carteira)
        from src.registry import listar_fundos_externos
        externos = listar_fundos_externos()
        
        # Busca por múltiplas chaves de referência
        chaves_busca = {
            chave_registro.upper().strip(),
            cfg.chave_carteira.upper().strip(),
        }
        if hasattr(cfg, 'chave_gerencial'):
            chaves_busca.add(cfg.chave_gerencial.upper().strip())
        
        for ext in externos:
            chave_ext = ext.get("chave", "").upper().strip()
            chave_ger_ext = ext.get("chave_gerencial", "").upper().strip()
            
            if chave_ext not in chaves_busca and chave_ger_ext not in chaves_busca:
                continue
                
            caminho_rel = ext.get("caminho_carteira", "").strip()
            if not caminho_rel:
                continue
                
            try:
                # Se for caminho absoluto, usa diretamente
                p_abs = _Path(caminho_rel)
                if p_abs.is_absolute() and p_abs.exists():
                    return str(p_abs)
                
                # Usa resolver_path (USERPROFILE / root_dir / caminho_rel)
                # que é o mesmo padrão usado pelo resto do sistema
                abs_path = resolver_path(caminho_rel)
                if _Path(abs_path).exists():
                    return abs_path
                    
                # Fallback: direto a partir de USERPROFILE sem root_dir
                import os
                perfil_usuario = os.environ.get("USERPROFILE", os.path.expanduser("~"))
                abs_path2 = str(_Path(perfil_usuario) / caminho_rel)
                if _Path(abs_path2).exists():
                    return abs_path2
            except Exception as exc:
                logger.debug(f"Tentativa de resolver caminho '{caminho_rel}' falhou: {exc}")
                
        return None

    @staticmethod
    def _detectar_aba_carteira(path_carteira: str) -> str:
        """Detecta automaticamente a aba correta do arquivo Excel/XLSB."""
        import pandas as pd
        # Ordem de preferência de abas a tentar
        ABAS_PREFERIDAS = [
            "CD_ATUAL", "CD_Atual", "cd_atual",
            "Carteira Diária", "Carteira Diaria", "CARTEIRA DIÁRIA",
            "Sheet1", "Plan1", "Planilha1",
        ]
        try:
            # Detecta o engine correto
            engine = "pyxlsb" if str(path_carteira).lower().endswith(".xlsb") else None
            kwargs = {"engine": engine} if engine else {}
            xl = pd.ExcelFile(path_carteira, **kwargs)
            abas = xl.sheet_names
            # Primeiro tenta as abas preferidas em ordem
            for aba_pref in ABAS_PREFERIDAS:
                for aba_real in abas:
                    if str(aba_real).strip().upper() == aba_pref.upper():
                        return aba_real
            # Se nenhuma preferida encontrada, retorna a primeira aba
            return abas[0] if abas else "CD_ATUAL"
        except Exception as exc:
            logger.warning(f"_detectar_aba_carteira: erro ao ler abas de '{path_carteira}': {exc}")
            return "CD_ATUAL"

    @Slot()
    def run(self) -> None:
        try:
            from src.registry import REGISTRO

            cfg = REGISTRO.get(self._fundo.upper())
            if not cfg:
                self.signals.erro.emit(f"Fundo '{self._fundo}' não encontrado no Registro.")
                return

            path_carteira = self._resolver_path_carteira_com_fallback(self._fundo, cfg)
            if not path_carteira or not Path(path_carteira).exists():
                self.signals.erro.emit(
                    f"Arquivo da carteira diária não encontrado.\n\n"
                    f"Certifique-se de que:\n"
                    f"1. O caminho da Carteira Diária foi preenchido na tela de Fundos\n"
                    f"2. O arquivo existe no caminho configurado\n"
                    f"3. O OneDrive/SharePoint está sincronizado\n\n"
                    f"Chave do fundo: {cfg.chave_carteira}"
                )
                return

            logger.info(f"Carregando carteira de {self._fundo} a partir de {path_carteira}...")
            
            # Detecta a aba automaticamente
            aba = self._detectar_aba_carteira(path_carteira)
            logger.info(f"Aba detectada para {self._fundo}: '{aba}'")

            # Instancia a classe de carteira correta para o fundo e carrega os dados
            carteira = cfg.classe_carteira(path_carteira)
            
            # Popula as palavras-chave de contas a pagar para agrupar corretamente
            from src.config.settings import obter_contas_pagar_fundo
            contas_pagar = obter_contas_pagar_fundo(cfg.chave_fundo_efetiva)
            if contas_pagar:
                carteira.acrescentar_contas_pagar(*contas_pagar)
                
            carteira.carregar_dados(aba=aba)

            # Extrai as variáveis da carteira parseada
            variaveis = []

            # 1. Atributos Globais
            ATRIBUTOS_MAP = {
                "patrimonio_total": "Patrimônio Total (PL)",
                "saldo_tesouraria": "Saldo em Tesouraria (C/C)",
                "pdd": "PDD (Provisão de Perdas)",
                "a_vencer": "Direitos a Vencer",
                "vencido": "Direitos Vencidos",
            }
            for attr_name, label_pt in ATRIBUTOS_MAP.items():
                if hasattr(carteira, attr_name):
                    val = getattr(carteira, attr_name)
                    if isinstance(val, (int, float)):
                        variaveis.append({
                            "fonte": "atributo",
                            "campo": attr_name,
                            "label": f"{label_pt} ({attr_name})",
                            "valor_retornado": val,
                            "grupo": "Atributos"
                        })

            # 2. Taxas da Carteira
            TAXAS_MAP = {
                "valor_administracao": "Taxa de Administração",
                "valor_anbima": "Taxa ANBIMA",
                "valor_taxa_auditoria": "Taxa de Auditoria",
                "valor_taxa_custodia": "Taxa de Custódia",
                "valor_taxa_gestao": "Taxa de Gestão",
                "valor_taxa_cvm": "Taxa CVM",
                "valor_taxa_performance": "Taxa de Performance",
                "valor_selic": "Taxa SELIC",
                "valor_cetip": "Taxa CETIP",
                "valor_liq_banco": "Banco Liquidante",
                "valor_di": "Total Renda Fixa (DI)",
            }
            for attr_name, label_pt in TAXAS_MAP.items():
                if hasattr(carteira, attr_name):
                    val = getattr(carteira, attr_name)
                    if isinstance(val, (int, float)):
                        variaveis.append({
                            "fonte": "taxa",
                            "campo": attr_name,
                            "label": f"{label_pt} ({attr_name})",
                            "valor_retornado": val,
                            "grupo": "Taxas"
                        })

            # 3. Linhas e Seções da Planilha (valor_carteira e soma_secao)
            usou_secoes = False
            dataframes = getattr(carteira, "_dataframes", {})
            if dataframes:
                # Filtra seções válidas
                secoes_validas = {k: df for k, df in dataframes.items() if df is not None and not df.empty}
                # Ignora as seções de contas/provisões e tesouraria pois são tratadas separadamente
                secoes_ignorar = {"contas_pagar", "contas", "contas_receber", "tesouraria"}
                secoes_validas = {k: df for k, df in secoes_validas.items() if k not in secoes_ignorar}
                
                if secoes_validas:
                    usou_secoes = True
                    for secao_nome, df in secoes_validas.items():
                        # A. Cria a "Soma Seção" para cada coluna numérica da seção
                        for c_idx, col in enumerate(df.columns):
                            series_num = pd.to_numeric(df.iloc[:, c_idx], errors='coerce')
                            if not series_num.dropna().empty:
                                try:
                                    col_sum = float(series_num.sum())
                                    variaveis.append({
                                        "fonte": "soma_secao",
                                        "secao": secao_nome,
                                        "coluna": col,
                                        "label": f"Soma Seção: {secao_nome} [{col}]",
                                        "valor_retornado": col_sum,
                                        "grupo": f"Planilha: {secao_nome}"
                                    })
                                except Exception:
                                    pass
                                    
                        # B. Descobre a coluna que serve de chave (código do ativo) na seção
                        col_chave = None
                        col_chave_idx = None
                        # Busca prioritária de colunas de identificadores
                        nomes_busca = ["código", "codigo", "ativo", "papel", "descrição", "descricao", "histórico", "historico", "série", "serie", "emissão", "emissao", "nome"]
                        for n in nomes_busca:
                            for idx_col, c in enumerate(df.columns):
                                if str(c).strip().lower() == n:
                                    col_chave = c
                                    col_chave_idx = idx_col
                                    break
                            if col_chave is not None:
                                break
                        if col_chave is None and len(df.columns) > 0:
                            col_chave = df.columns[0]
                            col_chave_idx = 0
                            
                        if col_chave_idx is not None:
                            for idx, row in df.iterrows():
                                chave_etl = row.iloc[col_chave_idx]
                                if pd.isna(chave_etl):
                                    continue
                                if isinstance(chave_etl, (int, float)):
                                    chave_etl = str(int(chave_etl))
                                else:
                                    chave_etl = str(chave_etl).strip()
                                    
                                if not chave_etl or chave_etl.startswith("Unnamed:") or chave_etl.lower() == "nan" or chave_etl.lower() == "totais:":
                                    continue
                                    
                                # Para cada outra coluna (que seja numérica)
                                for c_idx, col in enumerate(df.columns):
                                    if c_idx == col_chave_idx:
                                        continue
                                    val = row.iloc[c_idx]
                                    if pd.isna(val):
                                        continue
                                    try:
                                        val_num = float(val)
                                    except (ValueError, TypeError):
                                        continue
                                        
                                    variaveis.append({
                                        "fonte": "valor_carteira",
                                        "chave_etl": chave_etl,
                                        "coluna": col,
                                        "label": f"{chave_etl} [{col}]",
                                        "valor_retornado": val_num,
                                        "grupo": f"Planilha: {secao_nome}"
                                    })
                                    
            if not usou_secoes:
                # Fallback anterior para o caso de não haver sub-seções mapeadas
                df_plan = getattr(carteira, "dataframe", None)
                if df_plan is not None and not df_plan.empty:
                    col_chave = df_plan.columns[0]
                    current_headers = None
                    
                    for idx, row in df_plan.iterrows():
                        row_values = row.tolist()
                        row_str = [str(x).strip().lower() for x in row_values if not pd.isna(x)]
                        
                        # Identifica se é linha de cabeçalho
                        matching_cols = 0
                        for x in row_str:
                            if any(t == x or x.startswith(t) or x.endswith(t) for t in ["descri", "papel", "cod", "administr", "emit", "operac", "venc", "qtd", "taxa", "valor", "pl", "vlr", "pu", "ativo"]):
                                matching_cols += 1
                        is_header = matching_cols >= 2
                        
                        if is_header:
                            current_headers = [str(x).strip() if not pd.isna(x) else f"Col {i}" for i, x in enumerate(row_values)]
                            continue
                        
                        chave_etl = row[col_chave]
                        if pd.isna(chave_etl) or not isinstance(chave_etl, str):
                            continue
                        chave_etl = chave_etl.strip()
                        if not chave_etl or chave_etl.startswith("Unnamed:"):
                            continue
                        
                        for c_idx in range(1, len(row)):
                            val = row.iloc[c_idx]
                            if pd.isna(val) or not isinstance(val, (int, float)):
                                continue
                            
                            col_id = c_idx
                            if current_headers and c_idx < len(current_headers):
                                col_name = current_headers[c_idx]
                                if col_name.startswith("Unnamed:") or not col_name.strip():
                                    col_name = f"Col {c_idx}"
                                else:
                                    col_id = col_name
                            else:
                                col_label = df_plan.columns[c_idx]
                                col_name = str(col_label) if not str(col_label).startswith("Unnamed:") else f"Col {c_idx}"
                                if not col_name.startswith("Col "):
                                    col_id = col_name
                            
                            variaveis.append({
                                "fonte": "valor_carteira",
                                "chave_etl": chave_etl,
                                "coluna": col_id,
                                "label": f"{chave_etl} [{col_name}]",
                                "valor_retornado": float(val),
                                "grupo": f"Planilha: {chave_etl}"
                            })

            # 4. Cotas (df_cotas_superiores)
            df_cotas = getattr(carteira, "df_cotas_superiores", None)
            if df_cotas is not None and not df_cotas.empty:
                col_ordem = "Ordem" if "Ordem" in df_cotas.columns else df_cotas.columns[0]
                for idx, row in df_cotas.iterrows():
                    ordem_val = row[col_ordem]
                    if pd.isna(ordem_val):
                        continue
                    try:
                        ordem_int = int(ordem_val)
                    except (ValueError, TypeError):
                        continue

                    # Adiciona as colunas financeiras da cota
                    for col_name in ("Valor Total", "Qtde. Total", "Valor Cota", "Amortiz. Dia"):
                        if col_name in df_cotas.columns:
                            val = row[col_name]
                            if not pd.isna(val) and isinstance(val, (int, float)):
                                variaveis.append({
                                    "fonte": "cotas",
                                    "ordens": [ordem_int],
                                    "coluna_valor": col_name,
                                    "label": f"Cota Ordem {ordem_int} — {col_name}",
                                    "valor_retornado": float(val),
                                    "grupo": f"Cotas (Ordem {ordem_int})"
                                })

            # 5. Contas e Despesas (df_contas_filtrado e df_contas_receber_filtrado)
            for df_attr, df_label, df_code in [
                ("df_contas_filtrado", "Contas a Pagar", "df_contas_filtrado"),
                ("df_contas_receber_filtrado", "Contas a Receber", "df_contas_receber_filtrado")
            ]:
                df_c = getattr(carteira, df_attr, pd.DataFrame())
                if df_c is not None and not df_c.empty:
                    # Detecta coluna de descrição
                    col_desc = "Histórico" if "Histórico" in df_c.columns else None
                    if not col_desc:
                        col_desc = "Historico" if "Historico" in df_c.columns else df_c.columns[0]
                    
                    # Detecta coluna de valor
                    col_val = "Valor Total" if "Valor Total" in df_c.columns else None
                    if not col_val:
                        col_val = "Valor" if "Valor" in df_c.columns else df_c.columns[-1]

                    for idx, row in df_c.iterrows():
                        filtro_val = row[col_desc]
                        val = row[col_val]
                        if pd.isna(filtro_val) or not isinstance(filtro_val, str) or pd.isna(val):
                            continue
                        filtro_val = filtro_val.strip()
                        if not filtro_val:
                            continue

                        variaveis.append({
                            "fonte": "contas",
                            "filtro": filtro_val,
                            "dataframe": df_code,
                            "label": f"{df_label}: {filtro_val}",
                            "valor_retornado": float(val),
                            "grupo": df_label
                        })

            logger.info(f"Sucesso ao ler carteira de {self._fundo}. {len(variaveis)} variáveis detectadas.")
            self.signals.concluido.emit(variaveis)
        except Exception as exc:
            logger.error(f"Erro ao carregar arquivo de {self._fundo}: {exc}", exc_info=True)
            self.signals.erro.emit(str(exc))


# ---------------------------------------------------------------------------
# ViewModel Principal
# ---------------------------------------------------------------------------

class FileMappingViewModel(QObject):
    variaveis_prontas   = Signal(list)
    mapeamento_carregado = Signal(list, list)   # [(cat, [payloads]), ...]  cd, mec
    salvo               = Signal(str)
    erro                = Signal(str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._pool = QThreadPool.globalInstance()

    def todos_os_fundos(self) -> list[str]:
        """Retorna todos os fundos que possuem arquivo de carteira diária configurado."""
        from src.registry import REGISTRO, listar_fundos_externos
        from src.config.settings import configuracoes_validadas

        # Chaves de carteiras mapeadas em config.json
        try:
            cfg_settings = configuracoes_validadas()
            carteiras_config = set(cfg_settings.carteiras.keys())
        except Exception:
            carteiras_config = set()

        # Chaves dos fundos externos com caminho_carteira preenchido
        externos_com_carteira = set()
        for ext in listar_fundos_externos():
            if ext.get("caminho_carteira", "").strip():
                externos_com_carteira.add(ext.get("chave", "").upper().strip())

        resultado = []
        for chave, cfg in REGISTRO.items():
            chave_upper = chave.upper().strip()
            chave_carteira_upper = cfg.chave_carteira.upper().strip()
            
            # Inclui se:
            # 1. A chave do REGISTRO está em carteiras_config
            # 2. A chave_carteira (chave_gerencial) está em carteiras_config
            # 3. É fundo externo com caminho_carteira preenchido
            if (chave_upper in carteiras_config
                    or chave_carteira_upper in carteiras_config
                    or chave_upper in externos_com_carteira):
                resultado.append(chave)
        return sorted(resultado)


    def obter_caminho_fundo(self, fundo: str) -> str | None:
        try:
            from src.registry import REGISTRO
            config = REGISTRO.get(fundo)
            if not config:
                return None
            return _FileLoadWorker._resolver_path_carteira_com_fallback(fundo, config)
        except Exception as exc:
            logger.error(f"Erro ao obter caminho do fundo {fundo}: {exc}")
            return None


    def carregar_arquivo_carteira(self, fundo: str) -> None:
        """Lança a carga assíncrona do arquivo de carteira."""
        signals = _FileLoadSignals(self)
        signals.concluido.connect(self.variaveis_prontas)
        signals.erro.connect(self.erro)
        worker = _FileLoadWorker(fundo, signals)
        self._pool.start(worker)

    def carregar_mapeamento(self, fundo: str) -> None:
        """Lê o arquivo mapeamentos/{FUNDO}.json e reconstrói as categorias para CD/MEC."""
        path = MAPEAMENTOS_DIR / f"{fundo}.json"
        if not path.exists():
            self.erro.emit(f"Arquivo de mapeamento não encontrado: {fundo}.json")
            return

        try:
            dados = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            self.erro.emit(f"Erro ao ler {fundo}.json: {exc}")
            return

        def _extrair(mapeamento: list[dict]) -> list[tuple[str, list[dict]]]:
            resultado = []
            for item in mapeamento:
                cat = item.get("categoria", "")
                fonte = item.get("fonte", "fixo")
                
                payload = dict(item)
                
                # Restaura rótulos visuais para chips dos badges no card
                if fonte in ("atributo", "taxa"):
                    payload["label"] = f"{cat} ({payload.get('campo')})"
                elif fonte == "valor_carteira":
                    payload["label"] = f"{payload.get('chave_etl')} [Col {payload.get('coluna')}]"
                elif fonte == "cotas":
                    ordens = payload.get("ordens")
                    col_val = payload.get("coluna_valor")
                    payload["label"] = f"Cotas Ordem {ordens} — {col_val}"
                elif fonte == "contas":
                    df_label = "Despesas" if payload.get("dataframe") == "df_contas_filtrado" else "Recebíveis"
                    payload["label"] = f"Contas: {payload.get('filtro')} ({df_label})"
                elif fonte == "fixo":
                    payload["label"] = f"Fixo: {payload.get('valor_fixo')}"
                elif fonte == "custom":
                    payload["label"] = f"Custom: {payload.get('nome_funcao')}"
                elif fonte == "soma_secao":
                    payload["label"] = f"Soma Seção: {payload.get('secao')} [Col {payload.get('coluna')}]"
                elif fonte == "api_json":
                    payload["label"] = f"API JSON: {payload.get('caminho_json')}"
                else:
                    payload["label"] = cat

                resultado.append((cat, [payload]))
            return resultado

        cd  = _extrair(dados.get("mapeamento_cd",  []))
        mec = _extrair(dados.get("mapeamento_mec", []))
        self.mapeamento_carregado.emit(cd, mec)

    def calcular_status(
        self,
        variaveis: list[dict],
        categorias: list[tuple[str, list[dict]]],
    ) -> dict[str, str]:
        """Calcula se as variáveis estão 'mapeadas' ou 'livres'."""
        from src.gui.widgets.excel_column_card import _obter_chave_payload

        mapeadas_keys = set()
        for _, payloads in categorias:
            for p in payloads:
                mapeadas_keys.add(_obter_chave_payload(p))

        status: dict[str, str] = {}
        for var in variaveis:
            label = var.get("label", "")
            key = _obter_chave_payload(var)
            if key in mapeadas_keys:
                status[label] = "mapeado"
            else:
                status[label] = "livre"

        return status

    def salvar(
        self,
        fundo: str,
        cards_cd: list,
        cards_mec: list,
    ) -> None:
        """Escreve as regras de mapeamento dos cards de volta para o JSON."""
        path = MAPEAMENTOS_DIR / f"{fundo}.json"
        if not path.exists():
            self.erro.emit(f"Arquivo de mapeamento não encontrado: {fundo}.json")
            return

        try:
            dados = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            self.erro.emit(f"Erro ao ler {fundo}.json: {exc}")
            return

        def _cards_para_itens(cards: list) -> list[dict]:
            itens = []
            for card in cards:
                cat = card.categoria
                atrs = card.atributos_mapeados()
                if not atrs:
                    itens.append({"categoria": cat, "fonte": "fixo", "valor_fixo": 0.0})
                else:
                    for p in atrs:
                        fonte = p.get("fonte", "fixo")
                        item = {"categoria": cat, "fonte": fonte}
                        
                        # Mapeia cada propriedade conforme o schema Pydantic
                        if fonte in ("atributo", "taxa"):
                            item["campo"] = p.get("campo")
                        elif fonte == "valor_carteira":
                            item["chave_etl"] = p.get("chave_etl")
                            col_val = p.get("coluna")
                            try:
                                item["coluna"] = int(col_val)
                            except (ValueError, TypeError):
                                item["coluna"] = col_val
                        elif fonte == "cotas":
                            item["ordens"] = p.get("ordens")
                            item["coluna_valor"] = p.get("coluna_valor")
                            if p.get("agregacao"):
                                item["agregacao"] = p.get("agregacao")
                        elif fonte == "contas":
                            item["filtro"] = p.get("filtro")
                            if p.get("dataframe"):
                                item["dataframe"] = p.get("dataframe")
                        elif fonte == "fixo":
                            try:
                                item["valor_fixo"] = float(p.get("valor_fixo"))
                            except:
                                item["valor_fixo"] = p.get("valor_fixo")
                        elif fonte == "custom":
                            item["nome_funcao"] = p.get("nome_funcao")
                        elif fonte == "soma_secao":
                            item["secao"] = p.get("secao")
                            col_val = p.get("coluna")
                            try:
                                item["coluna"] = int(col_val)
                            except (ValueError, TypeError):
                                item["coluna"] = col_val
                        elif fonte == "api_json":
                            item["caminho_json"] = p.get("caminho_json")
                            if p.get("chave_filtro_json"):
                                item["chave_filtro_json"] = p.get("chave_filtro_json")
                            if p.get("valor_filtro_json") is not None:
                                item["valor_filtro_json"] = p.get("valor_filtro_json")
                            if p.get("campo_valor_json"):
                                item["campo_valor_json"] = p.get("campo_valor_json")

                        if p.get("multiplicador") and p["multiplicador"] != 1.0:
                            item["multiplicador"] = p["multiplicador"]
                        itens.append(item)
            return itens

        # Efetua backup histórico
        from datetime import datetime
        historico = MAPEAMENTOS_DIR / "historico"
        historico.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        import shutil
        shutil.copy2(path, historico / f"{fundo}_{ts}.json")

        dados["mapeamento_cd"]  = _cards_para_itens(cards_cd)
        dados["mapeamento_mec"] = _cards_para_itens(cards_mec)

        try:
            # Valida contra o Pydantic para segurança total
            from src.config.schemas import MapeamentoFundo
            MapeamentoFundo.model_validate(dados)

            path.write_text(json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8")
            self.salvo.emit(fundo)
        except Exception as exc:
            self.erro.emit(f"Erro de validação ou escrita ao salvar mapeamento: {exc}")
