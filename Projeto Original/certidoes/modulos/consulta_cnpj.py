"""Consulta CNPJ (gov.br) — abre o cnpjreva oficial da Receita no navegador.

O site bloqueia automação (captcha), então é manual: o programa abre a página e o
usuário resolve o captcha e baixa o cartão CNPJ oficial (Status.MANUAL). Os dados
para nomear a pasta (razão social) vêm da API pública gratuita, à parte disto.
"""

from __future__ import annotations

import webbrowser

from .. import cnpj_publico
from ..base import Contexto, ModuloCertidao, Resultado, Status
from ..documento import TipoDoc


class ConsultaCNPJ(ModuloCertidao):
    id = "consulta_cnpj"
    nome = "Consulta CNPJ (gov.br)"
    descricao = "Abre o cnpjreva oficial no navegador para você baixar o cartão CNPJ."
    url = cnpj_publico.CNPJREVA_URL
    requer_captcha = False
    implementado = True
    usa_api = True  # não usa o navegador Playwright; abre o navegador do sistema
    aceita = frozenset({TipoDoc.CNPJ})

    def executar(self, page, ctx: Contexto) -> Resultado:
        ctx.log("Consulta CNPJ: abrindo o cnpjreva oficial no seu navegador…")
        try:
            webbrowser.open(self.url)
        except Exception as exc:  # noqa: BLE001
            return Resultado(self.id, Status.ERRO, f"Não consegui abrir o navegador: {exc}")
        return Resultado(
            self.id, Status.MANUAL,
            "Abri o cnpjreva no seu navegador — resolva o captcha e baixe o cartão CNPJ.",
        )
