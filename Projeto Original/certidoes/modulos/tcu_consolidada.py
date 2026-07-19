"""Consulta Consolidada de Pessoa Jurídica (TCU) — modo configurável.

Reúne TCU Inidôneos, CNJ (CNIA), CEIS e CNEP num único PDF. O subdomínio que
esse serviço usa via navegador (certidoes-apf.apps.tcu.gov.br) tem um WAF que
bloqueia qualquer navegador controlado por automação (Playwright/Puppeteer) —
testado: um navegador comum (do usuário) passa normalmente, o Playwright é
sempre rejeitado, mesmo com um perfil "envelhecido" (cookies/histórico reais).

Conforme as Configurações (config.tcu_consolidada_modo):
  - "navegador" (padrão): abre no SEU navegador — contorna o WAF porque não é
    um navegador automatizado.
  - "api": baixa automaticamente pela API da Infosimples (precisa do token) —
    também contorna o WAF, já que a consulta não passa pelo nosso navegador.
"""

from __future__ import annotations

from .. import config, infosimples
from ..base import Contexto, ModuloCertidao, Resultado, Status, abrir_navegador
from ..documento import TipoDoc


class TCUConsolidada(ModuloCertidao):
    id = "tcu_consolidada_pj"
    nome = "Consulta Consolidada TCU CNPJ (TCU)"
    descricao = ("TCU — consolida Inidôneos, CNJ, CEIS e CNEP. Abre no seu navegador OU "
                 "baixa pela API (ver Configurações) — o WAF do TCU bloqueia automação nesse serviço.")
    url = "https://certidoes-apf.apps.tcu.gov.br/"
    requer_captcha = False
    implementado = True
    manual = False
    usa_api = True  # não usa o navegador Playwright — abre o do sistema OU usa a API
    aceita = frozenset({TipoDoc.CNPJ})

    def executar(self, page, ctx: Contexto) -> Resultado:
        modo = config.carregar().get("tcu_consolidada_modo", "navegador")
        if modo == "api":
            return self._via_api(ctx)
        return self._via_navegador(ctx)

    def _via_navegador(self, ctx: Contexto) -> Resultado:
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

    def _via_api(self, ctx: Contexto) -> Resultado:
        if not infosimples.token_configurado():
            return Resultado(
                self.id, Status.ERRO,
                "Token da Infosimples não configurado — abra Configurações e informe o token.",
            )
        ctx.log("TCU Consolidada: consultando via API (Infosimples)…")
        try:
            res = infosimples.consultar("tcu/consolidada-pj", cnpj=ctx.documento.numero)
        except infosimples.InfosimplesErro as exc:
            return Resultado(self.id, Status.ERRO, str(exc))

        code = res.get("code")
        if code == 200:
            caminho = ctx.caminho_pdf(self.id)
            if infosimples.baixar_recibo(res, caminho):
                ctx.log("TCU Consolidada: PDF baixado via API.")
                return Resultado(self.id, Status.OK, "Consulta Consolidada baixada via API.", caminho)
            return Resultado(self.id, Status.ERRO, "API retornou OK, mas sem PDF.")

        msg = (res.get("code_message") or "").strip()
        return Resultado(
            self.id, Status.ERRO,
            f"TCU Consolidada não liberou o PDF via API [code {code}]: {msg[:140]}",
        )
