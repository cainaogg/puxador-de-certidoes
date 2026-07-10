"""Nova interface (webview) do Puxador de Certidões — FASE 1 (fundação).

Renderiza `index.html` numa janela nativa (pywebview + WebView2) e liga os botões
ao MOTOR já existente (engine/base/registry), sem tocar no app.py (CustomTkinter).
Reaproveita os callbacks do engine: os updates que iam para os widgets agora vão
para o JS via `window.evaluate_js`.
"""

from __future__ import annotations

import json
import os
import re
import sys
import threading
from pathlib import Path

import webview

# Permite importar o pacote `certidoes` (um nível acima desta pasta).
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from certidoes import ajuda, paths  # noqa: E402
from certidoes.base import Status, so_letras_numeros  # noqa: E402
from certidoes.documento import DocumentoInvalido, TipoDoc, detectar  # noqa: E402
from certidoes.engine import executar_lote  # noqa: E402
from certidoes.registry import REGISTRY, por_id  # noqa: E402

PASTA_BASE = paths.base_dados() / "downloads"
HTML = Path(__file__).resolve().parent / "index.html"

# Status do motor -> chave de estilo no JS (ver PILL no index.html).
_ST = {
    "pendente": "pendente", "executando": "baixando",
    "aguardando_captcha": "aguardando_captcha", "ok": "ok", "erro": "erro",
    "nao_aplicavel": "nao_aplicavel", "cancelado": "pendente",
    "manual": "manual", "ja_valida": "ja_valida",
}


class Api:
    def __init__(self) -> None:
        self.window = None
        self.cancel_event = threading.Event()
        self.worker: threading.Thread | None = None

    # ---- chamadas JS -> Python -------------------------------------------
    def listar_certidoes(self):
        return [{"id": m.id, "label": m.nome,
                 "desc": ajuda.CERTIDOES.get(m.id, m.descricao or ""),
                 "impl": bool(m.implementado)} for m in REGISTRY]

    def iniciar(self, texto: str, ids) -> None:
        entries = self._parse(texto or "")
        modulos = [por_id(i) for i in ids if por_id(i).implementado]
        if not entries:
            self._log("⚠ Informe ao menos um CPF ou CNPJ válido.")
            self._js("finalizar()")
            return
        if not modulos:
            self._log("⚠ Selecione ao menos uma certidão.")
            self._js("finalizar()")
            return
        self.cancel_event.clear()
        self.worker = threading.Thread(target=self._rodar, args=(entries, modulos), daemon=True)
        self.worker.start()

    def acao(self, nome: str) -> None:
        if nome == "cancelar":
            self.cancel_event.set()
            self._log("Cancelamento solicitado (encerra após a certidão atual).")
        elif nome == "abrir_pasta":
            PASTA_BASE.mkdir(parents=True, exist_ok=True)
            os.startfile(str(PASTA_BASE))  # type: ignore[attr-defined]
        else:
            self._log(f"[{nome}] — em breve nesta interface (próxima fase).")

    # ---- execução (thread) -----------------------------------------------
    def _rodar(self, entries, modulos) -> None:
        def on_log(msg: str) -> None:
            self._log(msg)

        def on_status(mid: str, valor) -> None:
            st = valor.status if hasattr(valor, "status") else valor
            self._set_status(mid, st)

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
                if self.cancel_event.is_set():
                    self._log("Cancelado pelo usuário.")
                    break
                self._log(f"\n===== {doc.formatado} =====")
                aplic = [m for m in modulos if m.aplica_para(doc.tipo)]
                for m in modulos:
                    self._set_status(m.id, Status.PENDENTE if m in aplic else Status.NAO_APLICAVEL)
                if not aplic:
                    self._log(f"  (nenhuma certidão marcada se aplica a {doc.tipo.value.upper()})")
                    continue
                executar_lote(doc, aplic, PASTA_BASE, on_log, on_status,
                              self.cancel_event, nasc, nome, documento_pasta=donos[i])
            self._log("\nConcluído.")
        except Exception as exc:  # noqa: BLE001
            self._log(f"Erro geral: {type(exc).__name__}: {exc}")
        finally:
            self._js("finalizar()")

    # ---- helpers ----------------------------------------------------------
    def _parse(self, texto: str):
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

    def _js(self, code: str) -> None:
        if self.window:
            try:
                self.window.evaluate_js(code)
            except Exception:  # noqa: BLE001
                pass

    def _log(self, msg: str) -> None:
        self._js(f"addLog({json.dumps(msg)})")

    def _set_status(self, mid: str, status) -> None:
        chave = _ST.get(getattr(status, "value", str(status)), "pendente")
        self._js(f"setStatus({json.dumps(mid)},{json.dumps(chave)})")


def main() -> None:
    api = Api()
    janela = webview.create_window(
        "Puxador de Certidões", url=HTML.as_uri(), js_api=api,
        width=980, height=680, min_size=(920, 660), background_color="#0B0F17",
    )
    api.window = janela
    webview.start()


if __name__ == "__main__":
    main()
