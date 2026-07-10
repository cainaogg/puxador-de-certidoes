"""Nova interface (Edge modo-app via eel) do Puxador de Certidões.

Renderiza `index.html` numa janela do Edge/Chrome do sistema (modo app, sem barra
do navegador) e liga os botões ao MOTOR já existente (engine/base/registry), sem
tocar no app.py (CustomTkinter). O JS consulta uma fila (`poll`) a cada ~150ms —
só chamadas JS→Python, robustas no eel.
"""

from __future__ import annotations

import os
import re
import shutil
import sys
import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import filedialog

import eel

# Permite importar o pacote `certidoes` (um nível acima desta pasta).
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from certidoes import ajuda, config, paths  # noqa: E402
from certidoes.base import (  # noqa: E402
    Status, _texto_pdf, documento_no_texto, identificar_certidao, juntar_pdfs,
    nome_documento, nome_para_tipo, renomear_com_validade, so_letras_numeros,
    verificar_vencimentos,
)
from certidoes.documento import DocumentoInvalido, TipoDoc, detectar  # noqa: E402
from certidoes.engine import _pasta_do_grupo, executar_lote, nomear_pasta_mae  # noqa: E402
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
def texto_ajuda():
    return ajuda.PROGRAMA


@eel.expose
def carregar_config():
    c = config.carregar()
    return {"modo": c.get("receita_modo", "navegador"),
            "token": c.get("infosimples_token", "")}


@eel.expose
def salvar_config(modo, token):
    config.salvar(receita_modo=modo, infosimples_token=(token or "").strip())


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
    elif nome == "escanear":
        threading.Thread(target=_escanear, daemon=True).start()
    elif nome == "validade":
        threading.Thread(target=_verificador, daemon=True).start()
    elif nome == "juntar":
        threading.Thread(target=_juntar, daemon=True).start()
    else:
        _emit({"t": "log", "m": f"[{nome}] — em breve nesta interface (próxima fase)."})


# ---- utilitários (Escanear / Validade / Juntar) — mesma lógica do app.py ---
def _pedir_pasta(titulo: str):
    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    caminho = filedialog.askdirectory(title=titulo, initialdir=str(PASTA_BASE))
    root.destroy()
    return caminho


def _id_por_nome(nome_arquivo: str):
    """Se o arquivo já começa com o nome de uma certidão conhecida, devolve o id."""
    for modulo in REGISTRY:
        for tipo in (TipoDoc.CNPJ, TipoDoc.CPF):
            base = nome_documento(nome_para_tipo(modulo.nome, tipo))
            if base and nome_arquivo.startswith(base):
                return modulo.id
    return None


def _escanear() -> None:
    origem = _pedir_pasta("Pasta com os PDFs para renomear")
    if not origem:
        return
    n = 0
    doc_pasta = None
    for pdf in sorted(Path(origem).glob("*.pdf")):
        try:
            texto = _texto_pdf(pdf)
        except Exception:  # noqa: BLE001
            continue
        mid = _id_por_nome(pdf.name) or identificar_certidao(texto)
        if not mid:
            continue
        doc = documento_no_texto(texto)
        doc_pasta = doc_pasta or doc
        novo = renomear_com_validade(pdf, por_id(mid), doc)
        if novo.name != pdf.name:
            _emit({"t": "log", "m": f"Renomeado: {pdf.name} → {novo.name}"})
            n += 1
    if doc_pasta is not None:
        nomear_pasta_mae(Path(origem), doc_pasta, lambda m: _emit({"t": "log", "m": m}))
    _emit({"t": "log", "m": f"Escanear: {n} arquivo(s) renomeado(s)."})


def _verificador() -> None:
    origem = _pedir_pasta("Pasta para verificar a validade")
    if not origem:
        return
    achados = verificar_vencimentos(Path(origem), dias=100000)
    if not achados:
        _emit({"t": "log", "m": "Verificador: nenhum PDF com validade no nome encontrado."})
        return
    _emit({"t": "log", "m": f"Verificador de Validade — {len(achados)} certidão(ões):"})
    for pdf, d, restam in achados:
        marca = "[VENCIDA]" if restam < 0 else f"[faltam {restam}d]"
        _emit({"t": "log", "m": f"  {marca} {d.strftime('%d.%m.%Y')} — {pdf.name}"})


