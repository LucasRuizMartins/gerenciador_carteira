"""
ViewModel para o editor de mapeamentos JSON.
Lê/valida/salva os arquivos mapeamentos/*.json
integrando com o schema Pydantic do MappingEngine.
"""
from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QObject, Signal

from src.core.logger import get_logger

logger = get_logger(__name__)

# Diretório onde os JSONs de mapeamento estão armazenados
MAPEAMENTOS_DIR = Path(__file__).resolve().parents[3] / "mapeamentos"
HISTORICO_DIR   = MAPEAMENTOS_DIR / "historico"


class MappingViewModel(QObject):
    """
    Gerencia leitura, validação e persistência dos mapeamentos JSON.

    Sinais:
        dados_carregados(fundo, dados_dict)  — novo mapeamento foi carregado
        salvo(fundo)                          — mapeamento foi salvo
        erro(mensagem)                        — erro de validação ou IO
    """

    dados_carregados = Signal(str, dict)   # fundo, raw_dict
    salvo            = Signal(str)
    erro             = Signal(str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)

    # ------------------------------------------------------------------
    # Consulta
    # ------------------------------------------------------------------

    def fundos_com_mapeamento(self) -> list[str]:
        """Retorna fundos que têm arquivo JSON em mapeamentos/."""
        return sorted(
            p.stem for p in MAPEAMENTOS_DIR.glob("*.json")
            if p.is_file()
        )

    def todos_os_fundos(self) -> list[str]:
        """Retorna todos os fundos do registro (com ou sem JSON)."""
        from src.registry import REGISTRO
        return sorted(REGISTRO.keys())

    def carregar(self, fundo: str) -> None:
        """Lê o JSON do fundo e emite dados_carregados."""
        path = MAPEAMENTOS_DIR / f"{fundo}.json"
        if not path.exists():
            self.erro.emit(f"Arquivo não encontrado: {path.name}")
            return
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            self.dados_carregados.emit(fundo, data)
        except json.JSONDecodeError as exc:
            self.erro.emit(f"JSON inválido em {path.name}: {exc}")

    # ------------------------------------------------------------------
    # Validação
    # ------------------------------------------------------------------

    def validar(self, dados: dict) -> list[str]:
        """
        Valida os dados brutos contra o schema Pydantic do MappingEngine.
        Retorna lista de erros (vazia = válido).
        """
        from src.config.schemas import MapeamentoFundo
        try:
            MapeamentoFundo(**dados)
            return []
        except Exception as exc:
            # Extrai mensagens de erro do Pydantic
            erros = []
            try:
                for e in exc.errors():
                    loc = " → ".join(str(l) for l in e["loc"])
                    erros.append(f"{loc}: {e['msg']}")
            except Exception:
                erros.append(str(exc))
            return erros

    # ------------------------------------------------------------------
    # Persistência
    # ------------------------------------------------------------------

    def salvar(self, fundo: str, dados: dict) -> None:
        """
        1. Valida dados contra schema Pydantic.
        2. Faz backup da versão atual em mapeamentos/historico/.
        3. Escreve a nova versão no arquivo principal.
        Emite salvo() ou erro().
        """
        erros = self.validar(dados)
        if erros:
            self.erro.emit("Validação falhou:\n" + "\n".join(erros))
            return

        path = MAPEAMENTOS_DIR / f"{fundo}.json"
        self._fazer_backup(fundo, path)

        try:
            path.write_text(
                json.dumps(dados, ensure_ascii=False, indent=2),
                encoding="utf-8"
            )
            logger.info(f"Mapeamento de {fundo} salvo.")
            self.salvo.emit(fundo)
        except OSError as exc:
            self.erro.emit(f"Erro ao salvar {fundo}: {exc}")

    def _fazer_backup(self, fundo: str, path: Path) -> None:
        """Copia versão atual para historico/ antes de sobrescrever."""
        if not path.exists():
            return
        HISTORICO_DIR.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        dest = HISTORICO_DIR / f"{fundo}_{timestamp}.json"
        shutil.copy2(path, dest)
        logger.info(f"Backup criado: {dest.name}")

    def listar_backups(self, fundo: str) -> list[Path]:
        """Retorna lista de backups de um fundo, do mais recente ao mais antigo."""
        if not HISTORICO_DIR.exists():
            return []
        return sorted(
            HISTORICO_DIR.glob(f"{fundo}_*.json"),
            reverse=True
        )

    def restaurar_backup(self, fundo: str, backup_path: Path) -> None:
        """Restaura um backup, fazendo backup da versão atual primeiro."""
        try:
            dados = json.loads(backup_path.read_text(encoding="utf-8"))
            self.salvar(fundo, dados)
        except Exception as exc:
            self.erro.emit(f"Erro ao restaurar backup: {exc}")

    # ------------------------------------------------------------------
    # Helpers para a View
    # ------------------------------------------------------------------

    def fontes_disponiveis(self) -> list[str]:
        """Retorna os tipos de fonte suportados pelo engine."""
        return ["atributo", "taxa", "fixo", "custom", "valor_carteira", "cotas", "contas"]

    def novo_mapeamento(self, fundo: str) -> dict:
        """Retorna um template JSON mínimo para um novo fundo."""
        return {
            "versao": "1.0",
            "fundo": fundo,
            "administradora": "BRL",
            "mapeamento_cd": [
                {"categoria": "Data-Base", "fonte": "atributo", "campo": "data"}
            ],
            "mapeamento_mec": [
                {"categoria": "DATA", "fonte": "atributo", "campo": "data"}
            ]
        }
    def obter_caminho_fundo(self, fundo: str) -> str | None:
        """Retorna o caminho da pasta da carteira do fundo no sistema."""
        try:
            from src.registry import REGISTRO
            from src.config.settings import resolver_path_carteira
            
            config = REGISTRO.get(fundo)
            if not config:
                return None
            
            path_completo = resolver_path_carteira(config.chave_carteira)
            if path_completo:
                return str(Path(path_completo).parent)
            return None
        except Exception as exc:
            logger.error(f"Erro ao obter caminho do fundo {fundo}: {exc}")
            return None
    def obter_arquivo_fundo(self, fundo: str) -> str | None:
        """Retorna o caminho completo do arquivo da carteira do fundo."""
        try:
            from src.registry import REGISTRO
            from src.config.settings import resolver_path_carteira
            
            config = REGISTRO.get(fundo)
            if not config:
                return None
            
            return resolver_path_carteira(config.chave_carteira)
        except Exception as exc:
            logger.error(f"Erro ao obter arquivo do fundo {fundo}: {exc}")
            return None
