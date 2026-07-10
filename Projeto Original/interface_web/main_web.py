"""Nova interface (Edge modo-app via eel) do Puxador de Certidões.

Renderiza `index.html` numa janela do Edge/Chrome do sistema (modo app, sem barra
do navegador) e liga os botões ao MOTOR já existente (engine/base/registry), sem
tocar no app.py (CustomTkinter). O JS consulta uma fila (`poll`) a cada ~150ms —
só chamadas JS→Python, robustas no eel.
"""

from __future__ import annotations

import os
import re
import sys
import threading
from pathlib import Path

import eel

# Permite importar o pacote `certidoes` (um nível acima desta pasta).
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from certidoes import ajuda, paths  # noqa: E402
from certidoes.base import Status, so_letras_numeros  # noqa: E402
from certidoes.documento import DocumentoInvalido, TipoDoc, detectar  # noqa: E402
from certidoes.engine import executar_lote  # noqa: E402
from certidoes.registry import REGISTRY, por_id  # noqa: E402

PASTA_BASE = paths.base_dados() / "downloads"
WEB = Path(__file__).resolve().parent

# Status do motor -> chave de estilo no JS (ver PILL no index.html).
_ST = {
    "pendente": "pendente", "executando": "baixando",
    "aguardando_captcha": "aguardando_captcha", "ok": "ok", "erro": "erro",
    "nao_aplicavel": "nao_aplicavel", "cancelado": "pendente",
    "manual": "manual", "ja_valida": "ja_valida",
}

_cancel = threading.Event()
_fila: list = []
_lock = threading.Lock()


def _emit(evt: dict) -> None:
    with _lock:
        _fila.append(evt)


# ---- chamadas JS -> Python -----------------------------------------------
@eel.expose
def poll():
    """O JS chama isto a cada ~150ms para pegar os updates (log/status/fim)."""
    with _lock:
        out = list(_fila)
        _fila.clear()
    return out


@eel.expose
def listar_certidoes():
    return [{"id": m.id, "label": m.nome,
             "desc": ajuda.CERTIDOES.get(m.id, m.descricao or ""),
             "impl": bool(m.implementado)} for m in REGISTRY]


@eel.expose
def iniciar(texto: str, ids) -> None:
    entries = _parse(texto or "")
    modulos = [por_id(i) for i in ids if por_id(i).implementado]
    if not entries:
        _emit({"t": "log", "m": "⚠ Informe ao menos um CPF ou CNPJ válido."})
        _emit({"t": "fim"})
        return
    if not modulos:
        _emit({"t": "log", "m": "⚠ Selecione ao menos uma certidão."})
        _emit({"t": "fim"})
        return
    _cancel.clear()
    threading.Thread(target=_rodar, args=(entries, modulos), daemon=True).start()


@eel.expose
def acao(nome: str) -> None:
    if nome == "cancelar":
        _cancel.set()
        _emit({"t": "log", "m": "Cancelamento solicitado (encerra após a certidão atual)."})
    elif nome == "abrir_pasta":
        PASTA_BASE.mkdir(parents=True, exist_ok=True)
        os.startfile(str(PASTA_BASE))  # type: ignore[attr-defined]
    else:
        _emit({"t": "log", "m": f"[{nome}] — em breve nesta interface (próxima fase)."})


# ---- execução (thread) ----------------------------------------------------
def _rodar(entries, modulos) -> None:
    def on_log(msg: str) -> None:
        _emit({"t": "log", "m": msg})

    def on_status(mid: str, valor) -> None:
        st = valor.status if hasattr(valor, "status") else valor
        _emit({"t": "status", "id": mid, "st": _ST.get(getattr(st, "value", str(st)), "pendente")})

    # Associa cada CPF ao CNPJ mais próximo acima (sócio → pasta do CNPJ).
    donos = []
    ultimo_cnpj = None
    for d, _n, _no in entries:
        if d.tipo is TipoDoc.CNPJ:
            ultimo_cnpj = d
            donos.append(d)
        else:
            donos.append(ultimo_cnpj if ultimo_cnpj is not None else d)

    try:
        for i, (doc, nasc, nome) in enumerate(entries):
            if _cancel.is_set():
                _emit({"t": "log", "m": "Cancelado pelo usuário."})
                break
            _emit({"t": "log", "m": f"\n===== {doc.formatado} ====="})
            aplic = [m for m in modulos if m.aplica_para(doc.tipo)]
            for m in modulos:
                chave = "pendente" if m in aplic else "nao_aplicavel"
                _emit({"t": "status", "id": m.id, "st": chave})
            if not aplic:
                _emit({"t": "log", "m": f"  (nenhuma certidão marcada se aplica a {doc.tipo.value.upper()})"})
                continue
            executar_lote(doc, aplic, PASTA_BASE, on_log, on_status,
                          _cancel, nasc, nome, documento_pasta=donos[i])
        _emit({"t": "log", "m": "\nConcluído."})
    except Exception as exc:  # noqa: BLE001
        _emit({"t": "log", "m": f"Erro geral: {type(exc).__name__}: {exc}"})
    finally:
        _emit({"t": "fim"})


def _parse(texto: str):
    out = []
    for raw in texto.splitlines():
        linha = raw.strip()
        if not linha:
            continue
        m = re.search(r"\b(\d{2}/\d{2}/\d{4})\b", linha)
        nasc = m.group(1) if m else ""
        resto = linha.replace(nasc, "") if nasc else linha
        try:
            doc = detectar(resto)
        except DocumentoInvalido:
            continue
        sem = resto.replace(doc.formatado, " ").replace(doc.numero, " ")
        out.append((doc, nasc, so_letras_numeros(sem)))
    return out


def main() -> None:
    eel.init(str(WEB))
    eel.start("index.html", mode="edge", size=(980, 680), port=0, block=True)


if __name__ == "__main__":
    main()
