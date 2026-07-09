"""Certidão Negativa Correcional — CGU (Controladoria-Geral da União).

App BootstrapVue com **hCaptcha de imagens (Enterprise)** que a NopeCHA não resolve.
Opera em MODO ASSISTIDO: o programa abre, escolhe "Ente Privado", preenche o
CPF/CNPJ e clica em Consultar; aí PARA para o usuário resolver o captcha de imagens.
Depois captura o PDF gerado. (A NopeCHA fica desativada neste host — ver manifest.)

Fluxo mapeado em 2026-06-20. Se a CGU bloquear a automação como a Receita, este
módulo deve virar `manual = True`.
"""

from __future__ import annotations

import time

from ..base import Contexto, ModuloCertidao, Resultado, Status, salvar_pagina_como_pdf
from ..documento import TipoDoc

TIMEOUT_CAPTCHA_S = 5 * 60

_CLICAR_EMITIR = """
() => {
  const a = [...document.querySelectorAll('button,a')].find(
    e => (e.innerText || '').includes('Emitir Certidão de Entes Privados'));
  if (a) a.click();
  return !!a;
}
"""


class CGUCorrecional(ModuloCertidao):
    id = "cgu_correcional"
    nome = "Consulta CEIS CNPJ (CGU)"
    descricao = "CGU — hCaptcha de imagens (modo assistido: você resolve o captcha)."
    url = "https://certidoes.cgu.gov.br/"
    requer_captcha = True
    implementado = True
    aceita = frozenset({TipoDoc.CPF, TipoDoc.CNPJ})

    def executar(self, page, ctx: Contexto) -> Resultado:
        ctx.log("CGU: abrindo o site…")
        page.goto(self.url, wait_until="domcontentloaded", timeout=60_000)
        page.wait_for_timeout(6_000)

        # 1) Entrar em "Emitir Certidão de Entes Privados ou Agentes Públicos".
        if not page.evaluate(_CLICAR_EMITIR):
            return Resultado(self.id, Status.ERRO,
                             "Não achei a opção 'Emitir Certidão de Entes Privados'. Veja o print.")
        page.wait_for_timeout(5_000)

        # 2) Selecionar "Ente Privado" (a certidão correcional já vem marcada).
        try:
            page.get_by_text("Ente Privado", exact=False).first.click(timeout=10_000)
            page.wait_for_timeout(2_000)
        except Exception:
            pass

        # 3) Preencher o CPF/CNPJ.
        page.fill("#cpfCnpj", ctx.documento.numero, timeout=15_000)

        # 4) Consultar → aparece o captcha de imagens.
        page.click("#consultar", timeout=15_000)

        # 5) Pedir para o usuário resolver o captcha.
        ctx.aguardar_captcha(
            "CGU: resolva o captcha de imagens na janela do navegador (selecione as "
            "figuras pedidas) e confirme. O programa vai capturar o documento."
        )

        # 6) Aguardar o resultado (download / nova aba). Se aparecer um botão de
        #    baixar/visualizar/emitir após o captcha, clica nele.
        baixados: dict = {}
        page.on("download", lambda d: baixados.setdefault("d", d))
        nova: dict = {}
        page.context.on("page", lambda pg: nova.setdefault("p", pg))

        caminho = ctx.caminho_pdf(self.id)
        clicou_certidao = False
        fim = time.time() + TIMEOUT_CAPTCHA_S
        while time.time() < fim:
            if "d" in baixados:
                baixados["d"].save_as(str(caminho))
                ctx.log(f"CGU: PDF baixado em {caminho.name}")
                return Resultado(self.id, Status.OK, "Certidão baixada.", caminho)
            if "p" in nova and not nova["p"].is_closed():
                aba = nova["p"]
                try:
                    aba.wait_for_load_state("networkidle", timeout=20_000)
                except Exception:
                    pass
                salvar_pagina_como_pdf(aba, caminho)
                ctx.log(f"CGU: certidão salva em {caminho.name}")
                return Resultado(self.id, Status.OK, "Certidão salva.", caminho)
            # Depois do captcha, surge a tabela de resultado com o botão "Certidão"
            # (coluna Emissão). Clica nele (uma vez) para baixar/abrir o PDF.
            if not clicou_certidao and not page.is_closed():
                try:
                    bc = page.locator("button:has-text('Certidão'), a:has-text('Certidão')")
                    if bc.count() > 0 and bc.first.is_visible():
                        bc.first.click(timeout=5_000)
                        clicou_certidao = True
                        ctx.log("CGU: captcha resolvido; baixando a certidão…")
                except Exception:
                    pass
            page.wait_for_timeout(2_000)

        return Resultado(self.id, Status.ERRO,
                         "CGU: não obtive o documento (captcha não resolvido?). Veja o print.")
