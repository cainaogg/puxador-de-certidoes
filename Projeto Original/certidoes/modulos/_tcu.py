"""Helpers compartilhados da plataforma de certidões do TCU (certidoes.apps.tcu.gov.br).

As páginas (Inidôneos, Contas Julgadas Irregulares) têm UM campo só com um
alternador CPF/CNPJ. O modo NÃO está no placeholder; o sinal real é o prefixo
"CPF:" / "CNPJ:" ao lado do campo. Trocar com o botão "CPF"/"CNPJ". É preciso
CONFIRMAR o modo antes de digitar, senão o número entra no campo errado.
"""

from __future__ import annotations

from ..documento import TipoDoc

_PREFIXO_JS = r"""() => {
  const inp = [...document.querySelectorAll('input[type=text]')].find(e=>e.offsetWidth);
  let n = inp, txt='';
  for (let i=0;i<4 && n;i++){ n=n.parentElement;
    if(n){ const m=(n.innerText||'').match(/CNPJ:|CPF:/); if(m){ txt=m[0]; break; } } }
  return txt;
}"""


def modo_atual(page) -> str:
    """'cnpj' ou 'cpf' conforme o prefixo ao lado do campo."""
    return "cnpj" if (page.evaluate(_PREFIXO_JS) or "").startswith("CNPJ") else "cpf"


def garantir_modo(page, tipo: TipoDoc) -> bool:
    """Garante o campo no modo certo (CPF/CNPJ) ANTES de digitar. True se conseguiu."""
    alvo = "cnpj" if tipo is TipoDoc.CNPJ else "cpf"
    rotulo = "CNPJ" if alvo == "cnpj" else "CPF"
    for _ in range(4):
        if modo_atual(page) == alvo:
            return True
        try:
            page.get_by_role("button", name=rotulo).first.click(timeout=4_000)
        except Exception:  # noqa: BLE001
            pass
        page.wait_for_timeout(900)
    return modo_atual(page) == alvo
