"""Certidão Negativa da Receita Federal (RFB/PGFN) — modo configurável.

Conforme as Configurações (config.receita_modo):
  - "navegador": abre o site da Receita no SEU navegador para você emitir manualmente
    (funciona porque é o seu navegador confiável; a Receita bloqueia a automação).
  - "api": baixa automaticamente pela API da Infosimples (precisa do token).
    Para CPF, a API exige "birthdate" (data de nascimento, ISO 8601) — a mesma
    exigência do site da Receita. Sem data informada na lista, cai pro navegador.

    Testado com consulta paga real (2026-07): CNPJ baixou o PDF certinho. Para
    CPF, testei com um CPF fictício (só pra validar o formato) — a API aceitou
    os parâmetros (cpf + birthdate ISO) e repassou pro site de origem, que
    rejeitou por não achar o CPF cadastrado (esperado, é fictício); ou seja, o
    formato do pedido está correto, só não validei com dado de uma pessoa real.
"""

from __future__ import annotations

from .. import config, infosimples
from ..base import Contexto, ModuloCertidao, Resultado, Status, abrir_navegador
from ..documento import TipoDoc


def _data_iso(data_br: str) -> str:
    """Converte 'dd/mm/aaaa' -> 'aaaa-mm-dd' (ISO 8601, formato exigido pela API)."""
    d, m, a = data_br.strip().split("/")
    return f"{a}-{m.zfill(2)}-{d.zfill(2)}"


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
        modo = config.carregar().get("receita_modo", "navegador")
        if modo == "api":
            # Para CPF a API exige a data de nascimento (mesma exigência do site da
            # Receita). Sem ela informada na lista, não dá pra usar a API — cai pro
            # navegador, onde o usuário preenche à mão.
            if ctx.documento.tipo is TipoDoc.CPF and not ctx.data_nascimento:
                ctx.log("Receita: CPF sem data de nascimento na lista — a API exige, "
                        "abrindo no navegador…")
                return self._via_navegador(ctx)
            return self._via_api(ctx)
        return self._via_navegador(ctx)

    def _via_navegador(self, ctx: Contexto) -> Resultado:
        ctx.log("Receita: abrindo o site no seu navegador (número copiado — cole com Ctrl+V)…")
        try:
            # Para CPF, copia também a data de nascimento (se informada na lista).
            data = ctx.data_nascimento if ctx.documento.tipo is TipoDoc.CPF else ""
            abrir_navegador(self.url, ctx.documento.numero, data)
        except Exception as exc:  # noqa: BLE001
            return Resultado(self.id, Status.ERRO, f"Não consegui abrir o navegador: {exc}")
        return Resultado(
            self.id, Status.MANUAL,
            "Abri o site da Receita — o número está no clipboard (Ctrl+V). Emita a certidão lá.",
        )

    def _via_api(self, ctx: Contexto) -> Resultado:
        doc = ctx.documento
        if not infosimples.token_configurado():
            return Resultado(
                self.id, Status.ERRO,
                "Token da Infosimples não configurado — abra Configurações e informe o token.",
            )
        ctx.log("Receita: consultando via API (Infosimples)…")
        if doc.tipo is TipoDoc.CNPJ:
            params = {"cnpj": doc.numero}
        else:
            params = {"cpf": doc.numero, "birthdate": _data_iso(ctx.data_nascimento)}
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
