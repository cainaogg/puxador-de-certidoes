"""Certidão de Falência (TJRS, Cível 1º Grau) — abre no navegador para emissão manual.

No Projeto Original, a TJRS abre o sistema no SEU navegador padrão (como a Receita
no modo "navegador"); você seleciona o tipo, marca Pessoa Jurídica e preenche
Nome/CNPJ/Endereço manualmente. URL direta do formulário: /proc/alvara/.
"""

from __future__ import annotations

import webbrowser

from ..base import Contexto, ModuloCertidao, Resultado, Status
from ..documento import TipoDoc


class TJRSFalencia(ModuloCertidao):
    id = "tjrs_falencia"
    nome = "Certidão Judicial Cível Negativa - Falência 1º Grau (TJRS)"
    descricao = "TJRS — abre no seu navegador para você preencher e emitir."
    url = "https://www.tjrs.jus.br/proc/alvara/"
    requer_captcha = False
    implementado = True
    usa_api = True  # não usa o navegador Playwright (abre o navegador do sistema)
    aceita = frozenset({TipoDoc.CNPJ})

    def executar(self, page, ctx: Contexto) -> Resultado:
        ctx.log("TJRS: abrindo o sistema no seu navegador para emissão manual…")
        try:
            webbrowser.open(self.url)
        except Exception as exc:  # noqa: BLE001
            return Resultado(self.id, Status.ERRO, f"Não consegui abrir o navegador: {exc}")
        return Resultado(
            self.id, Status.MANUAL,
            "Abri o sistema do TJRS no seu navegador — selecione 'Certidão Judicial "
            "Cível Negativa de 1º Grau - Falência', marque Pessoa Jurídica, preencha "
            "Nome/CNPJ/Endereço e clique em 'Emitir Documento'.",
        )
