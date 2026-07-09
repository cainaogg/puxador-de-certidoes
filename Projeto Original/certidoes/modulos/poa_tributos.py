"""Certidão de Débitos Tributários — Município de Porto Alegre (Procempa/SIAT).

Formulário GWT com **reCAPTCHA**, resolvido automaticamente pela extensão NopeCHA
(carregada pelo motor). Como o painel do reCAPTCHA cobre o formulário, a ordem é:
  1. Esperar a NopeCHA resolver o reCAPTCHA (o painel fecha).
  2. Selecionar CPF/CNPJ e preencher o documento.
  3. Clicar em "Confirmar" → a certidão abre em nova aba → salvar em PDF.

Os campos do GWT não têm id/nome; localizamos o campo do documento pelo rótulo
("* CNPJ"/"* CPF") via JS. Mapeado em 2026-06-20.
"""

from __future__ import annotations

from ..base import (
    Contexto,
    ModuloCertidao,
    Resultado,
    Status,
    esperar_recaptcha,
    salvar_pagina_como_pdf,
)
from ..documento import TipoDoc

# Marca o campo do documento (cujo rótulo tem "CNPJ"/"CPF" e "*") para preencher.
_TAG_CAMPO = r"""
(rotulo) => {
  const vis = el => !!(el.offsetWidth || el.offsetHeight);
  const alvo = [...document.querySelectorAll('input[type=text]')].filter(vis).find(el => {
    let n = el;
    for (let i = 0; i < 4 && n; i++) {
      n = n.parentElement;
      if (n && new RegExp(rotulo).test(n.innerText || '') && /\*/.test(n.innerText || ''))
        return true;
    }
    return false;
  });
  if (alvo) { alvo.setAttribute('data-doc', '1'); return true; }
  return false;
}
"""

class POATributos(ModuloCertidao):
    id = "poa_tributos"
    nome = "CND Municipal (POA)"
    descricao = "Procempa/SIAT — reCAPTCHA resolve sozinho; se travar, você clica na janela."
    url = ("https://siat.procempa.com.br/siat/"
           "ArrSolicitarCertidaoGeralDebTributarios_Internet.do")
    requer_captcha = False  # a NopeCHA resolve sozinha
    implementado = True
    aceita = frozenset({TipoDoc.CNPJ})

    def executar(self, page, ctx: Contexto) -> Resultado:
        eh_cnpj = ctx.documento.tipo is TipoDoc.CNPJ
        ctx.log("POA Tributos: abrindo o site…")
        page.goto(self.url, wait_until="domcontentloaded", timeout=60_000)
        page.wait_for_timeout(2_500)

        # Garante que estamos na aba "Emitir" (ignora a aba "Confirmar autenticidade").
        try:
            page.get_by_text("Emitir", exact=True).first.click(timeout=4_000)
            page.wait_for_timeout(500)
        except Exception:
            pass

        # 1) Tenta já preencher CNPJ + documento (ordem natural). Se o painel do
        #    captcha estiver cobrindo o formulário, deixa para preencher depois.
        preenchido = self._preencher(page, ctx, eh_cnpj)

        # 2) Aguardar o reCAPTCHA: NopeCHA tenta sozinha; se travar, o usuário clica
        #    na janela (modo assistido) e o programa segue.
        ctx.log("POA Tributos: resolvendo o captcha…")
        if not esperar_recaptcha(page, ctx, "POA Tributos"):
            return Resultado(
                self.id, Status.ERRO,
                "O captcha (reCAPTCHA) não foi resolvido a tempo. Veja o print.",
            )
        page.wait_for_timeout(2_000)  # painel do captcha fecha

        # 3) Se não deu para preencher antes (painel cobrindo), preenche agora.
        if not preenchido:
            preenchido = self._preencher(page, ctx, eh_cnpj)
        if not preenchido:
            return Resultado(self.id, Status.ERRO,
                             "Não consegui preencher o CNPJ. Veja o print.")

        # 4) Confirmar → captura o download (ou a certidão em nova aba).
        baixados: dict = {}
        page.on("download", lambda d: baixados.setdefault("d", d))
        nova: dict = {}
        page.context.on("page", lambda pg: nova.setdefault("p", pg))

        # O "Confirmar" é um GWT CustomButton (div role=button com imagem). O primeiro
        # visível desse tipo é o Confirmar (o segundo é o Limpar). Assim não há risco
        # de clicar na aba "Confirmar autenticidade".
        botao = page.locator("div.gwt-CustomButton:visible")
        ctx.log("POA Tributos: emitindo…")
        botao.first.click(timeout=10_000)

        caminho = ctx.caminho_pdf(self.id)
        import time
        fim = time.time() + 40
        while time.time() < fim:
            if "d" in baixados:
                baixados["d"].save_as(str(caminho))
                ctx.log(f"POA Tributos: PDF baixado em {caminho.name}")
                return Resultado(self.id, Status.OK, "Certidão baixada.", caminho)
            if "p" in nova and not nova["p"].is_closed():
                aba = nova["p"]
                try:
                    aba.wait_for_load_state("networkidle", timeout=20_000)
                except Exception:
                    pass
                salvar_pagina_como_pdf(aba, caminho)
                ctx.log(f"POA Tributos: certidão salva em {caminho.name}")
                return Resultado(self.id, Status.OK, "Certidão salva.", caminho)
            page.wait_for_timeout(1_500)

        return Resultado(self.id, Status.ERRO,
                         "Não obtive o documento após Confirmar. Veja o print.")

    def _preencher(self, page, ctx: Contexto, eh_cnpj: bool) -> bool:
        """Seleciona CPF/CNPJ e digita o documento. Retorna True se conseguiu."""
        try:
            page.locator("input[type=radio]:visible").nth(1 if eh_cnpj else 0).click(timeout=5_000)
            page.wait_for_timeout(1_000)
            rotulo = "CNPJ" if eh_cnpj else "CPF"
            if not page.evaluate(_TAG_CAMPO, rotulo):
                return False
            page.locator("[data-doc='1']").fill(ctx.documento.numero, timeout=8_000)
            valor = page.locator("[data-doc='1']").input_value()
            return ctx.documento.numero in valor.replace(".", "").replace("/", "").replace("-", "")
        except Exception:
            return False
