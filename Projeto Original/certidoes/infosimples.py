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
    """Baixa o `site_receipts` (comprovante) da API para `caminho`.

    A Infosimples às vezes devolve o PDF original da fonte, mas às vezes
    "sintetiza" um recibo em HTML no lugar (quando o arquivo emitido pela fonte
    não é adequado pra visualização — ver documentação). Detecta pelo conteúdo
    (não pela URL) e converte o HTML pra PDF de verdade, senão salvaríamos HTML
    com extensão .pdf — abre errado em qualquer leitor."""
    recibos = resposta.get("site_receipts") or []
    if not recibos:
        return False
    caminho.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(recibos[0], timeout=60) as resp:
        dados = resp.read()
    if dados[:5] == b"%PDF-":
        caminho.write_bytes(dados)
    else:
        _html_para_pdf(dados.decode("utf-8", "replace"), caminho)
    return True


def _html_para_pdf(html: str, caminho: Path) -> None:
    """Converte um HTML (recibo sintetizado) num PDF de verdade, via Chromium
    headless — só para essa conversão pontual, não abre nenhum site."""
    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        navegador = pw.chromium.launch()
        try:
            page = navegador.new_page()
            page.set_content(html, wait_until="networkidle")
            page.pdf(path=str(caminho), format="A4", print_background=True)
        finally:
            navegador.close()


def primeiro_dado(resposta: dict) -> Optional[dict]:
    dados = resposta.get("data") or []
    return dados[0] if dados else None
