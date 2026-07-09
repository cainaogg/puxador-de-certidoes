"""Leitura de captcha de texto em imagem (offline, grátis) com ddddocr.

Usado no CNDT (TST), cujo captcha é 6 caracteres alfanuméricos desenhados sobre
círculos de ruído. A limpeza (abertura morfológica) remove as linhas finas dos
círculos e melhora muito o acerto do modelo.

Se as dependências (ddddocr/onnxruntime/opencv) não estiverem disponíveis,
`disponivel()` devolve False e o chamador cai no modo assistido — nada quebra.
"""

from __future__ import annotations

import base64
from typing import Optional

_ocr = None
_ok: Optional[bool] = None


def disponivel() -> bool:
    """True se dá para resolver captcha automaticamente (deps carregam)."""
    global _ok
    if _ok is None:
        try:
            import cv2  # noqa: F401
            import ddddocr  # noqa: F401
            import numpy  # noqa: F401
            _ok = True
        except Exception:  # noqa: BLE001
            _ok = False
    return _ok


def _motor():
    global _ocr
    if _ocr is None:
        import ddddocr
        _ocr = ddddocr.DdddOcr(show_ad=False)
    return _ocr


def _limpar(png: bytes) -> bytes:
    """Remove os círculos de ruído (linhas finas) preservando as letras."""
    import cv2
    import numpy as np

    img = cv2.imdecode(np.frombuffer(png, np.uint8), cv2.IMREAD_GRAYSCALE)
    _, binv = cv2.threshold(img, 180, 255, cv2.THRESH_BINARY_INV)
    aberto = cv2.morphologyEx(binv, cv2.MORPH_OPEN, np.ones((2, 2), np.uint8))
    return cv2.imencode(".png", cv2.bitwise_not(aberto))[1].tobytes()


def ler(png: bytes) -> str:
    """Texto lido do captcha (após limpar o ruído). '' se falhar."""
    try:
        return _motor().classification(_limpar(png)) or ""
    except Exception:  # noqa: BLE001
        return ""


def ler_data_uri(src: str) -> str:
    """Aceita 'data:image/...;base64,...' (o src da <img>) e devolve o texto."""
    if not src or "base64," not in src:
        return ""
    try:
        return ler(base64.b64decode(src.split("base64,", 1)[1]))
    except Exception:  # noqa: BLE001
        return ""
