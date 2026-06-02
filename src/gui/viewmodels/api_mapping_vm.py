"""
ApiMappingViewModel — lógica de negócio para a página de mapeamento de API.

Responsabilidades:
  1. Listar fundos que possuem doc_fundo_api.
  2. Consultar a API e caminhar recursivamente no JSON para extrair atributos.
  3. Carregar o mapeamento existente e calcular o status de cada atributo.
  4. Exportar o mapeamento visual para o formato JSON salvo em mapeamentos/*.json.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal, Slot

from src.core.logger import get_logger

logger = get_logger(__name__)

MAPEAMENTOS_DIR = Path(__file__).resolve().parents[3] / "mapeamentos"


# ---------------------------------------------------------------------------
# Utilidade: walker recursivo de JSON → lista de caminhos
# ---------------------------------------------------------------------------

def _walk_json(obj: Any, prefix: str = "") -> list[dict]:
    """
    Percorre recursivamente o JSON e extrai todos os "caminhos folha".

    Para valores escalares: retorna o caminho com notação de ponto.
    Para listas de dicts homogêneas: detecta as chaves internas e
    oferece filtros (ex: papel=A VENCER → valorPresente).

    Retorna lista de dicts com estrutura de payload de ApiAttrChip.
    """
    resultados: list[dict] = []

    if isinstance(obj, dict):
        for key, val in obj.items():
            novo_prefix = f"{prefix}.{key}" if prefix else key
            if isinstance(val, dict):
                resultados.extend(_walk_json(val, novo_prefix))
            elif isinstance(val, list):
                resultados.extend(_walk_list(val, novo_prefix))
            elif val is not None:
                resultados.append(_payload_escalar(novo_prefix, val))

    return resultados


def _walk_list(lst: list, prefix: str) -> list[dict]:
    """Extrai atributos de uma lista de dicts, gerando entradas filtráveis."""
    resultados = []

    # Filtra apenas dicts
    dicts = [item for item in lst if isinstance(item, dict)]
    if not dicts:
        return resultados

    # Detecta chave candidata a filtro (chave com valores string variados)
    todas_chaves = set()
    for d in dicts:
        todas_chaves.update(d.keys())

    chave_filtro: str | None = None
    for chave in ("papel", "tipo", "nome", "categoria", "historico", "descricao", "ordem"):
        if chave in todas_chaves:
            valores = {d.get(chave) for d in dicts if isinstance(d.get(chave), (str, int))}
            if 1 < len(valores) <= 20:
                chave_filtro = chave
                break

    if chave_filtro:
        # Uma entrada por valor único da chave filtro
        valores_unicos = sorted({d.get(chave_filtro) for d in dicts if isinstance(d.get(chave_filtro), (str, int))})

        for val_filtro in valores_unicos:
            # Dicts que correspondem ao filtro
            candidatos = [d for d in dicts if d.get(chave_filtro) == val_filtro]
            if not candidatos:
                continue
            cand = candidatos[0]
            
            # Percorre o objeto candidato para extrair todos os sub-caminhos (nested)
            sub_resultados = _walk_json(cand, prefix="")
            
            for sub in sub_resultados:
                campo_val = sub["caminho_json"]
                if campo_val == chave_filtro:
                    continue # Pula o próprio campo usado como filtro
                    
                # UX: No caso de pagar e receber, queremos apenas as variáveis cujo caminho final contenha 'valorTotal' (ex: valores.valorTotal)
                if ("receber" in prefix.lower() or "pagar" in prefix.lower()) and "valortotal" not in campo_val.lower():
                    continue

                val_real = sub["valor_retornado"]
                # Apenas extraímos para escalares numéricos na interface
                if isinstance(val_real, (int, float)):
                    label = f"{prefix}[{chave_filtro}={val_filtro}].{campo_val}"
                    resultados.append({
                        "caminho_json":      prefix,
                        "chave_filtro_json": chave_filtro,
                        "valor_filtro_json": str(val_filtro),
                        "campo_valor_json":  campo_val,
                        "label":             label,
                        "valor_retornado":   val_real,
                    })
    else:
        # Sem filtro detectado — trata cada dict como sub-objeto
        sample = dicts[0] if dicts else {}
        resultados.extend(_walk_json(sample, prefix))

    return resultados


def _payload_escalar(caminho: str, valor: Any = None) -> dict:
    return {
        "caminho_json":      caminho,
        "chave_filtro_json": None,
        "valor_filtro_json": None,
        "campo_valor_json":  None,
        "label":             caminho,
        "valor_retornado":   valor,
    }


# ---------------------------------------------------------------------------
# Worker assíncrono para consulta da API
# ---------------------------------------------------------------------------

class _ApiQuerySignals(QObject):
    concluido = Signal(list)    # lista de payloads extraídos
    erro      = Signal(str)


class _ApiQueryWorker(QRunnable):
    def __init__(self, fundo: str, data, signals: _ApiQuerySignals) -> None:
        super().__init__()
        self._fundo = fundo
        self._data  = data
        self.signals = signals
        self.setAutoDelete(True)

    @Slot()
    def run(self) -> None:
        try:
            from src.registry import REGISTRO
            from src.core.carteira_apex_api import CarteiraApexAPI

            cfg = REGISTRO.get(self._fundo.upper())
            if not cfg or not getattr(cfg, "doc_fundo_api", None):
                self.signals.erro.emit(f"Fundo '{self._fundo}' não tem integração API.")
                return

            carteira = CarteiraApexAPI.criar_da_api(cfg.doc_fundo_api, self._data)
            raw = carteira.raw_data
            base = raw.get("data", raw)
            atributos = _walk_json(base)

            # Adiciona opção sintética para a data de referência
            atributos.append({
                "caminho_json":      "data_referencia_carteira",
                "chave_filtro_json": None,
                "valor_filtro_json": None,
                "campo_valor_json":  None,
                "multiplicador":     1.0,
                "label":             "Data de Referência (atributo.data)",
                "fonte_real":        "atributo",
                "campo_real":        "data"
            })

            self.signals.concluido.emit(atributos)
        except Exception as exc:
            self.signals.erro.emit(str(exc))


# ---------------------------------------------------------------------------
# ViewModel principal
# ---------------------------------------------------------------------------

class ApiMappingViewModel(QObject):
    """
    ViewModel para a página de Mapeamento de API.

    Sinais:
        atributos_prontos(lista_de_payloads)  — consulta API concluída
        mapeamento_carregado(categorias_cd, categorias_mec)
        salvo(fundo)
        erro(mensagem)
    """

    atributos_prontos   = Signal(list)
    mapeamento_carregado = Signal(list, list)   # [(cat, [payloads]), ...]  cd, mec
    salvo               = Signal(str)
    erro                = Signal(str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._pool = QThreadPool.globalInstance()

    # ------------------------------------------------------------------
    # Consultas
    # ------------------------------------------------------------------

    def fundos_api(self) -> list[str]:
        from src.registry import REGISTRO
        return [
            k for k, v in REGISTRO.items()
            if getattr(v, "doc_fundo_api", None) and getattr(v, "administrador", "APEX").upper() == "APEX"
        ]

    def consultar_api(self, fundo: str, data) -> None:
        """Dispara consulta assíncrona à API. Emite atributos_prontos ou erro."""
        signals = _ApiQuerySignals(self)
        signals.concluido.connect(self.atributos_prontos)
        signals.erro.connect(self.erro)
        worker = _ApiQueryWorker(fundo, data, signals)
        self._pool.start(worker)

    # ------------------------------------------------------------------
    # Mapeamento existente
    # ------------------------------------------------------------------

    def carregar_mapeamento(self, fundo: str) -> None:
        """
        Lê o JSON de mapeamento existente e emite mapeamento_carregado
        com a estrutura: lista de (categoria, [payloads_api_json]).
        Itens não-api_json (fixo, custom, etc.) são incluídos com payloads=[].
        """
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
                if item.get("fonte") == "api_json":
                    caminho = item.get("caminho_json")
                    chave_filtro = item.get("chave_filtro_json")
                    valor_filtro = item.get("valor_filtro_json")
                    campo_valor = item.get("campo_valor_json")
                    if chave_filtro and valor_filtro:
                        label = f"{caminho}[{chave_filtro}={valor_filtro}].{campo_valor}"
                    else:
                        label = caminho
                        
                    payload = {
                        "caminho_json":      caminho,
                        "chave_filtro_json": chave_filtro,
                        "valor_filtro_json": valor_filtro,
                        "campo_valor_json":  campo_valor,
                        "multiplicador":     item.get("multiplicador", 1.0),
                        "label":             label,
                    }
                    resultado.append((cat, [payload]))
                elif item.get("fonte") == "atributo" and item.get("campo") == "data":
                    payload = {
                        "caminho_json":      "data_referencia_carteira", # Synthetic path
                        "chave_filtro_json": None,
                        "valor_filtro_json": None,
                        "campo_valor_json":  None,
                        "multiplicador":     1.0,
                        "label":             "Data de Referência (atributo.data)",
                        "fonte_real":        "atributo",
                        "campo_real":        "data"
                    }
                    resultado.append((cat, [payload]))
                else:
                    resultado.append((cat, []))
            return resultado

        cd  = _extrair(dados.get("mapeamento_cd",  []))
        mec = _extrair(dados.get("mapeamento_mec", []))
        self.mapeamento_carregado.emit(cd, mec)

    # ------------------------------------------------------------------
    # Calcular status dos chips
    # ------------------------------------------------------------------

    def calcular_status(
        self,
        atributos_api: list[dict],
        categorias: list[tuple[str, list[dict]]],
    ) -> dict[str, str]:
        """
        Dado os atributos detectados na API e as categorias mapeadas,
        retorna dict {label: status} onde status ∈ {"novo", "livre", "mapeado"}.
        """
        mapeados_labels = set()
        for _, payloads in categorias:
            for p in payloads:
                mapeados_labels.add(p.get("label", ""))

        status: dict[str, str] = {}
        for attr in atributos_api:
            label = attr.get("label", "")
            if label in mapeados_labels:
                status[label] = "mapeado"
            else:
                status[label] = "livre"

        return status

    # ------------------------------------------------------------------
    # Exportar e salvar
    # ------------------------------------------------------------------

    def salvar(
        self,
        fundo: str,
        cards_cd:  list,  # list[ExcelColumnCard]
        cards_mec: list,
    ) -> None:
        """
        Converte os cards em itens JSON e salva no arquivo de mapeamento.
        Itens sem atributos api_json são descartados (exceto fixo/outros
        que possam existir como base — por isso re-lemos o JSON original
        e substituímos apenas os itens api_json).
        """
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
                    # Mantém como fixo 0.0 se sem atributo
                    itens.append({"categoria": cat, "fonte": "fixo", "valor_fixo": 0.0})
                else:
                    # Processa todos os atributos (para acumular no engine)
                    for p in atrs:
                        if p.get("fonte_real") == "atributo":
                            # Mantém formato especial para atributo
                            item = {"categoria": cat, "fonte": "atributo", "campo": p.get("campo_real")}
                        else:
                            item = {"categoria": cat, "fonte": "api_json", "caminho_json": p["caminho_json"]}
                            if p.get("chave_filtro_json"):
                                item["chave_filtro_json"] = p["chave_filtro_json"]
                                item["valor_filtro_json"]  = str(p["valor_filtro_json"])
                                item["campo_valor_json"]   = p.get("campo_valor_json")
                        
                        if p.get("multiplicador") and p["multiplicador"] != 1.0:
                            item["multiplicador"] = p["multiplicador"]
                        itens.append(item)
            return itens

        from datetime import datetime
        from pathlib import Path as _Path
        historico = MAPEAMENTOS_DIR / "historico"
        historico.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        import shutil
        shutil.copy2(path, historico / f"{fundo}_{ts}.json")

        dados["mapeamento_cd"]  = _cards_para_itens(cards_cd)
        dados["mapeamento_mec"] = _cards_para_itens(cards_mec)

        try:
            path.write_text(json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8")
            self.salvo.emit(fundo)
        except OSError as exc:
            self.erro.emit(f"Erro ao salvar {fundo}.json: {exc}")
