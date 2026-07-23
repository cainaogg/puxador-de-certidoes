"""Certificado de Regularidade do FGTS (CRF) — Caixa Econômica Federal.

Fluxo (sem CAPTCHA):
  1. Seleciona o tipo de inscrição (CNPJ/CPF).
  2. Preenche a inscrição (somente dígitos).
  3. Clica em "Consultar".
  4. Na tela de resultado, abre o certificado e o salva em PDF.

OBS: os seletores abaixo são a melhor aproximação do formulário JSF da Caixa e
podem precisar de ajuste fino contra o site real. Pontos marcados com
`# AJUSTAR` são os candidatos mais prováveis de mudança.
"""

from __future__ import annotations

from ..base import (
    Contexto,
    ModuloCertidao,
    Resultado,
    Status,
    abrir_site_ou_manual,
    salvar_pagina_como_pdf,
)
from ..documento import TipoDoc


class FGTS(ModuloCertidao):
    id = "fgts_crf"
    nome = "Certificado FGTS (CRF)"
    descricao = "Caixa Econômica Federal — regularidade do FGTS."
    url = "https://consulta-crf.caixa.gov.br/consultacrf/pages/consultaEmpregador.jsf"
    requer_captcha = False
    implementado = True
    aceita = frozenset({TipoDoc.CNPJ, TipoDoc.CPF})

    # IDs reais do formulário JSF da Caixa (mapeados em 2026-06-19).
    SEL_TIPO = '[id="mainForm:tipoEstabelecimento"]'   # <select> CNPJ/CPF
    SEL_INSCRICAO = '[id="mainForm:txtInscricao1"]'    # campo da inscrição
    SEL_CONSULTAR = '[id="mainForm:btnConsultar"]'     # botão Consultar
    SEL_VISUALIZAR = '[id="mainForm:btnVisualizar"]'   # etapa 3: botão Visualizar
    SEL_IMPRIMIR = '[id="mainForm:btImprimir4"]'       # etapa 4: certificado final
    SEL_VOLTAR_FINAL = '[id="mainForm:btVoltar3"]'

    def executar(self, page, ctx: Contexto) -> Resultado:
        # CPF: só tem certificado quem é "empregador doméstico" registrado na Caixa.
        # Testado com CPF real em 2026-07: o site aceita, navega e responde
        # normalmente ("não encontrado" para quem não tem cadastro) — o formulário
        # não rejeita CPF. Os passos de Visualizar/Imprimir são iguais ao fluxo CNPJ.
        ctx.log("FGTS: abrindo o site da Caixa…")
        if not abrir_site_ou_manual(page, ctx, "FGTS", self.url):
            return Resultado(self.id, Status.MANUAL,
                             "O site da Caixa não respondeu a tempo. Abri no seu navegador padrão.")

        # 1) Tipo de inscrição é um <select> com as opções CNPJ/CPF.
        rotulo = "CNPJ" if ctx.documento.tipo is TipoDoc.CNPJ else "CPF"
        page.select_option(self.SEL_TIPO, label=rotulo, timeout=15_000)

        # 2) Campo da inscrição (somente dígitos).
        page.fill(self.SEL_INSCRICAO, ctx.documento.numero, timeout=15_000)

        # 3) UF fica em branco para CNPJ completo (conforme orientação do site).

        # 4) Consultar.
        ctx.log("FGTS: consultando…")
        page.click(self.SEL_CONSULTAR, timeout=15_000)
        page.wait_for_load_state("networkidle", timeout=60_000)

        # 5) Etapa 2 (Situação de Regularidade): clicar no link do certificado.
        #    Tudo a seguir navega na MESMA aba via AJAX.
        link = page.get_by_role("link", name="Certificado de Regularidade do FGTS - CRF")
        if link.count() == 0:
            link = page.locator("a:has-text('Certificado de Regularidade')")
        if link.count() == 0:
            texto = (page.inner_text("body")[:300]).strip()
            ctx.log(f"FGTS: link do certificado não encontrado. Tela diz: {texto!r}")
            return Resultado(
                self.id, Status.ERRO,
                "Não localizei o certificado (empresa pode estar irregular "
                "ou o layout mudou). Veja a screenshot.",
            )
        link.first.click(timeout=15_000)

        # 6) Etapa 3: aguardar e clicar em "Visualizar".
        page.wait_for_selector(self.SEL_VISUALIZAR, timeout=30_000)
        page.click(self.SEL_VISUALIZAR, timeout=15_000)

        # 7) Etapa 4: aguardar o certificado final (botão Imprimir) e salvar em PDF.
        #    Salvamos exatamente o que aparece ao clicar Imprimir > Salvar como PDF
        #    (inclui a logomarca da CAIXA; salvar_pagina_como_pdf espera as imagens).
        page.wait_for_selector(self.SEL_IMPRIMIR, timeout=30_000)

        caminho = ctx.caminho_pdf(self.id)
        salvar_pagina_como_pdf(page, caminho)
        ctx.log(f"FGTS: certificado salvo em {caminho.name}")
        return Resultado(self.id, Status.OK, "Certificado salvo.", caminho)
