"""Consulta Consolidada de Pessoa Jurídica (TCU) — CNPJ.

Reúne TCU Inidôneos, CNJ (CNIA), CEIS e CNEP num único PDF. O subdomínio que
esse serviço usa (certidoes-apf.apps.tcu.gov.br) tem um WAF que bloqueia
qualquer navegador controlado por automação (Playwright/Puppeteer) — testado:
um navegador comum (do usuário) passa normalmente, o Playwright é sempre
rejeitado, mesmo com um perfil "envelhecido" (cookies/histórico reais) e sem
nenhuma tentativa da nossa parte. Sem solução de automação viável — abre no
navegador do sistema, como a Receita Federal.
"""

from __future__ import annotations

from ..base import Contexto, ModuloCertidao, Resultado, Status, abrir_navegador
from ..documento import TipoDoc


class TCUConsolidada(ModuloCertidao):
    id = "tcu_consolidada_pj"
    nome = "Consulta Consolidada TCU CNPJ (TCU)"
    descricao = ("TCU — consolida Inidôneos, CNJ, CEIS e CNEP. Abre no seu navegador "
                 "(o WAF do TCU bloqueia automação nesse serviço).")
    url = "https://certidoes-apf.apps.tcu.gov.br/"
    requer_captcha = False
    implementado = True
    manual = False
    usa_api = True  # não usa o navegador Playwright — abre o do sistema
    aceita = frozenset({TipoDoc.CNPJ})

    def executar(self, page, ctx: Contexto) -> Resultado:
        ctx.log("TCU Consolidada: abrindo o site no seu navegador (número copiado — cole com Ctrl+V)…")
        try:
            abrir_navegador(self.url, ctx.documento.numero)
        except Exception as exc:  # noqa: BLE001
            return Resultado(self.id, Status.ERRO, f"Não consegui abrir o navegador: {exc}")
        return Resultado(
            self.id, Status.MANUAL,
            "Abri a Consulta Consolidada (TCU) — o CNPJ está no clipboard (Ctrl+V). "
            "Consulte e baixe o PDF manualmente lá.",
        )
