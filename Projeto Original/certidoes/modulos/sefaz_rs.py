"""Certidão de Situação Fiscal — SEFAZ-RS (CPF/CNPJ).

Usa ALTCHA (prova-de-trabalho que resolve sozinho ao marcar "Eu não sou um robô").
Fluxo: preenche CPF/CNPJ, marca o ALTCHA, espera resolver, clica Enviar e captura
o PDF gerado. Mapeado em 2026-06-20.

CPF testado com documento real em 2026-07: quando a certidão é NEGATIVA, o fluxo
é igual ao CNPJ. Quando é POSITIVA (há débito), o site exige login do titular
(gov.br) e mostra uma tela de aviso em vez do PDF — detectado via MSG_EXIGE_LOGIN
e reportado como erro claro (não confundir com sucesso).
"""

from __future__ import annotations

from ..base import Contexto, ModuloCertidao, Resultado, Status, salvar_pagina_como_pdf
from ..documento import TipoDoc

# Texto que indica que a certidão não pôde ser emitida (ex.: pendências).
MSGS_ERRO = ["não foi possível", "pendência", "irregular", "débito"]

# Quando a certidão dá "positiva" (há débito), o site exige login extra do titular
# e mostra esta tela de aviso em vez do PDF — não é a certidão.
MSG_EXIGE_LOGIN = "disponíveis apenas para o sujeito da certidão"


class SefazRS(ModuloCertidao):
    id = "sefaz_rs"
    nome = "CND Estadual (SEFAZ-RS)"
    descricao = "Receita Estadual RS — usa ALTCHA (resolve sozinho)."
    url = "https://www.sefaz.rs.gov.br/sat/CertidaoSitFiscalSolic.aspx"
    requer_captcha = False
    implementado = True
    aceita = frozenset({TipoDoc.CNPJ, TipoDoc.CPF})

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

        # Sem download: pode ter aberto numa nova aba, ou exibido erro. O site às
        # vezes mantém abas extras (ex.: about:blank) — a aba de resultado real é a
        # "_result.aspx"; pegar cegamente a última aba pode capturar a errada.
        paginas = page.context.pages
        destino = next((p for p in paginas if "_result" in p.url.lower()), None)
        if destino is None and len(paginas) > 1:
            destino = paginas[-1]
        if destino is not None:
            destino.wait_for_load_state("networkidle", timeout=20_000)
            corpo_destino = destino.inner_text("body")
            if MSG_EXIGE_LOGIN in corpo_destino:
                return Resultado(
                    self.id, Status.ERRO,
                    "SEFAZ-RS: a certidão deu positiva (há débito) e o site exige login "
                    "do próprio titular para emiti-la — não dá para automatizar. Acesse "
                    "o site e faça login com o gov.br do titular.",
                )
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
