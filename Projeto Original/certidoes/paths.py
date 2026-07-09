"""Resolução de caminhos que funciona rodando do código OU empacotado (.exe).

Quando o programa vira um executável (PyInstaller), os dados que o usuário grava
(downloads, config, token) devem ficar AO LADO do .exe, e os recursos embutidos
(a extensão em vendor/) ficam dentro do pacote (_MEIPASS). Fora do .exe, tudo
fica na raiz do projeto, como antes.
"""

from __future__ import annotations

import sys
from pathlib import Path

_RAIZ_CODIGO = Path(__file__).resolve().parent.parent


def _congelado() -> bool:
    return bool(getattr(sys, "frozen", False))


def base_dados() -> Path:
    """Pasta gravável (downloads, config, token): ao lado do .exe ou a raiz do projeto."""
    if _congelado():
        return Path(sys.executable).resolve().parent
    return _RAIZ_CODIGO


def base_recursos() -> Path:
    """Pasta dos recursos embutidos (vendor/): _MEIPASS no .exe, raiz no código."""
    if _congelado():
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent))
    return _RAIZ_CODIGO
