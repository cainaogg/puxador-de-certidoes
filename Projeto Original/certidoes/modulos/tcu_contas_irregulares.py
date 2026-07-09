"""Certidão Negativa de Contas Julgadas Irregulares (TCU) — CPF/CNPJ.

Mesma plataforma da TCU Inidôneos (certidoes.apps.tcu.gov.br): usa ALTCHA
(prova-de-trabalho que o navegador resolve sozinho, sem interação do usuário).

ATENÇÃO: o formulário tem UM campo só, com um alternador CPF/CNPJ. Se o campo
estiver em modo CPF e digitarmos um CNPJ, ele aceita os 11 primeiros dígitos como
CPF e dá "CPF inválido". Por isso só preenchemos DEPOIS de confirmar (pelo
placeholder) que o campo está no modo certo. Mapeado 2026-06-22.
"""

from __future__ import annotations

import time

from . import _tcu
from ..base import Contexto, ModuloCertidao, Resultado, Status
from ..documento import TipoDoc


class TCUContasIrregulares(ModuloCertidao):
    id = "tcu_contas_irregulares"
    nome = "Certidão Negativa de Contas Julgadas Irregulares CNPJ (TCU)"
    descricao = "TCU — usa ALTCHA (resolve sozinho, sem captcha manual)."
    url = "https://certidoes.apps.tcu.gov.br/emitir-certidao-contas-julgadas-irregulares"
    requer_captcha = False
    implementado = True
    aceita = frozenset({TipoDoc.CPF, TipoDoc.CNPJ})

    def executar(self, page, ctx: Contexto) -> Resultado:
        ctx.log("TCU Contas Irregulares: abrindo o site…")
        page.goto(self.url, wait_until="domcontentloaded", timeout=60_000)
        page.wait_for_timeout(3_000)
        return _tcu.com_retry(page, ctx, self.url, "TCU Contas Irregulares",
                              lambda pg: self._tentar(pg, ctx))

    def _tentar(self, page, ctx: Contexto) -> Resultado:
        doc = ctx.documento
        # Garante o campo no modo certo (CPF/CNPJ) ANTES de digitar (ver _tcu).
        if not _tcu.garantir_modo(page, doc.tipo):
            return Resultado(
                self.id, Status.ERRO,
                f"TCU Contas: não consegui alternar o campo para {doc.tipo.value.upper()}. Veja o print.",
            )
        page.locator("input[type='text']").first.fill(doc.numero, timeout=15_000)
        page.wait_for_timeout(600)
        ctx.log("TCU Contas Irregulares: emitindo (ALTCHA resolvido automaticamente)…")
        page.click("#btn-emitir-certidao", timeout=15_000)

        # O ALTCHA leva alguns segundos; só depois surge "Baixar Certidão" (sucesso)
        # ou uma mensagem de erro/pendência. "irregular"/"consta" NÃO são erro (estão
        # no título; "nada consta" é o resultado negativo desejado).
        baixar = page.locator(
            "button:has-text('Baixar Certidão'), a:has-text('Baixar Certidão')"
        )
        erro = page.locator(
            "text=/inválido|verifique os|não foi possível|pendênc|excede|limite de/i"
        )
        fim = time.time() + 50
        while time.time() < fim:
            if baixar.count() and baixar.first.is_visible():
                return _tcu.baixar_para(page, ctx, self.id, baixar, "TCU Contas Irregulares")
            if erro.count() and erro.first.is_visible():
                msg = (erro.first.inner_text() or "").strip().replace("\n", " ")
                return Resultado(self.id, Status.ERRO, f"TCU Contas: {msg[:140]}")
            page.wait_for_timeout(2_000)

        msg = _tcu.mensagem_erro(page) or "'Baixar Certidão' não apareceu (o captcha expirou?)"
        return Resultado(self.id, Status.ERRO, f"TCU Contas: {msg}")
