import logging
from datetime import date, datetime, timedelta
from typing import Any

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .config import ApexConfig

logger = logging.getLogger(__name__)


class TokenExpiredError(Exception):
    pass


class ApexAuthClient:
    """Responsável exclusivamente por obter e cachear o token de autenticação."""

    _TOKEN_ENDPOINT = "/api/auth"
    _TOKEN_MARGIN_SECONDS = 60  # renova 1 min antes de expirar

    def __init__(self, config: ApexConfig) -> None:
        self._config = config
        self._token: str | None = None
        self._expires_at: datetime | None = None

    @property
    def token(self) -> str:
        if self._is_token_valid():
            return self._token  # type: ignore[return-value]
        return self._refresh_token()

    def _is_token_valid(self) -> bool:
        if not self._token or not self._expires_at:
            return False
        return datetime.utcnow() < self._expires_at - timedelta(seconds=self._TOKEN_MARGIN_SECONDS)

    def _refresh_token(self) -> str:
        url = self._config.base_url + self._TOKEN_ENDPOINT
        logger.debug("Obtendo novo token em %s", url)

        response = requests.post(
            url,
            auth=(self._config.client_id, self._config.client_secret),
            timeout=10,
        )
        response.raise_for_status()

        payload = response.json()
        self._token = payload["idToken"]

        # Usa expiração retornada pela API ou assume 1 hora
        expires_in = payload.get("expiresIn", 3600)
        self._expires_at = datetime.utcnow() + timedelta(seconds=expires_in)

        logger.info("Token renovado. Expira em %s segundo(s).", expires_in)
        return self._token


class ApexHTTPClient:
    """
    Cliente HTTP base: monta sessão com retry, injeta headers padrão
    e expõe métodos get/post genéricos.
    """

    def __init__(self, config: ApexConfig, auth_client: ApexAuthClient) -> None:
        self._config = config
        self._auth = auth_client
        self._session = self._build_session()

    # ------------------------------------------------------------------
    # Configuração interna
    # ------------------------------------------------------------------

    def _build_session(self) -> requests.Session:
        session = requests.Session()

        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET", "POST"],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("https://", adapter)
        session.mount("http://", adapter)
        return session

    def _build_headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._auth.token}",
            "x-api-key": self._config.x_api_key,
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

    def _full_url(self, endpoint: str) -> str:
        return self._config.base_url + endpoint

    # ------------------------------------------------------------------
    # Métodos públicos
    # ------------------------------------------------------------------

    def get(self, endpoint: str, params: dict | None = None, **kwargs) -> Any:
        return self._request("GET", endpoint, params=params, **kwargs)

    def post(self, endpoint: str, json: dict | None = None, **kwargs) -> Any:
        return self._request("POST", endpoint, json=json, **kwargs)

    def _request(self, method: str, endpoint: str, **kwargs) -> Any:
        url = self._full_url(endpoint)
        logger.debug("%s %s | params=%s", method, url, kwargs.get("params"))

        response = self._session.request(
            method,
            url,
            headers=self._build_headers(),
            timeout=kwargs.pop("timeout", 15),
            **kwargs,
        )

        self._handle_response_errors(response)
        return response.json()

    @staticmethod
    def _handle_response_errors(response: requests.Response) -> None:
        if response.status_code == 401:
            raise TokenExpiredError("Token expirado ou inválido (401).")
        if response.status_code == 403:
            raise PermissionError("Acesso negado — verifique a x-api-key (403).")
        response.raise_for_status()