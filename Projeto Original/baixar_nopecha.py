"""Baixa a extensão NopeCHA (resolve captchas) para ``vendor/nopecha_ext``.

A extensão é distribuída publicamente pela NopeCHA no GitHub e **não contém
nenhum dado pessoal** — a versão gratuita funciona sem chave. Rode uma vez,
depois de clonar o projeto:

    python baixar_nopecha.py

Sem a extensão o programa continua funcionando: os captchas passam para o modo
assistido (você os resolve na janela do navegador que abre).
"""

from __future__ import annotations

import io
import urllib.request
import zipfile
from pathlib import Path

# Versão fixada (a mesma usada no desenvolvimento), para comportamento idêntico.
VERSAO = "0.6.1"
URL = (
    "https://github.com/NopeCHALLC/nopecha-extension/releases/download/"
    f"{VERSAO}/chromium_automation.zip"
)
DESTINO = Path(__file__).resolve().parent / "vendor" / "nopecha_ext"


def baixar(destino: Path = DESTINO) -> int:
    if (destino / "manifest.json").exists():
        print(f"NopeCHA já está em {destino} — nada a fazer.")
        return 0
    print(f"Baixando NopeCHA {VERSAO}…")
    try:
        with urllib.request.urlopen(URL, timeout=60) as resp:
            dados = resp.read()
        zf = zipfile.ZipFile(io.BytesIO(dados))
    except Exception as exc:  # noqa: BLE001
        print(f"Não consegui baixar ({exc}).")
        print("Tudo bem: o programa funciona sem ela (captcha em modo assistido).")
        return 1
    destino.mkdir(parents=True, exist_ok=True)
    zf.extractall(destino)
    print(f"Pronto! Extensão extraída em {destino}")
    return 0


if __name__ == "__main__":
    raise SystemExit(baixar())
