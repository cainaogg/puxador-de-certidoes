"""Nova interface (Edge modo-app via eel) do Puxador de Certidões.

Copyright (C) 2026 Cainã Gomes Süffert
Licenciado sob a GNU Affero General Public License v3.0 (ou, à sua escolha,
qualquer versão posterior). Veja o arquivo LICENSE na raiz do repositório.

Renderiza `index.html` numa janela do Edge/Chrome do sistema (modo app, sem barra
do navegador) e liga os botões ao MOTOR já existente (engine/base/registry), sem
tocar no app.py (CustomTkinter). O JS consulta uma fila (`poll`) a cada ~150ms —
só chamadas JS→Python, robustas no eel.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import threading
import time
import tkinter as tk
import webbrowser
from pathlib import Path
from tkinter import filedialog

import eel
from playwright.sync_api import sync_playwright

# Rodando do código: permite importar `certidoes` (um nível acima). No .exe, o
# PyInstaller já embute o pacote — não mexe no path.
if not getattr(sys, "frozen", False):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from certidoes import ajuda, atualizacao, config, paths  # noqa: E402
from certidoes.base import (  # noqa: E402
    Status, _texto_pdf, documento_no_texto, identificar_certidao, juntar_pdfs,
    nome_base_modulo, nome_documento, renomear_com_validade, so_letras_numeros,
    verificar_vencimentos,
)
from certidoes.documento import DocumentoInvalido, TipoDoc, detectar  # noqa: E402
from certidoes.engine import (  # noqa: E402
    _abrir_contexto, _pasta_do_grupo, executar_lote, nomear_pasta_mae,
)
from certidoes.registry import REGISTRY, por_id  # noqa: E402

PASTA_BASE = paths.base_dados() / "downloads"

# Certidões que SEMPRE exigem o usuário (nenhuma tentativa automática — a Receita
# e a CGU bloqueiam automação/só têm hCaptcha Enterprise; a Consolidada do TCU
# tem um WAF que bloqueia qualquer navegador automatizado, mesmo com perfil
# "envelhecido" — testado). Em vez de interromper o lote espalhado, ficam para
# uma fila única no final (ver _rodar_fila_manual).
SEMPRE_MANUAL = {"receita_federal", "consulta_cnpj", "cgu_correcional", "tcu_consolidada_pj"}
# Pasta da UI: no .exe (onefile) fica em _MEIPASS/interface_web; no código, aqui.
WEB = (Path(getattr(sys, "_MEIPASS", "")) / "interface_web"
       if getattr(sys, "frozen", False) else Path(__file__).resolve().parent)

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
_rodando = threading.Lock()  # trava contra 2 lotes simultâneos (2 navegadores abertos)


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
    custom = (c.get("pasta_downloads_navegador") or "").strip()
    return {"modo": c.get("receita_modo", "navegador"),
            "modo_cnpj": c.get("consulta_cnpj_modo", "navegador"),
            "modo_tcu": c.get("tcu_consolidada_modo", "navegador"),
            "token": c.get("infosimples_token", ""),
            "accent": c.get("accent", "#3B82F6"),
            "tema": c.get("tema", "dark"),
            "pasta_downloads": str(custom or _pasta_downloads_padrao()),
            "pasta_downloads_custom": bool(custom)}


@eel.expose
def salvar_config(modo, modo_cnpj, modo_tcu, token):
    config.salvar(receita_modo=modo, consulta_cnpj_modo=modo_cnpj,
                  tcu_consolidada_modo=modo_tcu, infosimples_token=(token or "").strip())


@eel.expose
def escolher_pasta_downloads_navegador():
    escolhida = _pedir_pasta("Pasta onde seu navegador salva os downloads",
                              inicial=_pasta_downloads_navegador())
    if not escolhida:
        return None
    config.salvar(pasta_downloads_navegador=escolhida)
    return {"caminho": escolhida, "custom": True}


@eel.expose
def restaurar_pasta_downloads_navegador():
    config.salvar(pasta_downloads_navegador="")
    return {"caminho": str(_pasta_downloads_padrao()), "custom": False}


@eel.expose
def salvar_accent(cor):
    config.salvar(accent=cor)


@eel.expose
def salvar_tema(tema):
    config.salvar(tema=tema)


# --- Perfis de download (o "Padrão" é fixo/computado na interface) ---
@eel.expose
def listar_perfis():
    c = config.carregar()
    return {"perfis": c.get("perfis", {}), "ativo": c.get("perfil_ativo", "Padrão")}


@eel.expose
def salvar_perfil(nome, cnpj_ids, cpf_ids):
    nome = (nome or "").strip()
    if not nome or nome == "Padrão":  # "Padrão" é travado; nome vazio ignorado
        return
    perfis = dict(config.carregar().get("perfis", {}))
    perfis[nome] = {"cnpj": list(cnpj_ids or []), "cpf": list(cpf_ids or [])}
    config.salvar(perfis=perfis, perfil_ativo=nome)


@eel.expose
def remover_perfil(nome):
    if nome == "Padrão":
        return
    c = config.carregar()
    perfis = dict(c.get("perfis", {}))
    perfis.pop(nome, None)
    ativo = c.get("perfil_ativo", "Padrão")
    config.salvar(perfis=perfis, perfil_ativo=("Padrão" if ativo == nome else ativo))


@eel.expose
def definir_perfil_ativo(nome):
    config.salvar(perfil_ativo=(nome or "Padrão"))


@eel.expose
def listar_certidoes():
    def tags(m):
        vals = {t.value.upper() for t in getattr(m, "aceita", frozenset())}
        return [t for t in ("CNPJ", "CPF") if t in vals]  # CNPJ primeiro
    return [{"id": m.id, "label": ajuda.LABELS.get(m.id, m.nome),
             "desc": ajuda.CERTIDOES.get(m.id, m.descricao or ""),
             "site": bool(getattr(m, "url", "")),
             "impl": bool(m.implementado),
             "tags": tags(m)} for m in REGISTRY]


@eel.expose
def resumo_vencimentos(dias=15):
    """Certidões vencidas ou a vencer em `dias` na pasta padrão do programa — para
    o sino de notificações do Painel. Sempre olha PASTA_BASE (não pede pasta ao
    usuário, diferente do "Verificador" manual do menu, que continua livre para
    qualquer pasta).

    Cada item tem uma `chave` estável (caminho+data) usada para lembrar o que já
    foi visto/excluído (fica salvo em config.json, então persiste entre aberturas
    do programa) — excluídas somem da lista; vistas só param de contar no badge."""
    if not PASTA_BASE.exists():
        return []
    c = config.carregar()
    vistas = set(c.get("notif_vistas", []))
    excluidas = set(c.get("notif_excluidas", []))
    out = []
    for pdf, d, restam in verificar_vencimentos(PASTA_BASE, dias=dias):
        chave = f"{pdf}|{d.isoformat()}"
        if chave in excluidas:
            continue
        try:
            empresa = pdf.relative_to(PASTA_BASE).parts[0]
        except Exception:  # noqa: BLE001
            empresa = pdf.parent.name
        out.append({"chave": chave, "empresa": empresa, "arquivo": pdf.name,
                    "data": d.strftime("%d/%m/%Y"), "restam": restam,
                    "nova": chave not in vistas})
    return out


@eel.expose
def marcar_vencimentos_vistos(chaves):
    vistas = set(config.carregar().get("notif_vistas", []))
    vistas.update(chaves or [])
    config.salvar(notif_vistas=list(vistas))


@eel.expose
def excluir_vencimento(chave):
    excluidas = set(config.carregar().get("notif_excluidas", []))
    excluidas.add(chave)
    config.salvar(notif_excluidas=list(excluidas))


# --- Atualização do programa (sino) ---------------------------------------
@eel.expose
def verificar_atualizacao():
    """Checa o último release do GitHub em background — uma chamada de rede não
    pode travar a thread principal do eel (sem monkey-patch, ela bloqueia tudo).
    O resultado (se houver versão nova) chega pela fila de eventos (poll)."""
    def trabalho():
        info = atualizacao.verificar()
        if info:
            _emit({"t": "update_disponivel", **info})
    threading.Thread(target=trabalho, daemon=True).start()


@eel.expose
def baixar_atualizacao(info):
    """Baixa o .exe do release em background e avisa o progresso/fim pela fila."""
    def trabalho():
        try:
            def progresso(pct):
                _emit({"t": "update_progresso", "pct": pct})
            caminho = atualizacao.baixar(info["asset_url"], info.get("asset_tamanho", 0),
                                          on_progresso=progresso)
            config.salvar(atualizacao_pendente={
                "caminho": str(caminho), "versao": info.get("versao", ""), "relancar": False,
            })
            _emit({"t": "update_pronto", "versao": info.get("versao", "")})
        except Exception as exc:  # noqa: BLE001
            _emit({"t": "update_erro", "m": str(exc)})
    threading.Thread(target=trabalho, daemon=True).start()


@eel.expose
def marcar_relancar_apos_fechar():
    """Chamado pelo botão "Reiniciar" do aviso de atualização: marca para reabrir
    assim que a janela fechar (ver `_ao_fechar`, chamado por eel via close_callback)."""
    pendente = config.carregar().get("atualizacao_pendente")
    if pendente:
        pendente["relancar"] = True
        config.salvar(atualizacao_pendente=pendente)


@eel.expose
def forcar_saida():
    """Rede de segurança: se `window.close()` não fechar a janela (alguns
    navegadores restringem em modo-app), o JS chama isto para sair na força."""
    _aplicar_atualizacao_pendente()
    os._exit(0)


def _aplicar_atualizacao_pendente() -> None:
    pendente = config.carregar().get("atualizacao_pendente")
    if not pendente:
        return
    if Path(pendente["caminho"]).exists():
        atualizacao.agendar_substituicao(Path(pendente["caminho"]), pendente.get("relancar", False))
    config.salvar(atualizacao_pendente=None)


def _ao_fechar(page, sockets) -> None:
    """close_callback do eel: dispara quando uma janela/websocket fecha. Sem
    outras janelas abertas (`sockets` vazio), é o fechamento de verdade —
    aplica a atualização pendente (se houver) e encerra o processo."""
    if sockets:
        return
    _aplicar_atualizacao_pendente()
    os._exit(0)


@eel.expose
def listar_nomes():
    """Nomenclatura dos documentos (Configurações): nome padrão do programa e o
    personalizado (se houver) de cada certidão — para o editor na aba nova."""
    personalizados = config.carregar().get("nomes_personalizados", {})
    out = []
    for m in REGISTRY:
        padrao = nome_documento(m.nome)
        custom = (personalizados.get(m.id) or "").strip()
        out.append({"id": m.id, "label": ajuda.LABELS.get(m.id, m.nome),
                    "padrao": padrao, "atual": custom or padrao,
                    "personalizado": bool(custom)})
    return out


@eel.expose
def salvar_nome_personalizado(mid, nome):
    """Define o nome personalizado de um documento. Nome vazio remove a
    personalização (volta a usar o padrão)."""
    personalizados = dict(config.carregar().get("nomes_personalizados", {}))
    nome = (nome or "").strip()
    if nome:
        personalizados[mid] = nome
    else:
        personalizados.pop(mid, None)
    config.salvar(nomes_personalizados=personalizados)


@eel.expose
def escolher_pasta_processo():
    """Seletor de pasta (dentro de PASTA_BASE) para o botão "Atualizar processo":
    reconhece o CNPJ/CPF pelo nome da pasta, para refazer a busca desse documento.
    O motor já pula sozinho o que ainda está válido (certidao_valida_existente),
    então isso na prática só baixa o que venceu ou nunca saiu — não precisa de
    lógica nova para "achar o que falta"."""
    origem = _pedir_pasta("Pasta da empresa/pessoa para atualizar")
    if not origem:
        return {"ok": False}
    try:
        doc = detectar(Path(origem).name)
    except DocumentoInvalido:
        return {"ok": False, "erro": "Não reconheci um CNPJ/CPF válido no nome dessa pasta."}
    return {"ok": True, "numero": doc.formatado, "tipo": doc.tipo.value.upper()}


@eel.expose
def abrir_site(mid):
    url = getattr(por_id(mid), "url", "")
    if url:
        webbrowser.open(url)
    else:
        _emit({"t": "log", "m": "Esta certidão não tem site próprio para abrir."})


@eel.expose
def abrir_link(url):
    if url:
        webbrowser.open(url)


@eel.expose
def iniciar(texto: str, ids_cnpj, ids_cpf) -> None:
    entries = _parse(texto or "")
    # Listas separadas por tipo: o perfil ativo pode marcar a mesma certidão só
    # para CNPJ (ou só para CPF) — rodar tudo numa lista única ignorava isso e
    # emitia certidões pra um tipo de documento que o perfil não pedia.
    mods_cnpj = [por_id(i) for i in (ids_cnpj or []) if por_id(i).implementado]
    mods_cpf = [por_id(i) for i in (ids_cpf or []) if por_id(i).implementado]
    if not entries:
        _emit({"t": "log", "m": "⚠ Informe ao menos um CPF ou CNPJ válido."})
        _emit({"t": "fim"})
        return
    if not mods_cnpj and not mods_cpf:
        _emit({"t": "log", "m": "⚠ Selecione ao menos uma certidão."})
        _emit({"t": "fim"})
        return
    if not _rodando.acquire(blocking=False):
        # Já tem um lote rodando (ex.: clique duplo, ou "Atualizar processo" clicado
        # durante uma busca). Sem isso, dois navegadores abririam ao mesmo tempo.
        # NÃO emite "fim": o lote em andamento ainda vai terminar e emitir o dele —
        # emitir aqui reabilitaria o botão Buscar antes da hora.
        _emit({"t": "log", "m": "⚠ Já tem uma busca em andamento — aguarde terminar."})
        return
    _cancel.clear()
    threading.Thread(target=_rodar, args=(entries, mods_cnpj, mods_cpf), daemon=True).start()


@eel.expose
def acao(nome: str) -> None:
    if nome == "cancelar":
        _cancel.set()
        _emit({"t": "log", "m": "Cancelamento solicitado (encerra após a certidão atual)."})
    elif nome == "abrir_pasta":
        PASTA_BASE.mkdir(parents=True, exist_ok=True)
        # explorer.exe (processo separado) é confiável no .exe; os.startfile
        # roda numa greenlet do eel e às vezes não abre a janela (COM).
        try:
            subprocess.Popen(["explorer", str(PASTA_BASE)])
        except Exception:  # noqa: BLE001
            os.startfile(str(PASTA_BASE))  # type: ignore[attr-defined]
        _emit({"t": "log", "m": "Abrindo a pasta de downloads…"})
    elif nome == "escanear":
        threading.Thread(target=_escanear, daemon=True).start()
    elif nome == "juntar":
        threading.Thread(target=_juntar, daemon=True).start()
    else:
        _emit({"t": "log", "m": f"[{nome}] — em breve nesta interface (próxima fase)."})


# ---- utilitários (Escanear / Validade / Juntar) — mesma lógica do app.py ---
def _pedir_pasta(titulo: str, inicial=None):
    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    caminho = filedialog.askdirectory(title=titulo, initialdir=str(inicial or PASTA_BASE))
    root.destroy()
    return caminho


def _pasta_downloads_padrao() -> Path:
    return Path.home() / "Downloads"


def _pasta_downloads_navegador() -> Path:
    """Pasta onde o programa procura os PDFs baixados manualmente (Receita, Cartão
    CNPJ, Consulta Consolidada TCU) — a Downloads do Windows, ou a que o usuário
    escolheu em Configurações › Preferência de Download, se o navegador dele
    salvar em outro lugar."""
    custom = (config.carregar().get("pasta_downloads_navegador") or "").strip()
    return Path(custom) if custom else _pasta_downloads_padrao()


def _id_por_nome(nome_arquivo: str):
    """Se o arquivo já começa com o nome de uma certidão conhecida, devolve o id."""
    for modulo in REGISTRY:
        for tipo in (TipoDoc.CNPJ, TipoDoc.CPF):
            base = nome_base_modulo(modulo, tipo)
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
def _rodar(entries, mods_cnpj, mods_cpf) -> None:
    # União: pra zerar o status ("pendente"/"não aplicável") de toda linha
    # marcada, mesmo a que só vale pro outro tipo de documento desta mesma busca.
    modulos = list({m.id: m for m in (mods_cnpj + mods_cpf)}.values())

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
    # Vigia a pasta Downloads durante toda a sessão (não só no final): documentos
    # manuais (Receita, Cartão CNPJ, Consulta Consolidada TCU) são importados assim
    # que você baixar, mesmo enquanto o resto do lote ainda está rodando. Continua
    # de vigia por mais 3 min depois da sessão acabar (ver sessao_ativa.clear() no
    # finally), pra dar tempo de terminar o que ainda estava em aberto.
    pendencias: list = []  # (modulo_id, número, pasta destino) p/ importar da Downloads
    pendencias_lock = threading.Lock()
    sessao_ativa = threading.Event()
    sessao_ativa.set()

    def registrar_pendencia(modulo_id: str, numero: str, pasta) -> None:
        with pendencias_lock:
            pendencias.append((modulo_id, numero, pasta))

    threading.Thread(target=_importar_downloads,
                      args=(pendencias, pendencias_lock, sessao_ativa, inicio_sessao),
                      daemon=True).start()

    fila_manual = []  # (doc, nasc, nome, dono, [módulos sempre-manuais desta linha])
    try:
        for i, (doc, nasc, nome) in enumerate(entries):
            if _cancel.is_set():
                _emit({"t": "log", "m": "Cancelado pelo usuário."})
                break
            _emit({"t": "log", "m": f"\n===== {doc.formatado} ====="})
            modulos_do_tipo = mods_cnpj if doc.tipo is TipoDoc.CNPJ else mods_cpf
            aplic = [m for m in modulos_do_tipo if m.aplica_para(doc.tipo)]
            for m in modulos:
                chave = "pendente" if m in aplic else "nao_aplicavel"
                _emit({"t": "status", "id": m.id, "st": chave})
            if not aplic:
                _emit({"t": "log", "m": f"  (nenhuma certidão marcada se aplica a {doc.tipo.value.upper()})"})
                continue
            # As "sempre manuais" ficam para a fila do final (não interrompem aqui).
            aplic_auto = [m for m in aplic if m.id not in SEMPRE_MANUAL]
            aplic_manual = [m for m in aplic if m.id in SEMPRE_MANUAL]
            if aplic_manual:
                fila_manual.append((doc, nasc, nome, donos[i], aplic_manual))
            if aplic_auto:
                resultados = executar_lote(doc, aplic_auto, PASTA_BASE, on_log, on_status,
                                           _cancel, nasc, nome, documento_pasta=donos[i])
                grupo = _pasta_do_grupo(PASTA_BASE, donos[i])
                for r in resultados:
                    if r.status is Status.MANUAL:
                        registrar_pendencia(r.modulo_id, doc.numero, grupo)

        if fila_manual and not _cancel.is_set():
            _emit({"t": "log", "m": "\n===== Fila de emissão manual (uma vez, no final) ====="})
            _rodar_fila_manual(fila_manual, on_log, on_status, registrar_pendencia)

        _emit({"t": "log", "m": "\nConcluído."})
    except Exception as exc:  # noqa: BLE001
        _emit({"t": "log", "m": f"Erro geral: {type(exc).__name__}: {exc}"})
    finally:
        _rodando.release()
        sessao_ativa.clear()  # sessão acabou: o importador ganha mais 3 min de tolerância
        _emit({"t": "fim"})


def _rodar_fila_manual(fila, on_log, on_status, registrar_pendencia):
    """Processa, de uma vez só no final do lote, as certidões que sempre exigem o
    usuário — em vez de interromper espalhado ao longo da execução.

    Primeiro Receita/Cartão CNPJ/TCU Consolidada (abrem aba no navegador do
    sistema e não esperam nada — disparam todas juntas, ficam "cozinhando"
    enquanto o resto roda). Depois o CEIS/CGU (exige resolver um captcha de imagens por vez),
    num único navegador reaproveitado entre as empresas, para não abrir/fechar
    um a cada uma. `registrar_pendencia(modulo_id, numero, pasta)` alimenta o
    importador da pasta Downloads, que já está de vigia desde o início da sessão."""
    for doc, nasc, nome, dono, mods in fila:
        if _cancel.is_set():
            break
        rapidos = [m for m in mods if m.id != "cgu_correcional"]
        if not rapidos:
            continue
        on_log(f"\n----- {doc.formatado} -----")
        resultados = executar_lote(doc, rapidos, PASTA_BASE, on_log, on_status,
                                   _cancel, nasc, nome, documento_pasta=dono)
        grupo = _pasta_do_grupo(PASTA_BASE, dono)
        for r in resultados:
            if r.status is Status.MANUAL:
                registrar_pendencia(r.modulo_id, doc.numero, grupo)

    pendentes_cgu = [(doc, nasc, nome, dono) for doc, nasc, nome, dono, mods in fila
                     if any(m.id == "cgu_correcional" for m in mods)]
    if pendentes_cgu and not _cancel.is_set():
        modulo_cgu = por_id("cgu_correcional")
        on_log(f"\nCEIS (CGU): {len(pendentes_cgu)} pendente(s) — resolva o captcha de cada uma.")
        with sync_playwright() as pw:
            contexto = _abrir_contexto(pw, on_log)
            try:
                for doc, nasc, nome, dono in pendentes_cgu:
                    if _cancel.is_set():
                        break
                    on_log(f"\n----- {doc.formatado} (CEIS) -----")
                    resultados = executar_lote(doc, [modulo_cgu], PASTA_BASE, on_log, on_status,
                                               _cancel, nasc, nome, documento_pasta=dono,
                                               contexto_compartilhado=contexto)
                    grupo = _pasta_do_grupo(PASTA_BASE, dono)
                    for r in resultados:
                        if r.status is Status.MANUAL:
                            registrar_pendencia(r.modulo_id, doc.numero, grupo)
            finally:
                try:
                    contexto.close()
                except Exception:  # noqa: BLE001
                    pass


def _importar_downloads(pendencias: list, lock: threading.Lock,
                         sessao_ativa: threading.Event, inicio_sessao: float) -> None:
    """Vigia a pasta Downloads durante toda a sessão — reconhece um documento
    manual (Receita, Cartão CNPJ, Consulta Consolidada TCU) pelo CONTEÚDO do PDF
    assim que ele aparece, move pra pasta certa e renomeia com a validade, sem
    esperar o resto do lote terminar.

    `pendencias` cresce ao vivo (outra thread chama `registrar_pendencia`, que
    tranca com `lock`); some da lista assim que o arquivo é importado. Depois que
    a sessão termina (`sessao_ativa` limpo), ainda dá mais 3 min de tolerância
    antes de desistir do que sobrou — dá tempo de terminar algo que ainda estava
    em aberto (ex.: a Consulta Consolidada do TCU, que demora no site deles)."""
    downloads = _pasta_downloads_navegador()
    if not downloads.exists():
        return
    vistos: set = set()
    avisou = False
    fim_graca = None
    while not _cancel.is_set():
        with lock:
            restantes = list(pendencias)
        if restantes:
            if not avisou:
                _emit({"t": "log", "m": "Vigiando a pasta Downloads — assim que você baixar um "
                                        "documento manual, eu movo e renomeio sozinho…"})
                avisou = True
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
                if not mid:
                    continue
                # Casa por ALFANUMÉRICO (maiúsculas): robusto a CNPJ com espaços e ao
                # CNPJ alfanumérico (novo formato). pnum já vem limpo de documento.py.
                alnum = re.sub(r"[^0-9A-Za-z]", "", texto).upper()
                with lock:
                    candidatos = list(pendencias)
                for pend in candidatos:
                    pmid, pnum, pasta = pend
                    if mid == pmid and pnum in alnum:
                        try:
                            pasta.mkdir(parents=True, exist_ok=True)
                            destino = pasta / pdf.name
                            shutil.move(str(pdf), str(destino))
                            novo = renomear_com_validade(destino, por_id(mid), detectar(pnum))
                            _emit({"t": "log", "m": f"Importei da Downloads: {novo.name}  →  {pasta.parent.name}"})
                        except Exception as exc:  # noqa: BLE001
                            _emit({"t": "log", "m": f"Não consegui importar {pdf.name}: {exc}"})
                        with lock:
                            if pend in pendencias:
                                pendencias.remove(pend)
                        break

        if not sessao_ativa.is_set():
            if fim_graca is None:
                fim_graca = time.time() + 180
            with lock:
                sobrou = bool(pendencias)
            if not sobrou or time.time() >= fim_graca:
                break
        time.sleep(3)

    with lock:
        sobrando = list(pendencias)
    if sobrando:
        nomes = sorted({por_id(p[0]).nome for p in sobrando})
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
    eel.start("index.html", mode="edge", size=(980, 680), port=0, block=True,
              close_callback=_ao_fechar)


if __name__ == "__main__":
    main()
