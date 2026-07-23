"""Comprovante de Inscrição no ISS — Município de Porto Alegre (Procempa/SIAT).

Mesmo padrão da POA Tributos (GWT + reCAPTCHA resolvido pela NopeCHA), com duas
diferenças: o tipo é um <select> (CPF/CNPJ/…) e o campo é "* Número do documento".
A aba correta é "Emitir Inscrição" (ignorar "Autenticar Inscrição"). 2026-06-20.
"""

from __future__ import annotations

from ..base import (
    Contexto,
    ModuloCertidao,
    Resultado,
    Status,
    abrir_site_ou_manual,
    emitir_e_capturar,
    esperar_recaptcha,
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
    aceita = frozenset({TipoDoc.CNPJ, TipoDoc.CPF})

    def executar(self, page, ctx: Contexto) -> Resultado:
        eh_cnpj = ctx.documento.tipo is TipoDoc.CNPJ
        ctx.log("POA ISS: abrindo o site…")
        if not abrir_site_ou_manual(page, ctx, "POA ISS", self.url):
            return Resultado(self.id, Status.MANUAL,
                             "O site da Procempa não respondeu a tempo. Abri no seu navegador padrão.")
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

        # 4) Confirmar → captura o download OU a certidão em nova aba (robusto a
        #    navegador que força baixar o PDF por uma aba que fecha na hora).
        ctx.log("POA ISS: emitindo…")
        def _confirmar() -> None:
            page.locator("div.gwt-CustomButton:visible").first.click(timeout=10_000)
        res = emitir_e_capturar(page, ctx, self.id, "POA ISS", _confirmar)
        if res.status is not Status.OK:
            try:
                corpo = page.inner_text("body")
            except Exception:  # noqa: BLE001
                corpo = ""
            if "não foi localizado cadastro" in corpo.lower():
                return Resultado(
                    self.id, Status.ERRO,
                    "Não há inscrição de ISSQN cadastrada para este documento (não é "
                    "aplicável a quem não presta serviço autônomo registrado).",
                )
        return res

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
