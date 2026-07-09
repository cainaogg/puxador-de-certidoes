"""Certidão Negativa de Débitos Trabalhistas (CNDT) — TST.

Este site exige CAPTCHA, então o módulo opera em MODO ASSISTIDO:
  1. Abre o site e clica em "Emitir Certidão".
  2. Preenche o CPF/CNPJ automaticamente.
  3. Para e pede ao usuário para resolver o CAPTCHA e confirmar a emissão.
  4. Captura o PDF gerado (download) e o salva.

Seletores marcados com `# AJUSTAR` são os candidatos mais prováveis de mudar.
"""

from __future__ import annotations

from ..base import Contexto, ModuloCertidao, Resultado, Status
from ..documento import TipoDoc

# Tempo máximo que esperamos o usuário resolver o CAPTCHA e emitir (5 min).
TIMEOUT_CAPTCHA_MS = 5 * 60 * 1000


class CNDT(ModuloCertidao):
    id = "cndt_trabalhista"
    nome = "CND Trabalhista (CNDT)"
    descricao = "TST — exige CAPTCHA (modo assistido)."
    url = "https://cndt-certidao.tst.jus.br/inicio.faces"
    requer_captcha = True
    implementado = True
    aceita = frozenset({TipoDoc.CNPJ})

    # IDs reais do formulário JSF do TST (mapeados em 2026-06-20).
    SEL_CPF_CNPJ = '[id="gerarCertidaoForm:cpfCnpj"]'
    SEL_CAMPO_CAPTCHA = "#idCampoResposta"

    def executar(self, page, ctx: Contexto) -> Resultado:
        ctx.log("CNDT: abrindo o site do TST…")
        page.goto(self.url, wait_until="domcontentloaded", timeout=60_000)

        # 1) Botão "Emitir Certidão" na página inicial (leva ao formulário).
        page.get_by_role("button", name="Emitir Certidão", exact=True).first.click(timeout=15_000)
        page.wait_for_load_state("networkidle", timeout=30_000)

        # 2) Preencher o CPF/CNPJ automaticamente.
        try:
            page.fill(self.SEL_CPF_CNPJ, ctx.documento.numero, timeout=15_000)
            ctx.log("CNDT: CPF/CNPJ preenchido automaticamente.")
        except Exception:
            ctx.log("CNDT: não consegui preencher o documento — preencha manualmente.")

        # 3) Levar o foco para o campo do CAPTCHA e aguardar o usuário.
        try:
            page.click(self.SEL_CAMPO_CAPTCHA, timeout=5_000)
        except Exception:
            pass
        ctx.aguardar_captcha(
            "CNDT: digite na janela do navegador os caracteres da imagem (CAPTCHA) "
            "e clique em 'Emitir Certidão'. O PDF será capturado automaticamente."
        )

        # 4) Capturar o download disparado após o usuário emitir.
        try:
            with page.expect_download(timeout=TIMEOUT_CAPTCHA_MS) as info:
                pass  # o clique é feito pelo usuário; só aguardamos o download
            download = info.value
        except Exception:
            return Resultado(
                self.id,
                Status.ERRO,
                "Tempo esgotado aguardando a emissão (CAPTCHA não resolvido?).",
            )

        caminho = ctx.caminho_pdf(self.id)
        download.save_as(str(caminho))
        ctx.log(f"CNDT: salvo em {caminho.name}")
        return Resultado(self.id, Status.OK, "Certidão salva.", caminho)
