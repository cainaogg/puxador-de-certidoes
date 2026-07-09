"""Interface gráfica (CustomTkinter) do baixador de certidões (Projeto Original)."""

from __future__ import annotations

import os
import re
import threading
import tkinter as tk
from pathlib import Path
from typing import Dict, List, Tuple, Union

import customtkinter as ctk
from PIL import Image

from tkinter import filedialog

from . import ajuda, config, paths
from .base import (
    STATUS_LABEL,
    ModuloCertidao,
    Resultado,
    Status,
    _texto_pdf,
    documento_no_texto,
    identificar_certidao,
    juntar_pdfs,
    nome_documento,
    nome_para_tipo,
    renomear_com_validade,
    so_letras_numeros,
    verificar_vencimentos,
)
from .documento import Documento, DocumentoInvalido, TipoDoc, detectar
from .engine import executar_lote, nomear_pasta_mae
from .registry import REGISTRY, por_id

PASTA_BASE = paths.base_dados() / "downloads"

PLACEHOLDER = ("Um documento por linha. Exemplos:\n"
               "12.345.678/0001-90\n"
               "123.456.789-00 01/01/1980 FULANO DE TAL   (CPF: data p/ CND Federal, nome p/ CNJ)")

TEXTO_AJUDA_DOCS = (
    "Digite um CPF ou CNPJ por linha (com ou sem pontuação). O programa baixa as "
    "certidões marcadas para o primeiro documento, depois para o próximo — pode misturar "
    "CNPJ e CPF.\n\nPara a CND Federal de um CPF, a Receita exige a data de nascimento: "
    "coloque na mesma linha, depois do CPF. Ex.: 123.456.789-00 01/01/1980.\n\n"
    "Para a certidão do CNJ de um CPF, informe também o nome da pessoa na mesma linha "
    "(ex.: 123.456.789-00 01/01/1980 FULANO DE TAL) — o CNJ exige o nome e não há fonte "
    "gratuita dele para CPF.")

FONTE = "Inter"           # texto normal
FONTE_BOLD = "Inter Medium"  # títulos/negrito (mais próximo do mockup que o bold sintético)


def _registrar_fontes() -> None:
    """Registra a fonte Inter (empacotada) no Windows, para o Tk poder usá-la."""
    fdir = paths.base_recursos() / "assets" / "fonts"
    if not fdir.exists() or os.name != "nt":
        return
    import ctypes
    for ttf in fdir.glob("*.ttf"):
        try:
            ctypes.windll.gdi32.AddFontResourceExW(str(ttf), 0x10, 0)  # FR_PRIVATE
        except Exception:  # noqa: BLE001
            pass


def _icone(nome: str, size: int = 18) -> "ctk.CTkImage | None":
    """Carrega um ícone PNG de assets/ como CTkImage (o mesmo p/ claro e escuro)."""
    p = paths.base_recursos() / "assets" / f"ic_{nome}.png"
    if not p.exists():
        return None
    img = Image.open(p)
    return ctk.CTkImage(light_image=img, dark_image=img, size=(size, size))

# Status como "badge" colorido: (cor de fundo, cor do texto). Tons para modo escuro.
BADGE = {
    Status.OK: ("#1b4332", "#74e39b"),
    Status.JA_VALIDA: ("#123a3a", "#67d8c4"),
    Status.ERRO: ("#4a1e1e", "#f0a3a3"),
    Status.EXECUTANDO: ("#123a5e", "#7fbef0"),
    Status.AGUARDANDO_CAPTCHA: ("#4a3410", "#f0c477"),
    Status.MANUAL: ("#4a3410", "#f0c477"),
    Status.PENDENTE: ("#333333", "#a0a0a0"),
    Status.NAO_APLICAVEL: ("#2a2a2a", "#707070"),
    Status.CANCELADO: ("#333333", "#a0a0a0"),
}
BADGE_TEXTO = {
    Status.OK: "Baixado",
    Status.JA_VALIDA: "Já válida",
    Status.ERRO: "Erro",
    Status.EXECUTANDO: "Baixando…",
    Status.AGUARDANDO_CAPTCHA: "Resolva o captcha",
    Status.MANUAL: "Emitir manual",
    Status.PENDENTE: "Pendente",
    Status.NAO_APLICAVEL: "—",
    Status.CANCELADO: "Cancelado",
}


