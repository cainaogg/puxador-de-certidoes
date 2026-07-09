"""Consulta Consolidada de Pessoa Jurídica (TCU) — CNPJ.

Reúne TCU Inidôneos, CNJ (CNIA), CEIS e CNEP num único PDF. Sem captcha.
Fluxo: preenche o CNPJ, clica CONSULTAR, aguarda o processamento (consulta vários
órgãos) e clica em "BAIXAR PDF". Mapeado em 2026-06-20.
"""

from __future__ import annotations

import time

from ..base import Contexto, ModuloCertidao, Resultado, Status, salvar_pagina_como_pdf
from ..documento import TipoDoc


class TCUConsolidada(ModuloCertidao):
    id = "tcu_consolidada_pj"
    nome = "Consulta Consolidada TCU CNPJ (TCU)"
    descricao = "TCU — consolida Inidôneos, CNJ, CEIS e CNEP. Sem captcha."
    url = "https://certidoes-apf.apps.tcu.gov.br/"
    requer_captcha = False
    implementado = True
    aceita = frozenset({TipoDoc.CNPJ})

    def executar(self, page, ctx: Contexto) -> Resultado:
        ctx.log("TCU Consolidada: abrindo o site…")
        page.goto(self.url, wait_until="domcontentloaded", timeout=60_000)
        page.wait_for_timeout(3_000)
        if self._bloqueado(page):
            return self._erro_firewall()

        page.fill("#numero-cnpj", ctx.documento.numero, timeout=15_000)
        ctx.log("TCU Consolidada: consultando (pode demorar, consulta vários órgãos)…")
        page.get_by_role("button", name="CONSULTAR").first.click(timeout=15_000)

        # Aguarda (com limite) o "BAIXAR PDF" OU detecta o bloqueio do firewall do TCU.
        # A consulta consolidada pode demorar bastante (depende de vários órgãos).
        baixar = page.locator(
            "button:has-text('BAIXAR PDF'), a:has-text('BAIXAR PDF')"
        )
        inicio = time.time()
        fim = inicio + 180
        proximo_aviso = 30
        while time.time() < fim:
            if baixar.count() > 0 and baixar.first.is_visible():
                break
            if self._bloqueado(page):
                return self._erro_firewall()
            decorrido = int(time.time() - inicio)
            if decorrido >= proximo_aviso:
                ctx.log(f"TCU Consolidada: ainda processando… ({decorrido}s, aguarde)")
                proximo_aviso += 30
            page.wait_for_timeout(2_000)
        else:
            return Resultado(
                self.id, Status.ERRO,
                "TCU: a consulta consolidada demorou demais (site lento). "
                "Tente novamente. Veja o print.",
            )

        caminho = ctx.caminho_pdf(self.id)
        try:
            with page.expect_download(timeout=30_000) as info:
                baixar.first.click(timeout=15_000)
            info.value.save_as(str(caminho))
        except Exception:
            # Se abrir o PDF numa nova aba em vez de baixar, imprime essa aba.
            paginas = page.context.pages
            destino = paginas[-1] if len(paginas) > 1 else page
            salvar_pagina_como_pdf(destino, caminho)

        ctx.log(f"TCU Consolidada: salvo em {caminho.name}")
        return Resultado(self.id, Status.OK, "Consulta consolidada salva.", caminho)

    @staticmethod
    def _bloqueado(page) -> bool:
        """Detecta a tela de bloqueio do firewall (WAF) do TCU."""
        try:
            corpo = page.inner_text("body").lower()
        except Exception:
            return False
        return (
            "requisição rejeitada" in corpo
            or "bloqueado pela solução de firewall" in corpo
            or "acesso a este recurso foi bloqueado" in corpo
        )

    def _erro_firewall(self) -> Resultado:
        return Resultado(
            self.id, Status.ERRO,
            "O firewall do TCU bloqueou o acesso (acontece com muitos acessos "
            "seguidos). Tente novamente daqui a alguns minutos. Veja o print.",
        )
