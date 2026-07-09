"""Cliente simples da API da Infosimples (usado só pela Receita, modo 'api').

O token vem das Configurações (config.json -> infosimples_token). Só usa a
biblioteca padrão (urllib).
"""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Optional

from . import config

BASE = "https://api.infosimples.com/api/v2/consultas/"


class InfosimplesErro(Exception):
    """Falha ao chamar a API (token ausente, rede, HTTP, etc.)."""


def token_configurado() -> bool:
    return bool(config.carregar().get("infosimples_token", "").strip())


def consultar(endpoint: str, *, timeout_api: int = 600, **params) -> dict:
    token = config.carregar().get("infosimples_token", "").strip()
    if not token:
        raise InfosimplesErro("Token da Infosimples não configurado (Configurações).")
    corpo = urllib.parse.urlencode(
        {"token": token, "timeout": timeout_api, **params}
    ).encode()
    req = urllib.request.Request(BASE + endpoint, data=corpo, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout_api / 3 + 60) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detalhe = exc.read().decode("utf-8", "replace")[:200]
        raise InfosimplesErro(f"HTTP {exc.code}: {detalhe}") from exc
    except Exception as exc:  # noqa: BLE001
        raise InfosimplesErro(f"Falha na conexão com a API: {exc}") from exc


def baixar_recibo(resposta: dict, caminho: Path) -> bool:
    recibos = resposta.get("site_receipts") or []
    if not recibos:
        return False
    caminho.parent.mkdir(parents=True, exist_ok=True)
    urllib.request.urlretrieve(recibos[0], str(caminho))
    return True


def primeiro_dado(resposta: dict) -> Optional[dict]:
    dados = resposta.get("data") or []
    return dados[0] if dados else None
