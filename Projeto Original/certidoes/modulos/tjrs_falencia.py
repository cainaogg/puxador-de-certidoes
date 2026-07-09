"""Certidão Judicial Cível Negativa de 1º Grau - Falência (TJRS).

Automatizado via Playwright. O site NÃO tem captcha. O programa:
  1. consulta o CNPJ na BrasilAPI (razão social + endereço, grátis);
  2. abre o formulário, escolhe "...Falência", marca Pessoa Jurídica e preenche
     Nome/CNPJ/Endereço;
  3. clica "Emitir Documento" — a certidão sai como download (PDF).

O TJRS valida Nome e Endereço: aceita SÓ letras e números (sem acento nem
símbolos). Por isso os dois são limpos para ASCII alfanumérico. Se a consulta
pública falhar (ex.: sem internet), cai no modo manual (abre o site no
navegador). Mapeado em 2026-07-09.
"""

from __future__ import annotations

import webbrowser

from .. import cnpj_publico
from ..base import (
    Contexto,
    ModuloCertidao,
    Resultado,
    Status,
    emitir_e_capturar,
    so_letras_numeros,
)
from ..documento import TipoDoc

_OPCAO_FALENCIA = "Certidão Judicial Cível Negativa de 1º Grau - Falência"


class TJRSFalencia(ModuloCertidao):
    id = "tjrs_falencia"
    nome = "Certidão Judicial Cível Negativa - Falência 1º Grau (TJRS)"
    descricao = "TJRS — preenche e emite sozinho (usa razão social e endereço do CNPJ)."
    url = "https://www.tjrs.jus.br/proc/alvara/"
    requer_captcha = False
    implementado = True
    aceita = frozenset({TipoDoc.CNPJ})

    def executar(self, page, ctx: Contexto) -> Resultado:
        # 1) Dados do CNPJ (razão social + endereço) pela API pública gratuita.
        ctx.log("TJRS: consultando razão social e endereço do CNPJ…")
        dados = cnpj_publico.consultar(ctx.documento.numero)
        if not dados:
            return self._fallback_manual(
                ctx, "não consegui consultar a razão social/endereço do CNPJ")

        nome = so_letras_numeros(dados.get("razao_social") or dados.get("nome") or "")
        endereco = so_letras_numeros(cnpj_publico.endereco_para_form(dados))
        if not nome or not endereco:
            return self._fallback_manual(ctx, "dados do CNPJ vieram incompletos")

        # 2) Abre o formulário e preenche.
        ctx.log("TJRS: abrindo o formulário…")
        page.goto(self.url, wait_until="domcontentloaded", timeout=60_000)
        page.wait_for_timeout(2_500)
        page.select_option("select#tipoDocumento", label=_OPCAO_FALENCIA)
        page.wait_for_timeout(1_000)
        page.check("input[name=tipoPessoa][value=J]", force=True)  # Pessoa Jurídica
        page.wait_for_timeout(1_000)
        page.fill("input[name=nome]", nome)
        page.fill("input[name=cnpj]", ctx.documento.numero)  # dígitos (campo maxlength=14)
        page.fill("input[name=endereco]", endereco)
        ctx.log(f"TJRS: emitindo para {nome}…")

        # 3) Captura eventuais alerts de validação e emite (a certidão vem como
        #    download por um popup — o helper cobre isso).
        alertas: list = []
        page.on("dialog", lambda d: (alertas.append(d.message), d.accept()))

        def _emitir() -> None:
            page.get_by_text("Emitir Documento", exact=True).first.click(timeout=10_000)

        res = emitir_e_capturar(page, ctx, self.id, "TJRS", _emitir, timeout=40)
        if res.status is not Status.OK and alertas:
            return Resultado(self.id, Status.ERRO, f"TJRS recusou: {alertas[-1]}")
        return res

    def _fallback_manual(self, ctx: Contexto, motivo: str) -> Resultado:
        """Sem dados do CNPJ: abre o site no navegador para emissão manual."""
        ctx.log(f"TJRS: {motivo} — abrindo o site para você emitir manualmente.")
        try:
            webbrowser.open(self.url)
        except Exception:  # noqa: BLE001
            pass
        return Resultado(
            self.id, Status.MANUAL,
            "Não obtive os dados do CNPJ para preencher sozinho. Abri o site do TJRS: "
            "escolha 'Certidão…Falência', marque Pessoa Jurídica e preencha "
            "Nome/CNPJ/Endereço (só letras e números).",
        )
