from dataclasses import dataclass


@dataclass(frozen=True)
class ApexConfig:
    base_url: str
    client_id: str
    client_secret: str
    x_api_key: str

    @classmethod
    def from_dict(cls, cfg: dict) -> "ApexConfig":
        return cls(
            base_url=cfg["base_url_apex_dev"],
            client_id=cfg["clientId"],
            client_secret=cfg["clientSecret"],
            x_api_key=cfg["x_api"],
        )