def _badge_txt(status: Status) -> str:
    """Texto do badge com folga lateral (vira uma pílula compacta, sem largura fixa)."""
    return f"  {BADGE_TEXTO.get(status, str(status.value))}  "


class Linha:
    """Widgets de uma certidão na lista."""

    def __init__(self, modulo: ModuloCertidao, var: tk.IntVar,
                 checkbox: ctk.CTkCheckBox, status: ctk.CTkLabel):
        self.modulo = modulo
        self.var = var
        self.checkbox = checkbox
        self.status = status


class Tooltip:
    """Balão de ajuda que aparece ao passar o mouse (sem abrir janela)."""

    def __init__(self, widget, texto: str):
        self.widget = widget
        self.texto = texto
        self.tip: tk.Toplevel | None = None
        widget.bind("<Enter>", self._mostrar)
        widget.bind("<Leave>", self._esconder)

    def _mostrar(self, _e=None) -> None:
        if self.tip or not self.texto:
            return
        x = self.widget.winfo_rootx() + 24
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 6
        self.tip = tk.Toplevel(self.widget)
        self.tip.wm_overrideredirect(True)
        self.tip.wm_geometry(f"+{x}+{y}")
        tk.Label(self.tip, text=self.texto, justify="left", wraplength=380,
                 bg="#2b2b2b", fg="#e8e8e8", relief="solid", borderwidth=1,
                 font=(FONTE, 10), padx=10, pady=8).pack()

    def _esconder(self, _e=None) -> None:
        if self.tip:
            self.tip.destroy()
            self.tip = None


