"""Certidão Negativa de Improbidade Administrativa e Inelegibilidade (CNJ).

Automatizado via Playwright. O formulário tem **reCAPTCHA v2** (o mesmo que a
NopeCHA resolve no POA; se travar, você clica na janela — modo assistido). Fluxo:
  1. marca Jurídica/Física, preenche CPF/CNPJ (dígitos) e o Nome;
  2. resolve o 1º reCAPTCHA e clica "Pesquisar";
  3. quando surge "Gerar Certidão Negativa", resolve o 2º reCAPTCHA e clica;
  4. captura o download da certidão.

O Nome (razão social do CNPJ vem da BrasilAPI; do CPF, o usuário informa na mesma
linha) é limpo para letras/números (o CNJ rejeita acentos e símbolos). Se não
houver nome ou a consulta falhar, cai no modo manual. Mapeado em 2026-07-09.
"""

from __future__ import annotations

import webbrowser

from .. import cnpj_publico
from ..base import (
    Contexto,
    ModuloCertidao,
    Resultado,
    Status,
    abrir_site_ou_manual,
    emitir_e_capturar,
    esperar_recaptcha,
    so_letras_numeros,
)
from ..documento import TipoDoc


class CNJImprobidade(ModuloCertidao):
    id = "cnj_improbidade"
    nome = "Certidão Negativa de Improb. Admin e Ineleg. CNPJ (CNJ)"
    descricao = "CNJ — preenche e emite sozinho (reCAPTCHA resolvido pela NopeCHA/assistido)."
    url = "https://www.cnj.jus.br/improbidade_adm/consultar_requerido.php?validar=form"
    requer_captcha = True
    implementado = True
    aceita = frozenset({TipoDoc.CPF, TipoDoc.CNPJ})

    SEL_CPF_CNPJ = "#num_cpf_cnpj"
    SEL_NOME = "#nom_requerido"
    SEL_PESQUISAR = "#btnPesquisarRequerido"
    SEL_NEGATIVA = "#btnCertidaoNegativa"
    SEL_POSITIVA = "#btnCertidaoPositiva"

    def executar(self, page, ctx: Contexto) -> Resultado:
        eh_cnpj = ctx.documento.tipo is TipoDoc.CNPJ

        # 1) Nome: CNPJ -> BrasilAPI; CPF -> informado pelo usuário na mesma linha.
        if eh_cnpj:
            ctx.log("CNJ: consultando a razão social do CNPJ…")
            dados = cnpj_publico.consultar(ctx.documento.numero)
            nome = so_letras_numeros((dados or {}).get("razao_social")
                                     or (dados or {}).get("nome") or "")
        else:
            nome = so_letras_numeros(ctx.nome_informado or "")
        if not nome:
            motivo = ("não obtive a razão social do CNPJ" if eh_cnpj
                      else "não foi informado o nome do CPF (inclua o nome na mesma linha)")
            return self._fallback_manual(ctx, motivo, eh_cnpj)

        # 2) Preencher o formulário.
        ctx.log("CNJ: abrindo o formulário…")
        if not abrir_site_ou_manual(page, ctx, "CNJ", self.url):
            return Resultado(self.id, Status.MANUAL,
                             "O site do CNJ não respondeu a tempo. Abri no seu navegador padrão.")
        page.wait_for_timeout(3_000)
        page.check("#tipoPessoaJuridica" if eh_cnpj else "#tipoPessoaFisica")
        page.fill(self.SEL_CPF_CNPJ, ctx.documento.numero)  # dígitos (maxlength 14)
        page.fill(self.SEL_NOME, nome)
        ctx.log(f"CNJ: pesquisando '{nome}'…")

        # 3) 1º reCAPTCHA + Pesquisar.
        if not esperar_recaptcha(page, ctx, "CNJ (1/2)"):
            return Resultado(self.id, Status.ERRO,
                             "O reCAPTCHA não foi resolvido a tempo. Veja o print.")
        page.click(self.SEL_PESQUISAR, timeout=10_000)

        # 4) Aguardar o resultado: botão Negativa (limpo) ou Positiva (há registros).
        try:
            page.wait_for_selector(self.SEL_NEGATIVA, state="visible", timeout=30_000)
        except Exception:  # noqa: BLE001
            try:
                if page.locator(self.SEL_POSITIVA).is_visible():
                    return Resultado(self.id, Status.ERRO,
                                     "CNJ: constam registros (certidão POSITIVA) — analise manualmente.")
            except Exception:  # noqa: BLE001
                pass
            return Resultado(self.id, Status.ERRO,
                             "CNJ: a pesquisa não retornou o botão de certidão (captcha?). Veja o print.")

        # 5) 2º reCAPTCHA + Gerar Certidão Negativa → captura o download.
        page.wait_for_timeout(1_000)
        ctx.log("CNJ: resolvendo o 2º reCAPTCHA…")
        if not esperar_recaptcha(page, ctx, "CNJ (2/2)"):
            return Resultado(self.id, Status.ERRO,
                             "O 2º reCAPTCHA não foi resolvido a tempo. Veja o print.")

        def _gerar() -> None:
            page.click(self.SEL_NEGATIVA, timeout=10_000)

        return emitir_e_capturar(page, ctx, self.id, "CNJ", _gerar)

    def _fallback_manual(self, ctx: Contexto, motivo: str, eh_cnpj: bool) -> Resultado:
        ctx.log(f"CNJ: {motivo} — abrindo o site para emissão manual.")
        try:
            webbrowser.open(self.url)
        except Exception:  # noqa: BLE001
            pass
        tipo = "Jurídica" if eh_cnpj else "Física"
        return Resultado(
            self.id, Status.MANUAL,
            f"Abri o CNJ no seu navegador — marque '{tipo}', preencha o "
            f"{'CNPJ' if eh_cnpj else 'CPF'} e o Nome, resolva o captcha, clique em "
            "'Pesquisar' e depois em 'Gerar Certidão Negativa'.",
        )
