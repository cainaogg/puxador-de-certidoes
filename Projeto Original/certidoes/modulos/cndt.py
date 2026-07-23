"""Certidão Negativa de Débitos Trabalhistas (CNDT) — TST.

O site exige um CAPTCHA de texto em imagem (6 caracteres alfanuméricos sobre
círculos de ruído). O módulo tenta resolver **automaticamente** (ddddocr, offline)
com repetição — emitir é grátis e o captcha recarrega à vontade, então se um
captcha falhar ele tenta outro. Se o OCR não estiver disponível (deps ausentes)
ou esgotar as tentativas, cai no **modo assistido** (você digita na janela).

Seletores JSF do TST mapeados em 2026-06-20 / 2026-07-09.
"""

from __future__ import annotations

import re
import time

from .. import captcha_ocr
from ..base import Contexto, ModuloCertidao, Resultado, Status, abrir_site_ou_manual
from ..documento import TipoDoc

TIMEOUT_CAPTCHA_MS = 5 * 60 * 1000  # espera no modo assistido


def _bind_download(pg, baixados: dict) -> None:
    try:
        pg.on("download", lambda d: baixados.setdefault("d", d))
    except Exception:  # noqa: BLE001
        pass


class CNDT(ModuloCertidao):
    id = "cndt_trabalhista"
    nome = "CND Trabalhista (CNDT)"
    descricao = "TST — resolve o captcha sozinho (offline); se falhar, modo assistido."
    url = "https://cndt-certidao.tst.jus.br/gerarCertidao.faces"
    requer_captcha = True
    implementado = True
    aceita = frozenset({TipoDoc.CNPJ, TipoDoc.CPF})

    SEL_CPF_CNPJ = '[id="gerarCertidaoForm:cpfCnpj"]'
    SEL_CAMPO_CAPTCHA = "#idCampoResposta"
    SEL_IMG = "#idImgBase64"
    SEL_EMITIR = '[id="gerarCertidaoForm:btnEmitirCertidao"]'
    MAX_TENTATIVAS = 8

    def executar(self, page, ctx: Contexto) -> Resultado:
        ctx.log("CNDT: abrindo o site do TST…")
        if not abrir_site_ou_manual(page, ctx, "CNDT", self.url):
            return Resultado(self.id, Status.MANUAL,
                             "O site do TST não respondeu a tempo. Abri no seu navegador padrão.")
        page.wait_for_timeout(2_000)
        self._esperar_captcha(page)
        try:
            page.fill(self.SEL_CPF_CNPJ, ctx.documento.formatado, timeout=15_000)
            ctx.log("CNDT: CNPJ preenchido.")
        except Exception:  # noqa: BLE001
            ctx.log("CNDT: não consegui preencher o documento.")

        if captcha_ocr.disponivel():
            res = self._auto(page, ctx)
            if res is not None:
                return res
            ctx.log("CNDT: não resolvi o captcha sozinho — passando para o modo assistido.")
        else:
            ctx.log("CNDT: OCR indisponível — modo assistido.")
        return self._assistido(page, ctx)

    # ------------------------------------------------------------- automático
    def _auto(self, page, ctx: Contexto):
        """Resolve o captcha com OCR, com retry. Devolve Resultado OK ou None."""
        baixados: dict = {}
        novas: list = []
        page.on("download", lambda d: baixados.setdefault("d", d))
        page.context.on("page", lambda p: (novas.append(p), _bind_download(p, baixados)))

        for tent in range(1, self.MAX_TENTATIVAS + 1):
            try:
                src = page.eval_on_selector(self.SEL_IMG, "e => e.src")
            except Exception:  # noqa: BLE001
                return None
            texto = captcha_ocr.ler_data_uri(src)
            if not re.fullmatch(r"[a-z0-9]{6}", texto):
                ctx.log(f"CNDT: captcha ilegível ({texto!r}); tentando outro…")
                if not self._recarregar(page, ctx):
                    return None
                continue

            baixados.clear()
            novas.clear()
            try:
                page.fill(self.SEL_CAMPO_CAPTCHA, texto)
                ctx.log(f"CNDT: tentativa {tent}/{self.MAX_TENTATIVAS} (captcha '{texto}')…")
                page.click(self.SEL_EMITIR, timeout=10_000)
            except Exception:  # noqa: BLE001
                return None

            caminho = self._capturar(page, ctx, baixados, novas)
            if caminho:
                ctx.log(f"CNDT: salvo em {caminho.name} (captcha resolvido sozinho).")
                return Resultado(self.id, Status.OK, "Certidão salva.", caminho)

            if not self._recarregar(page, ctx):
                return None
        return None  # esgotou as tentativas

    def _capturar(self, page, ctx: Contexto, baixados: dict, novas: list, prazo: int = 12):
        """Espera o PDF após emitir (download ou aba-PDF). None se não vier."""
        caminho = ctx.caminho_pdf(self.id)
        fim = time.time() + prazo
        while time.time() < fim:
            if "d" in baixados:
                try:
                    baixados["d"].save_as(str(caminho))
                    return caminho
                except Exception:  # noqa: BLE001
                    return None
            for p in list(novas):
                try:
                    if p.is_closed():
                        continue
                    ct = (p.evaluate("() => document.contentType") or "").lower()
                    if "pdf" in ct or p.url.lower().endswith(".pdf"):
                        resp = p.context.request.get(p.url)
                        caminho.parent.mkdir(parents=True, exist_ok=True)
                        caminho.write_bytes(resp.body())
                        return caminho
                except Exception:  # noqa: BLE001
                    continue
            try:
                page.wait_for_timeout(700)
            except Exception:  # noqa: BLE001
                time.sleep(0.7)
        return None

    def _recarregar(self, page, ctx: Contexto) -> bool:
        """Recarrega o formulário (novo captcha) e repõe o CNPJ."""
        try:
            page.goto(self.url, wait_until="domcontentloaded", timeout=60_000)
            page.wait_for_timeout(1_200)
            self._esperar_captcha(page)
            page.fill(self.SEL_CPF_CNPJ, ctx.documento.formatado, timeout=15_000)
            return True
        except Exception:  # noqa: BLE001
            return False

    def _esperar_captcha(self, page) -> None:
        try:
            page.wait_for_function(
                "() => { const e=document.querySelector('#idImgBase64');"
                " return e && e.src && e.src.startsWith('data:image'); }",
                timeout=15_000,
            )
        except Exception:  # noqa: BLE001
            pass

    # -------------------------------------------------------------- assistido
    def _assistido(self, page, ctx: Contexto) -> Resultado:
        try:
            page.click(self.SEL_CAMPO_CAPTCHA, timeout=5_000)
        except Exception:  # noqa: BLE001
            pass
        ctx.aguardar_captcha(
            "CNDT: digite na janela do navegador os caracteres da imagem (CAPTCHA) "
            "e clique em 'Emitir Certidão'. O PDF será capturado automaticamente."
        )
        try:
            with page.expect_download(timeout=TIMEOUT_CAPTCHA_MS) as info:
                pass  # o clique é do usuário; só aguardamos o download
            download = info.value
        except Exception:  # noqa: BLE001
            return Resultado(
                self.id, Status.ERRO,
                "Tempo esgotado aguardando a emissão (CAPTCHA não resolvido?).",
            )
        caminho = ctx.caminho_pdf(self.id)
        download.save_as(str(caminho))
        ctx.log(f"CNDT: salvo em {caminho.name}")
        return Resultado(self.id, Status.OK, "Certidão salva.", caminho)