class App(ctk.CTk):
    def __init__(self) -> None:
        _registrar_fontes()
        ctk.ThemeManager.theme["CTkFont"]["family"] = FONTE
        super().__init__()
        self.title("Puxador de Certidões")
        self._centralizar(780, 800)
        self.minsize(680, 600)

        self.linhas: Dict[str, Linha] = {}
        self.cancel_event = threading.Event()
        self.worker: threading.Thread | None = None
        self.documento_atual: Documento | None = None
        self._ph_ativo = True

        self._montar_topo()
        self._montar_lista()
        self._montar_rodape()
        self._restaurar_placeholder()
        # Clicar fora da caixa (inclusive em espaço vazio) restaura os exemplos.
        self.bind("<Button-1>", self._clique_fora, add="+")

    def _centralizar(self, w: int, h: int) -> None:
        """Abre a janela no centro da tela."""
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        x = max(0, (sw - w) // 2)
        y = max(0, (sh - h) // 2 - 20)  # um pouco acima do centro exato
        self.geometry(f"{w}x{h}+{x}+{y}")

    # ------------------------------------------------------------------ topo
    def _montar_topo(self) -> None:
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=18, pady=(14, 2))
        ic_app = _icone("certificate", 30)
        if ic_app:
            ctk.CTkLabel(header, text="", image=ic_app).pack(side="left", padx=(0, 10))
        titulo = ctk.CTkFrame(header, fg_color="transparent")
        titulo.pack(side="left")
        ctk.CTkLabel(titulo, text="Puxador de Certidões",
                     font=(FONTE_BOLD, 20)).pack(anchor="w")
        ctk.CTkLabel(titulo, text="Baixe todas as certidões de um CNPJ ou CPF de uma vez",
                     text_color="gray", font=(FONTE, 12)).pack(anchor="w")
        btn_cfg = ctk.CTkButton(header, text="", image=_icone("settings", 20),
                                width=38, height=38, fg_color="gray25", hover_color="gray35",
                                command=self._abrir_config)
        btn_cfg.pack(side="right")
        Tooltip(btn_cfg, "Configurações")
        btn_aj = ctk.CTkButton(header, text="", image=_icone("help", 20),
                               width=38, height=38, fg_color="gray25", hover_color="gray35",
                               command=self._ajuda_programa)
        btn_aj.pack(side="right", padx=8)
        Tooltip(btn_aj, "Ajuda")

        topo = ctk.CTkFrame(self)
        topo.pack(fill="x", padx=16, pady=(6, 8))

        cab = ctk.CTkFrame(topo, fg_color="transparent")
        cab.pack(fill="x", padx=12, pady=(12, 2))
        ctk.CTkLabel(cab, text="Documentos — um por linha",
                     font=(FONTE_BOLD, 14)).pack(side="left")
        ajuda_docs = ctk.CTkLabel(cab, text="?", width=22, height=22, fg_color="gray",
                                  corner_radius=11, text_color="white", font=(FONTE_BOLD, 12))
        ajuda_docs.pack(side="left", padx=8)
        Tooltip(ajuda_docs, TEXTO_AJUDA_DOCS)

        self.txt_docs = ctk.CTkTextbox(topo, height=86, font=(FONTE, 13), wrap="none")
        self.txt_docs.pack(fill="x", padx=12, pady=(0, 4))
        self.txt_docs.bind("<FocusIn>", self._ph_in)
        self.txt_docs.bind("<FocusOut>", self._ph_out)
        self.txt_docs.bind("<KeyRelease>", lambda _e: self._atualizar_resumo())

        self.lbl_resumo = ctk.CTkLabel(topo, text="", anchor="w")
        self.lbl_resumo.pack(fill="x", padx=12, pady=(0, 10))

    # ------------------------------------------------------ placeholder cinza
    def _restaurar_placeholder(self) -> None:
        self._ph_ativo = True
        self.txt_docs.delete("1.0", "end")
        self.txt_docs.insert("1.0", PLACEHOLDER)
        self.txt_docs.configure(text_color="gray")

    def _ph_in(self, _e=None) -> None:
        if self._ph_ativo:
            self.txt_docs.delete("1.0", "end")
            self.txt_docs.configure(text_color=("gray10", "gray90"))
            self._ph_ativo = False

    def _ph_out(self, _e=None) -> None:
        if not self.txt_docs.get("1.0", "end").strip():
            self._restaurar_placeholder()

    def _clique_fora(self, event) -> None:
        # Se clicou fora da caixa e ela está vazia (sem placeholder), restaura.
        if event.widget in (self.txt_docs, getattr(self.txt_docs, "_textbox", None)):
            return
        if not self._ph_ativo and not self.txt_docs.get("1.0", "end").strip():
            self._restaurar_placeholder()
            self.focus_set()

    def _texto_docs(self) -> str:
        return "" if self._ph_ativo else self.txt_docs.get("1.0", "end")

    # ----------------------------------------------------------------- lista
    def _montar_lista(self) -> None:
        barra = ctk.CTkFrame(self, fg_color="transparent")
        barra.pack(fill="x", padx=20, pady=(2, 0))
        ctk.CTkLabel(barra, text="Certidões", font=(FONTE_BOLD, 14)).pack(side="left")
        ctk.CTkLabel(barra, text="passe o mouse no ? para entender",
                     text_color="gray", font=(FONTE, 11)).pack(side="left", padx=8)

        self.var_todas = tk.IntVar(value=0)
        ctk.CTkCheckBox(barra, text="Selecionar todas", variable=self.var_todas,
                        command=self._toggle_todas, font=(FONTE, 13)).pack(side="right", pady=4)

        self.scroll = ctk.CTkScrollableFrame(self, label_text="")
        self.scroll.pack(fill="both", expand=True, padx=16, pady=(6, 8))

        # Lista única, na ordem definida no registry.
        for modulo in REGISTRY:
            self._linha(modulo)

    def _grupo(self, titulo: str, modulos) -> None:
        if not modulos:
            return
        ctk.CTkLabel(self.scroll, text=titulo, font=(FONTE_BOLD, 13),
                     anchor="w").pack(fill="x", pady=(10, 2), padx=4)
        for modulo in modulos:
            self._linha(modulo)

    def _linha(self, modulo: ModuloCertidao) -> None:
        row = ctk.CTkFrame(self.scroll)
        row.pack(fill="x", pady=2, padx=2)

        var = tk.IntVar(value=0)
        texto = modulo.nome
        if not modulo.implementado:
            texto += "  (em breve)"
        chk = ctk.CTkCheckBox(row, text=texto, variable=var, command=self._sincronizar_todas)
        chk.pack(side="left", padx=(8, 4), pady=6)
        if not modulo.implementado:
            chk.configure(state="disabled")

        interr = ctk.CTkLabel(row, text="?", width=22, height=22, fg_color="gray30",
                              corner_radius=11, text_color="white", font=(FONTE_BOLD, 12))
        interr.pack(side="right", padx=(6, 10))
        Tooltip(interr, ajuda.CERTIDOES.get(modulo.id, modulo.descricao or ""))

        bg, fg = BADGE[Status.PENDENTE]
        status = ctk.CTkLabel(row, text=_badge_txt(Status.PENDENTE), fg_color=bg,
                              text_color=fg, corner_radius=12, height=26, font=(FONTE_BOLD, 12))
        status.pack(side="right")

        self.linhas[modulo.id] = Linha(modulo, var, chk, status)

    # ---------------------------------------------------------------- rodapé
    def _montar_rodape(self) -> None:
        botoes = ctk.CTkFrame(self, fg_color="transparent")
        botoes.pack(fill="x", padx=16, pady=(0, 6))

        self.btn_buscar = ctk.CTkButton(botoes, text="Buscar e baixar", height=40,
                                        image=_icone("download"), compound="left",
                                        font=(FONTE_BOLD, 14), command=self._iniciar)
        self.btn_buscar.pack(side="left")

        self.btn_cancelar = ctk.CTkButton(botoes, text="Cancelar", height=40, width=110,
                                          fg_color="gray", command=self._cancelar, state="disabled")
        self.btn_cancelar.pack(side="left", padx=8)

        ctk.CTkButton(botoes, text="Abrir pasta", image=_icone("folder"), compound="left",
                      height=40, width=130, fg_color="gray25", hover_color="gray35",
                      command=self._abrir_pasta).pack(side="right")

        utils = ctk.CTkFrame(self, fg_color="transparent")
        utils.pack(fill="x", padx=16, pady=(0, 6))
        for txt, ico, cmd in [("Escanear baixados", "search", self._escanear),
                              ("Verificador de Validade", "calendar", self._verificador),
                              ("Juntar PDFs", "files", self._juntar_manual)]:
            ctk.CTkButton(utils, text=txt, image=_icone(ico, 16), compound="left",
                          height=36, fg_color="gray", command=cmd).pack(side="left", padx=(0, 8))

        self.log = ctk.CTkTextbox(self, height=150, fg_color="#0a0a0a",
                                  text_color="#e6e6e6", font=(FONTE, 12))
        self.log.pack(fill="both", expand=False, padx=16, pady=(0, 16))
        # Tags coloridas+negrito no Text interno (CTkTextbox.tag_config proíbe 'font').
        _neg = (FONTE_BOLD, 13)
        self.log._textbox.tag_config("vermelho", foreground="#ff6b6b", font=_neg)
        self.log._textbox.tag_config("amarelo", foreground="#e0a341", font=_neg)
        self.log._textbox.tag_config("verde", foreground="#6ee39b", font=_neg)
        self.log.configure(state="disabled")

    # ----------------------------------------------------------- documentos
    def _parse_documentos(self) -> Tuple[List[Tuple[Documento, str, str]], List[str]]:
        """Lê o textbox: cada linha tem o documento e, opcionalmente, data de
        nascimento e nome (ex.: '123.456.789-00 01/01/1980 FULANO DE TAL' — a data
        serve à CND Federal e o nome ao CNJ, quando é um CPF)."""
        entries: List[Tuple[Documento, str, str]] = []
        invalidas: List[str] = []
        for raw in self._texto_docs().splitlines():
            linha = raw.strip()
            if not linha:
                continue
            m = re.search(r"\b(\d{2}/\d{2}/\d{4})\b", linha)
            nasc = m.group(1) if m else ""
            resto = linha.replace(nasc, "") if nasc else linha
            try:
                doc = detectar(resto)
            except DocumentoInvalido:
                invalidas.append(linha)
                continue
            # o que sobra (sem o número do documento) vira o nome informado
            sem_num = resto.replace(doc.formatado, " ").replace(doc.numero, " ")
            nome = so_letras_numeros(sem_num)
            entries.append((doc, nasc, nome))
        return entries, invalidas

    def _atualizar_resumo(self) -> None:
        entries, invalidas = self._parse_documentos()
        n_cnpj = sum(1 for d, *_ in entries if d.tipo is TipoDoc.CNPJ)
        n_cpf = sum(1 for d, *_ in entries if d.tipo is TipoDoc.CPF)
        partes = []
        if entries:
            partes.append(f"✓ {len(entries)} documento(s): {n_cnpj} CNPJ, {n_cpf} CPF")
        if invalidas:
            partes.append(f"⚠ {len(invalidas)} linha(s) inválida(s)")
        self.lbl_resumo.configure(text="    ".join(partes),
                                  text_color="#c62828" if invalidas else "#2e7d32")

        # Habilita só as certidões que servem para os tipos presentes (ex.: um CPF
        # sozinho desabilita as que são só de CNPJ). Caixa vazia = todas habilitadas.
        tipos = {d.tipo for d, *_ in entries}
        for linha in self.linhas.values():
            if not linha.modulo.implementado:
                continue
            aplica = (not tipos) or bool(linha.modulo.aceita & tipos)
            linha.checkbox.configure(state="normal" if aplica else "disabled")
            if not aplica:
                linha.var.set(0)
        self._sincronizar_todas()

    def _toggle_todas(self) -> None:
        alvo = self.var_todas.get()
        for linha in self.linhas.values():
            if linha.modulo.implementado and str(linha.checkbox.cget("state")) != "disabled":
                linha.var.set(alvo)

    def _sincronizar_todas(self) -> None:
        marcaveis = [l for l in self.linhas.values()
                     if l.modulo.implementado and str(l.checkbox.cget("state")) != "disabled"]
        todas = marcaveis and all(l.var.get() for l in marcaveis)
        self.var_todas.set(1 if todas else 0)

    # -------------------------------------------------------------- ajuda
    def _mostrar_ajuda(self, titulo: str, texto: str) -> None:
        win = ctk.CTkToplevel(self)
        win.title(titulo)
        win.geometry("540x440")
        win.transient(self)
        win.grab_set()
        ctk.CTkLabel(win, text=titulo, font=(FONTE_BOLD, 15),
                     wraplength=500, justify="left").pack(padx=16, pady=(14, 6), anchor="w")
        box = ctk.CTkTextbox(win, wrap="word", font=(FONTE, 13))
        box.pack(fill="both", expand=True, padx=16, pady=(0, 10))
        box.insert("1.0", texto)
        box.configure(state="disabled")
        ctk.CTkButton(win, text="Fechar", command=win.destroy).pack(pady=(0, 12))

    def _ajuda_certidao(self, modulo: ModuloCertidao) -> None:
        texto = ajuda.CERTIDOES.get(modulo.id, modulo.descricao or "Sem descrição.")
        self._mostrar_ajuda(modulo.nome, texto)

    def _ajuda_programa(self) -> None:
        self._mostrar_ajuda("Como funciona o programa", ajuda.PROGRAMA)

    def _ajuda_documentos(self) -> None:
        self._mostrar_ajuda(
            "Como informar os documentos",
            "Digite um CPF ou CNPJ por linha (com ou sem pontuação). O programa baixa as "
            "certidões marcadas para o primeiro documento, depois para o próximo, e assim "
            "por diante. Pode misturar CNPJ e CPF.\n\n"
            "Para a CND Federal de um CPF, a Receita exige a data de nascimento: coloque-a "
            "na mesma linha, depois do CPF. Ex.: '123.456.789-00 01/01/1980'.")

    # --------------------------------------------------------------- log/status
    def _set_status(self, modulo_id: str, valor: Union[Status, Resultado]) -> None:
        linha = self.linhas.get(modulo_id)
        if not linha:
            return
        if isinstance(valor, Resultado):
            status = valor.status
            if valor.mensagem and status is Status.ERRO:
                self._append_log(f"{linha.modulo.nome}: {valor.mensagem}")
        else:
            status = valor
        bg, fg = BADGE.get(status, BADGE[Status.PENDENTE])
        linha.status.configure(text=_badge_txt(status), fg_color=bg, text_color=fg)

    def _reset_status(self, modulos, aplicaveis) -> None:
        ids_ap = {m.id for m in aplicaveis}
        for m in modulos:
            self._set_status(m.id, Status.PENDENTE if m.id in ids_ap else Status.NAO_APLICAVEL)

    def _append_log(self, msg: str) -> None:
        self.log.configure(state="normal")
        self.log.insert("end", msg + "\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    # --------------------------------------------------------------- execução
    def _iniciar(self) -> None:
        entries, invalidas = self._parse_documentos()
        if not entries:
            self._append_log("⚠ Informe ao menos um CPF ou CNPJ válido.")
            return
        selecionados = [l.modulo for l in self.linhas.values()
                        if l.modulo.implementado and l.var.get()]
        if not selecionados:
            self._append_log("⚠ Selecione ao menos uma certidão.")
            return
        if invalidas:
            amostra = "; ".join(invalidas[:3]) + ("…" if len(invalidas) > 3 else "")
            self._append_log(f"⚠ Ignorando {len(invalidas)} linha(s) inválida(s): {amostra}")

        self.documento_atual = entries[0][0]
        self.cancel_event.clear()
        self.btn_buscar.configure(state="disabled")
        self.btn_cancelar.configure(state="normal")
        self._append_log(f"Iniciando {len(entries)} documento(s) × {len(selecionados)} certidão(ões)…")
        self.worker = threading.Thread(target=self._rodar,
                                       args=(entries, selecionados), daemon=True)
        self.worker.start()

    def _rodar(self, entries: List[Tuple[Documento, str]], modulos) -> None:
        def on_log(msg: str) -> None:
            self.after(0, self._append_log, msg)

        def on_status(mid: str, valor) -> None:
            self.after(0, self._set_status, mid, valor)

        try:
            total_ok = total = total_val = 0
            for i, (doc, nasc, nome) in enumerate(entries, 1):
                if self.cancel_event.is_set():
                    self.after(0, self._append_log, "Cancelado pelo usuário.")
                    break
                self.after(0, self._append_log,
                           f"\n===== Documento {i}/{len(entries)}: {doc.formatado} =====")
                aplic = [m for m in modulos if m.aplica_para(doc.tipo)]
                self.after(0, self._reset_status, modulos, aplic)
                if not aplic:
                    self.after(0, self._append_log,
                               f"  (nenhuma certidão marcada se aplica a {doc.tipo.value.upper()})")
                    continue
                resultados = executar_lote(doc, aplic, PASTA_BASE, on_log, on_status,
                                           self.cancel_event, nasc, nome)
                total_ok += sum(1 for r in resultados if r.status is Status.OK)
                total_val += sum(1 for r in resultados if r.status is Status.JA_VALIDA)
                total += len(resultados)
                self.documento_atual = doc
            extra = f" · {total_val} já válida(s) (puladas)" if total_val else ""
            self.after(0, self._append_log,
                       f"\nConcluído: {total_ok}/{total} baixada(s){extra} em {len(entries)} documento(s).")
        except Exception as exc:  # noqa: BLE001
            self.after(0, self._append_log, f"Erro geral: {type(exc).__name__}: {exc}")
        finally:
            self.after(0, self._finalizar)

    def _finalizar(self) -> None:
        self.btn_buscar.configure(state="normal")
        self.btn_cancelar.configure(state="disabled")

    def _cancelar(self) -> None:
        self.cancel_event.set()
        self._append_log("Cancelamento solicitado (encerra após a certidão atual).")

    def _abrir_pasta(self) -> None:
        # Abre a pasta-raiz de downloads (cada documento tem sua subpasta nomeada).
        PASTA_BASE.mkdir(parents=True, exist_ok=True)
        os.startfile(str(PASTA_BASE))  # type: ignore[attr-defined]  # Windows

    # ---------------------------------------------------- escanear / vencimentos
    def _escanear(self) -> None:
        # ponytail: síncrono. Renomeia os PDFs NA PRÓPRIA pasta (não move nem cria
        # subpasta). Identifica pela nome do arquivo (confiável); só olha o conteúdo
        # se o nome não for reconhecido. Com muitos arquivos, trava alguns segundos.
        origem = filedialog.askdirectory(
            title="Pasta com os PDFs para renomear",
            initialdir=str(PASTA_BASE))
        if not origem:
            return
        n = 0
        doc_pasta = None
        for pdf in sorted(Path(origem).glob("*.pdf")):
            try:
                texto = _texto_pdf(pdf)
            except Exception:  # noqa: BLE001
                continue
            mid = self._id_por_nome(pdf.name) or identificar_certidao(texto)
            if not mid:
                continue
            doc = documento_no_texto(texto)  # p/ o token CPF/CNPJ e p/ nomear a pasta
            doc_pasta = doc_pasta or doc
            novo = renomear_com_validade(pdf, por_id(mid), doc)  # renomeia no lugar
            if novo.name != pdf.name:
                self._append_log(f"Renomeado: {pdf.name} → {novo.name}")
                n += 1
        # aproveita para nomear a pasta-mãe do documento (razão social - número)
        if doc_pasta is not None:
            nomear_pasta_mae(Path(origem), doc_pasta, self._append_log)
        self._append_log(f"Escanear: {n} arquivo(s) renomeado(s).")

    def _id_por_nome(self, nome_arquivo: str):
        """Se o arquivo já começa com o nome de uma certidão conhecida, devolve o id."""
        for modulo in REGISTRY:
            for tipo in (TipoDoc.CNPJ, TipoDoc.CPF):
                base = nome_documento(nome_para_tipo(modulo.nome, tipo))
                if base and nome_arquivo.startswith(base):
                    return modulo.id
        return None

    def _verificador(self) -> None:
        origem = filedialog.askdirectory(
            title="Pasta para verificar a validade",
            initialdir=str(PASTA_BASE))
        if not origem:
            return
        achados = verificar_vencimentos(Path(origem), dias=100000)  # todas as datadas
        if not achados:
            self._append_log("Verificador: nenhum PDF com validade no nome encontrado.")
            return
        self._append_log(f"Verificador de Validade — {len(achados)} certidão(ões):")
        precisam = set()
        self.log.configure(state="normal")
        for pdf, d, restam in achados:
            if restam < 0:
                badge, tag = "[VENCIDA]", "vermelho"
            elif restam <= 7:
                badge, tag = f"[faltam {restam}d]", "amarelo"
            else:
                badge, tag = f"[faltam {restam}d]", "verde"
            self.log.insert("end", "  ")
            self.log.insert("end", badge, tag)
            self.log.insert("end", f" {d.strftime('%d.%m.%Y')} — {pdf.name}\n")
            if restam <= 7:  # vencida ou a vencer em breve -> precisa atualizar
                try:
                    mid = identificar_certidao(_texto_pdf(pdf))
                except Exception:  # noqa: BLE001
                    mid = None
                if mid:
                    precisam.add(mid)
        self.log.see("end")
        self.log.configure(state="disabled")
        marcadas = 0
        for mid in precisam:
            linha = self.linhas.get(mid)
            if linha and linha.modulo.implementado and str(linha.checkbox.cget("state")) != "disabled":
                linha.var.set(1)
                marcadas += 1
        self._sincronizar_todas()
        if marcadas:
            self._append_log(f"Marquei {marcadas} certidão(ões) a atualizar (vencidas ou ≤7 dias).")

    def _juntar_manual(self) -> None:
        arquivos = filedialog.askopenfilenames(
            title="Selecione os PDFs para juntar num só",
            initialdir=str(PASTA_BASE), filetypes=[("PDF", "*.pdf")])
        if len(arquivos) < 2:
            self._append_log("Juntar: selecione ao menos 2 PDFs.")
            return
        paths = [Path(a) for a in arquivos]
        novo = juntar_pdfs(paths, paths[0].parent)
        if novo:
            self._append_log(f"Juntado ({len(paths)} PDFs) em: {novo}")
        else:
            self._append_log("Juntar: não consegui gerar o PDF.")

    # --------------------------------------------------------- configurações
    def _abrir_config(self) -> None:
        cfg = config.carregar()
        win = ctk.CTkToplevel(self)
        win.title("Configurações")
        win.geometry("560x500")
        win.transient(self)
        win.grab_set()

        ctk.CTkLabel(win, text="Configurações", font=(FONTE_BOLD, 16)).pack(pady=(16, 6))

        # Receita Federal: navegador OU API
        frm = ctk.CTkFrame(win)
        frm.pack(fill="x", padx=16, pady=8)
        ctk.CTkLabel(frm, text="Certidão da Receita Federal — como emitir:",
                     font=(FONTE_BOLD, 13), anchor="w").pack(fill="x", padx=12, pady=(10, 4))
        opcoes = {"Abrir no meu navegador": "navegador",
                  "Baixar pela API (Infosimples)": "api"}
        seg = ctk.CTkSegmentedButton(frm, values=list(opcoes.keys()))
        seg.pack(fill="x", padx=12, pady=(0, 8))
        atual = next((k for k, v in opcoes.items() if v == cfg.get("receita_modo")),
                     "Abrir no meu navegador")
        seg.set(atual)
        ctk.CTkLabel(
            frm, justify="left", anchor="w", text_color="gray",
            text=("• Navegador: abre o site no SEU navegador para emitir na mão.\n"
                  "• API: baixa sozinho (precisa do token abaixo; ~R$0,26/consulta)."),
        ).pack(fill="x", padx=12, pady=(0, 10))

        # Token da API
        frm2 = ctk.CTkFrame(win)
        frm2.pack(fill="x", padx=16, pady=8)
        ctk.CTkLabel(frm2, text="Token da API Infosimples (para o modo API):",
                     font=(FONTE_BOLD, 13), anchor="w").pack(fill="x", padx=12, pady=(10, 4))
        entry_token = ctk.CTkEntry(frm2, placeholder_text="cole seu token aqui", show="*")
        entry_token.pack(fill="x", padx=12, pady=(0, 12))
        if cfg.get("infosimples_token"):
            entry_token.insert(0, cfg["infosimples_token"])

        msg = ctk.CTkLabel(win, text="", text_color="#2e7d32")
        msg.pack(pady=(0, 2))

        def salvar() -> None:
            config.salvar(
                receita_modo=opcoes.get(seg.get(), "navegador"),
                infosimples_token=entry_token.get().strip(),
            )
            msg.configure(text="✓ Configurações salvas!")
            win.after(900, win.destroy)

        ctk.CTkButton(win, text="Salvar", height=38, command=salvar).pack(pady=(2, 12))


def main() -> None:
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("blue")
    App().mainloop()


if __name__ == "__main__":
    main()
