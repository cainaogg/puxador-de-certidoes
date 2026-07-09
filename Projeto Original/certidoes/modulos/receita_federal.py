"""Certidão Negativa da Receita Federal (RFB/PGFN) — modo configurável.

Conforme as Configurações (config.receita_modo):
  - "navegador": abre o site da Receita no SEU navegador para você emitir manualmente
    (funciona porque é o seu navegador confiável; a Receita bloqueia a automação).
  - "api": baixa automaticamente pela API da Infosimples (precisa do token).
"""

from __future__ import annotations

import webbrowser

from .. import config, infosimples
from ..base import Contexto, ModuloCertidao, Resultado, Status
from ..documento import TipoDoc


class ReceitaFederal(ModuloCertidao):
    id = "receita_federal"
    nome = "CND Federal CNPJ (RFB/PGFN)"
    descricao = "Receita Federal — abre no navegador OU baixa pela API (ver Configurações)."
    url = "https://servicos.receitafederal.gov.br/servico/certidoes/#/home"
    requer_captcha = False
    implementado = True
    manual = False
    usa_api = True  # não usa o navegador Playwright (abre o do sistema ou usa a API)
    aceita = frozenset({TipoDoc.CPF, TipoDoc.CNPJ})

    def executar(self, page, ctx: Contexto) -> Resultado:
        # Para CPF a Receita exige a data de nascimento; o programa original não a
        # coleta — então sempre abre o site para emissão manual (decisão do usuário).
        if ctx.documento.tipo is TipoDoc.CPF:
            return self._via_navegador(ctx)
        modo = config.carregar().get("receita_modo", "navegador")
        if modo == "api":
            return self._via_api(ctx)
        return self._via_navegador(ctx)

    def _via_navegador(self, ctx: Contexto) -> Resultado:
        ctx.log("Receita: abrindo o site no seu navegador para emissão manual…")
        try:
            webbrowser.open(self.url)
        except Exception as exc:  # noqa: BLE001
            return Resultado(self.id, Status.ERRO, f"Não consegui abrir o navegador: {exc}")
        return Resultado(
            self.id, Status.MANUAL,
            "Abri o site da Receita no seu navegador — emita a certidão manualmente lá.",
        )

    def _via_api(self, ctx: Contexto) -> Resultado:
        doc = ctx.documento
        if not infosimples.token_configurado():
            return Resultado(
                self.id, Status.ERRO,
                "Token da Infosimples não configurado — abra Configurações e informe o token.",
            )
        ctx.log("Receita: consultando via API (Infosimples)…")
        params = {"cnpj": doc.numero} if doc.tipo is TipoDoc.CNPJ else {"cpf": doc.numero}
        try:
            res = infosimples.consultar("receita-federal/pgfn", **params)
        except infosimples.InfosimplesErro as exc:
            return Resultado(self.id, Status.ERRO, str(exc))

        code = res.get("code")
        if code == 200:
            caminho = ctx.caminho_pdf(self.id)
            if infosimples.baixar_recibo(res, caminho):
                dado = infosimples.primeiro_dado(res) or {}
                validade = dado.get("validade_data") or ""
                ctx.log(f"Receita: CND baixada via API (validade {validade}).")
                return Resultado(
                    self.id, Status.OK,
                    f"Certidão baixada via API. Validade: {validade}", caminho,
                )
            return Resultado(self.id, Status.ERRO, "API retornou OK, mas sem PDF.")

        msg = (res.get("code_message") or "").strip()
        return Resultado(
            self.id, Status.ERRO,
            f"Receita não liberou a certidão (pode ter pendências) [code {code}]: {msg[:140]}",
        )
