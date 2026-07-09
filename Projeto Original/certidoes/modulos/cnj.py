"""Certidão de Improbidade Administrativa (CNJ) — abre no navegador para emissão manual.

No Projeto Original (sem API), a CNJ abre o sistema no SEU navegador padrão. O nome
(razão social / pessoa física) é obrigatório no formulário e não temos como obtê-lo
só com o CPF/CNPJ sem a API — então você preenche manualmente. URL: consultar_requerido.php.
"""

from __future__ import annotations

import webbrowser

from ..base import Contexto, ModuloCertidao, Resultado, Status
from ..documento import TipoDoc


class CNJImprobidade(ModuloCertidao):
    id = "cnj_improbidade"
    nome = "Certidão Negativa de Improb. Admin e Ineleg. CNPJ (CNJ)"
    descricao = "CNJ — abre no seu navegador para você preencher e emitir."
    url = "https://www.cnj.jus.br/improbidade_adm/consultar_requerido.php"
    requer_captcha = False
    implementado = True
    usa_api = True  # não usa o navegador Playwright (abre o navegador do sistema)
    aceita = frozenset({TipoDoc.CPF, TipoDoc.CNPJ})

    def executar(self, page, ctx: Contexto) -> Resultado:
        eh_cnpj = ctx.documento.tipo is TipoDoc.CNPJ
        tipo = "Jurídica" if eh_cnpj else "Física"
        ctx.log("CNJ: abrindo o site no seu navegador para emissão manual…")
        try:
            webbrowser.open(self.url)
        except Exception as exc:  # noqa: BLE001
            return Resultado(self.id, Status.ERRO, f"Não consegui abrir o navegador: {exc}")
        return Resultado(
            self.id, Status.MANUAL,
            f"Abri o CNJ no seu navegador — marque '{tipo}', preencha o "
            f"{'CNPJ' if eh_cnpj else 'CPF'} e o Nome, resolva o captcha, clique em "
            "'Pesquisar' e depois em 'Gerar Certidão Negativa'.",
        )
