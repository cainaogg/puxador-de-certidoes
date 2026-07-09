"""Certidão de Situação Fiscal — SEFAZ-RS (CPF/CNPJ).

Usa ALTCHA (prova-de-trabalho que resolve sozinho ao marcar "Eu não sou um robô").
Fluxo: preenche CPF/CNPJ, marca o ALTCHA, espera resolver, clica Enviar e captura
o PDF gerado. Mapeado em 2026-06-20.
"""

from __future__ import annotations

from ..base import Contexto, ModuloCertidao, Resultado, Status, salvar_pagina_como_pdf
from ..documento import TipoDoc

# Texto que indica que a certidão não pôde ser emitida (ex.: pendências).
MSGS_ERRO = ["não foi possível", "pendência", "irregular", "débito"]


class SefazRS(ModuloCertidao):
    id = "sefaz_rs"
    nome = "CND Estadual (SEFAZ-RS)"
    descricao = "Receita Estadual RS — usa ALTCHA (resolve sozinho)."
    url = "https://www.sefaz.rs.gov.br/sat/CertidaoSitFiscalSolic.aspx"
    requer_captcha = False
    implementado = True
    aceita = frozenset({TipoDoc.CNPJ})

    def executar(self, page, ctx: Contexto) -> Resultado:
        ctx.log("SEFAZ-RS: abrindo o site…")
        page.goto(self.url, wait_until="domcontentloaded", timeout=60_000)
        page.wait_for_timeout(3_000)

        campo = "campoCnpj" if ctx.documento.tipo is TipoDoc.CNPJ else "campoCpf"
        page.fill(f"input[name='{campo}']", ctx.documento.numero, timeout=15_000)

        # ALTCHA: marca o checkbox para iniciar a prova-de-trabalho.
        ctx.log("SEFAZ-RS: resolvendo o ALTCHA (automático)…")
        cb = page.locator("input[id^='altcha_checkbox'], .altcha-checkbox input")
        if cb.count() > 0:
            try:
                cb.first.click(timeout=5_000)
            except Exception:
                pass
        # Espera o token do ALTCHA ser gerado.
        for _ in range(25):
            page.wait_for_timeout(1_000)
            tamanho = page.evaluate(
                "() => { const e = document.querySelector(\"input[name='altcha']\");"
                " return e ? (e.value || '').length : 0; }"
            )
            if tamanho and tamanho > 0:
                break

        # Enviar e capturar o PDF.
        baixados: dict = {}
        page.on("download", lambda d: baixados.setdefault("d", d))
        ctx.log("SEFAZ-RS: enviando…")
        page.click("#btnEnviar", timeout=15_000)

        for _ in range(25):
            page.wait_for_timeout(1_000)
            if "d" in baixados:
                break

        caminho = ctx.caminho_pdf(self.id)
        if "d" in baixados:
            baixados["d"].save_as(str(caminho))
            ctx.log(f"SEFAZ-RS: salvo em {caminho.name}")
            return Resultado(self.id, Status.OK, "Certidão salva.", caminho)

        # Sem download: pode ter aberto numa nova aba, ou exibido erro.
        paginas = page.context.pages
        if len(paginas) > 1:
            destino = paginas[-1]
            destino.wait_for_load_state("networkidle", timeout=20_000)
            salvar_pagina_como_pdf(destino, caminho)
            return Resultado(self.id, Status.OK, "Certidão salva (nova aba).", caminho)

        corpo = page.inner_text("body").lower()
        if any(m in corpo for m in MSGS_ERRO):
            return Resultado(
                self.id, Status.ERRO,
                "SEFAZ-RS não emitiu (possível pendência/débito). Veja o print.",
            )
        return Resultado(
            self.id, Status.ERRO,
            "SEFAZ-RS: não obtive o PDF (layout pode ter mudado). Veja o print.",
        )
