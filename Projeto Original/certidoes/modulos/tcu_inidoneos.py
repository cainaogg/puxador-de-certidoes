"""Certidão de Licitantes Inidôneos (TCU) — CPF/CNPJ.

Usa ALTCHA (captcha de prova-de-trabalho que o navegador resolve sozinho, sem
interação do usuário). Fluxo: preenche o documento, clica "Emitir certidão",
aguarda o ALTCHA resolver e o botão "Baixar Certidão" aparecer. Mapeado 2026-06-20.
"""

from __future__ import annotations

from . import _tcu
from ..base import Contexto, ModuloCertidao, Resultado, Status
from ..documento import TipoDoc


class TCUInidoneos(ModuloCertidao):
    id = "tcu_inidoneos"
    nome = "Certidão Negativa Licitantes Inidôneos CNPJ (TCU)"
    descricao = "TCU — usa ALTCHA (resolve sozinho, sem captcha manual)."
    url = "https://certidoes.apps.tcu.gov.br/emitir-certidao-inidoneos"
    requer_captcha = False
    implementado = True
    aceita = frozenset({TipoDoc.CPF, TipoDoc.CNPJ})

    def executar(self, page, ctx: Contexto) -> Resultado:
        ctx.log("TCU Inidôneos: abrindo o site…")
        page.goto(self.url, wait_until="domcontentloaded", timeout=60_000)
        page.wait_for_timeout(3_000)
        return _tcu.com_retry(page, ctx, self.url, "TCU Inidôneos",
                              lambda pg: self._tentar(pg, ctx))

    def _tentar(self, page, ctx: Contexto) -> Resultado:
        # Garante o campo no modo certo (a página começa em CNPJ; p/ CPF há o
        # botão "CPF"). Sem isso, um CPF cairia no campo CNPJ. Ver _tcu.
        if not _tcu.garantir_modo(page, ctx.documento.tipo):
            return Resultado(
                self.id, Status.ERRO,
                f"TCU Inidôneos: não consegui alternar o campo para "
                f"{ctx.documento.tipo.value.upper()}. Veja o print.",
            )
        page.locator("input[type='text']").first.fill(ctx.documento.numero, timeout=15_000)
        ctx.log("TCU Inidôneos: emitindo (o ALTCHA é resolvido automaticamente)…")
        page.click("#btn-emitir-certidao-inidoneos", timeout=15_000)

        # Após o ALTCHA, surge "Baixar Certidão" (ou um erro transitório do TCU).
        baixar = page.locator(
            "button:has-text('Baixar Certidão'), a:has-text('Baixar Certidão')"
        )
        try:
            baixar.first.wait_for(state="visible", timeout=45_000)
        except Exception:  # noqa: BLE001
            msg = _tcu.mensagem_erro(page) or "não apareceu 'Baixar Certidão' (o captcha expirou?)"
            return Resultado(self.id, Status.ERRO, f"TCU Inidôneos: {msg}")
        return _tcu.baixar_para(page, ctx, self.id, baixar, "TCU Inidôneos")
