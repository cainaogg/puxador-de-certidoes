"""Comprovante de Inscrição no ISS — Município de Porto Alegre (Procempa/SIAT).

Mesmo padrão da POA Tributos (GWT + reCAPTCHA resolvido pela NopeCHA), com duas
diferenças: o tipo é um <select> (CPF/CNPJ/…) e o campo é "* Número do documento".
A aba correta é "Emitir Inscrição" (ignorar "Autenticar Inscrição"). 2026-06-20.
"""

from __future__ import annotations

import time

from ..base import (
    Contexto,
    ModuloCertidao,
    Resultado,
    Status,
    esperar_recaptcha,
    salvar_pagina_como_pdf,
)
from ..documento import TipoDoc

# Marca o campo "* Número do documento" para o Playwright preencher.
_TAG_CAMPO = r"""
() => {
  const vis = el => !!(el.offsetWidth || el.offsetHeight);
  const alvo = [...document.querySelectorAll('input[type=text]')].filter(vis).find(el => {
    let n = el;
    for (let i = 0; i < 4 && n; i++) {
      n = n.parentElement;
      if (n && (n.innerText || '').includes('Número do documento') && (n.innerText || '').includes('*'))
        return true;
    }
    return false;
  });
  if (alvo) { alvo.setAttribute('data-doc', '1'); return true; }
  return false;
}
"""

class POAISS(ModuloCertidao):
    id = "poa_iss"
    nome = "Comprovante ISSQN Porto Alegre"
    descricao = "Procempa/SIAT — reCAPTCHA resolve sozinho; se travar, você clica na janela."
    url = ("https://siat.procempa.com.br/siat/"
           "CpsEmitirComprovanteInscricao_Internet.do")
    requer_captcha = False  # a NopeCHA resolve sozinha
    implementado = True
    aceita = frozenset({TipoDoc.CNPJ})

    def executar(self, page, ctx: Contexto) -> Resultado:
        eh_cnpj = ctx.documento.tipo is TipoDoc.CNPJ
        ctx.log("POA ISS: abrindo o site…")
        page.goto(self.url, wait_until="domcontentloaded", timeout=60_000)
        page.wait_for_timeout(2_500)

        # Garante a aba "Emitir Inscrição" (ignora "Autenticar Inscrição").
        try:
            page.get_by_text("Emitir Inscrição", exact=True).first.click(timeout=4_000)
            page.wait_for_timeout(500)
        except Exception:
            pass

        # 1) Tenta já escolher o tipo e preencher (ordem natural).
        preenchido = self._preencher(page, ctx, eh_cnpj)

        # 2) Aguardar o reCAPTCHA: NopeCHA tenta sozinha; se travar, o usuário clica
        #    na janela (modo assistido) e o programa segue.
        ctx.log("POA ISS: resolvendo o captcha…")
        if not esperar_recaptcha(page, ctx, "POA ISS"):
            return Resultado(
                self.id, Status.ERRO,
                "O captcha (reCAPTCHA) não foi resolvido a tempo. Veja o print.",
            )
        page.wait_for_timeout(2_000)  # painel do captcha fecha

        # 3) Se o painel cobria o form, preenche agora.
        if not preenchido:
            preenchido = self._preencher(page, ctx, eh_cnpj)
        if not preenchido:
            return Resultado(self.id, Status.ERRO,
                             "Não consegui preencher o documento. Veja o print.")

        # 4) Confirmar → captura download ou nova aba.
        baixados: dict = {}
        page.on("download", lambda d: baixados.setdefault("d", d))
        nova: dict = {}
        page.context.on("page", lambda pg: nova.setdefault("p", pg))

        botao = page.locator("div.gwt-CustomButton:visible")
        ctx.log("POA ISS: emitindo…")
        botao.first.click(timeout=10_000)

        caminho = ctx.caminho_pdf(self.id)
        fim = time.time() + 40
        while time.time() < fim:
            if "d" in baixados:
                baixados["d"].save_as(str(caminho))
                ctx.log(f"POA ISS: PDF baixado em {caminho.name}")
                return Resultado(self.id, Status.OK, "Comprovante baixado.", caminho)
            if "p" in nova and not nova["p"].is_closed():
                aba = nova["p"]
                try:
                    aba.wait_for_load_state("networkidle", timeout=20_000)
                except Exception:
                    pass
                salvar_pagina_como_pdf(aba, caminho)
                ctx.log(f"POA ISS: comprovante salvo em {caminho.name}")
                return Resultado(self.id, Status.OK, "Comprovante salvo.", caminho)
            page.wait_for_timeout(1_500)

        return Resultado(self.id, Status.ERRO,
                         "Não obtive o documento após Confirmar. Veja o print.")

    def _preencher(self, page, ctx: Contexto, eh_cnpj: bool) -> bool:
        """Escolhe o tipo no <select> e digita o documento. True se conseguiu."""
        try:
            rotulo = "CNPJ" if eh_cnpj else "CPF"
            page.locator("select:visible").first.select_option(label=rotulo, timeout=5_000)
            page.wait_for_timeout(800)
            if not page.evaluate(_TAG_CAMPO):
                return False
            page.locator("[data-doc='1']").fill(ctx.documento.numero, timeout=8_000)
            valor = page.locator("[data-doc='1']").input_value()
            return ctx.documento.numero in valor.replace(".", "").replace("/", "").replace("-", "")
        except Exception:
            return False