def _juntar() -> None:
    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    arquivos = filedialog.askopenfilenames(
        title="Selecione os PDFs para juntar num só",
        initialdir=str(PASTA_BASE), filetypes=[("PDF", "*.pdf")])
    root.destroy()
    if len(arquivos) < 2:
        _emit({"t": "log", "m": "Juntar: selecione ao menos 2 PDFs."})
        return
    caminhos = [Path(a) for a in arquivos]
    novo = juntar_pdfs(caminhos, caminhos[0].parent)
    _emit({"t": "log", "m": f"Juntado ({len(caminhos)} PDFs) em: {novo}" if novo
           else "Juntar: não consegui gerar o PDF."})


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

    inicio_sessao = time.time()
    pendencias = []  # (modulo_id, número, pasta destino) p/ importar da Downloads
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
            resultados = executar_lote(doc, aplic, PASTA_BASE, on_log, on_status,
                                       _cancel, nasc, nome, documento_pasta=donos[i])
            grupo = _pasta_do_grupo(PASTA_BASE, donos[i])
            for r in resultados:
                if r.status is Status.MANUAL:
                    pendencias.append((r.modulo_id, doc.numero, grupo))
        _emit({"t": "log", "m": "\nConcluído."})
        if pendencias and not _cancel.is_set():
            threading.Thread(target=_importar_downloads,
                             args=(pendencias, inicio_sessao), daemon=True).start()
    except Exception as exc:  # noqa: BLE001
        _emit({"t": "log", "m": f"Erro geral: {type(exc).__name__}: {exc}"})
    finally:
        _emit({"t": "fim"})


def _importar_downloads(pendencias, inicio_sessao: float) -> None:
    """Move da Downloads os documentos manuais da Receita desta sessão (mesma lógica
    do app.py): recentes + reconhecidos + CNPJ/CPF batendo. Para ao achar tudo (~3 min)."""
    downloads = Path.home() / "Downloads"
    if not downloads.exists():
        return
    restantes = list(pendencias)
    vistos: set = set()
    fim = time.time() + 180
    _emit({"t": "log", "m": "Aguardando os documentos manuais na pasta Downloads (movo automaticamente)…"})
    while restantes and time.time() < fim and not _cancel.is_set():
        try:
            pdfs = sorted(downloads.glob("*.pdf"), key=lambda p: p.stat().st_mtime, reverse=True)
        except Exception:  # noqa: BLE001
            pdfs = []
        for pdf in pdfs:
            if pdf in vistos:
                continue
            try:
                if pdf.stat().st_mtime < inicio_sessao:
                    vistos.add(pdf)
                    continue
            except Exception:  # noqa: BLE001
                continue
            try:
                texto = _texto_pdf(pdf)
            except Exception:  # noqa: BLE001
                continue  # talvez ainda baixando
            vistos.add(pdf)
            mid = identificar_certidao(texto)
            docpdf = documento_no_texto(texto)
            if not mid or not docpdf:
                continue
            for pend in list(restantes):
                pmid, pnum, pasta = pend
                if mid == pmid and docpdf.numero == pnum:
                    try:
                        pasta.mkdir(parents=True, exist_ok=True)
                        destino = pasta / pdf.name
                        shutil.move(str(pdf), str(destino))
                        novo = renomear_com_validade(destino, por_id(mid), docpdf)
                        _emit({"t": "log", "m": f"Importei da Downloads: {novo.name}  →  {pasta.parent.name}"})
                    except Exception as exc:  # noqa: BLE001
                        _emit({"t": "log", "m": f"Não consegui importar {pdf.name}: {exc}"})
                    restantes.remove(pend)
                    break
        if restantes:
            time.sleep(3)
    if restantes:
        nomes = sorted({por_id(p[0]).nome for p in restantes})
        _emit({"t": "log", "m": "Importador: ainda não achei na Downloads: " + "; ".join(nomes)})


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
