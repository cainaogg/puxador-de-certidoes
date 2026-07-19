"""Consulta CNPJ (Cartão CNPJ) — modo configurável.

Conforme as Configurações (config.consulta_cnpj_modo):
  - "navegador": abre o cnpjreva oficial no SEU navegador para você baixar
    manualmente (o site bloqueia automação — exige captcha).
  - "api": baixa automaticamente pela API da Infosimples (precisa do token).
"""

from __future__ import annotations

from .. import cnpj_publico, config, infosimples
from ..base import Contexto, ModuloCertidao, Resultado, Status, abrir_navegador
from ..documento import TipoDoc


class ConsultaCNPJ(ModuloCertidao):
    id = "consulta_cnpj"
    nome = "Consulta CNPJ (gov.br)"
    descricao = "Abre o cnpjreva oficial no navegador OU baixa pela API (ver Configurações)."
    url = cnpj_publico.CNPJREVA_URL
    requer_captcha = False
    implementado = True
    usa_api = True  # não usa o navegador Playwright; abre o do sistema OU usa a API
    aceita = frozenset({TipoDoc.CNPJ})

    def executar(self, page, ctx: Contexto) -> Resultado:
        modo = config.carregar().get("consulta_cnpj_modo", "navegador")
        if modo == "api":
            return self._via_api(ctx)
        return self._via_navegador(ctx)

    def _via_navegador(self, ctx: Contexto) -> Resultado:
        ctx.log("Consulta CNPJ: abrindo o cnpjreva oficial (CNPJ copiado — cole com Ctrl+V)…")
        try:
            abrir_navegador(self.url, ctx.documento.numero)
        except Exception as exc:  # noqa: BLE001
            return Resultado(self.id, Status.ERRO, f"Não consegui abrir o navegador: {exc}")
        return Resultado(
            self.id, Status.MANUAL,
            "Abri o cnpjreva — o CNPJ está no clipboard (Ctrl+V). Resolva o captcha e baixe o cartão.",
        )

    def _via_api(self, ctx: Contexto) -> Resultado:
        if not infosimples.token_configurado():
            return Resultado(
                self.id, Status.ERRO,
                "Token da Infosimples não configurado — abra Configurações e informe o token.",
            )
        ctx.log("Consulta CNPJ: consultando via API (Infosimples)…")
        try:
            res = infosimples.consultar("receita-federal/cnpj", cnpj=ctx.documento.numero)
        except infosimples.InfosimplesErro as exc:
            return Resultado(self.id, Status.ERRO, str(exc))

        code = res.get("code")
        if code == 200:
            caminho = ctx.caminho_pdf(self.id)
            if infosimples.baixar_recibo(res, caminho):
                ctx.log("Consulta CNPJ: cartão baixado via API.")
                return Resultado(self.id, Status.OK, "Cartão CNPJ baixado via API.", caminho)
            return Resultado(self.id, Status.ERRO, "API retornou OK, mas sem PDF.")

        msg = (res.get("code_message") or "").strip()
        return Resultado(
            self.id, Status.ERRO,
            f"Consulta CNPJ não liberou o cartão via API [code {code}]: {msg[:140]}",
        )
