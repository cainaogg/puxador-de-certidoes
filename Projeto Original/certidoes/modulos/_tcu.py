"""Helpers compartilhados da plataforma de certidões do TCU (certidoes.apps.tcu.gov.br).

As páginas (Inidôneos, Contas Julgadas Irregulares) têm UM campo só com um
alternador CPF/CNPJ. O modo NÃO está no placeholder; o sinal real é o prefixo
"CPF:" / "CNPJ:" ao lado do campo. Trocar com o botão "CPF"/"CNPJ". É preciso
CONFIRMAR o modo antes de digitar, senão o número entra no campo errado.
"""

from __future__ import annotations

from ..base import Resultado, Status, salvar_pagina_como_pdf
from ..documento import TipoDoc

# Mensagens transitórias do TCU (rede lenta/proxy do trabalho): vale tentar de novo.
_ERROS_TRANSITORIOS = (
    "captcha expirou", "erro no serviço", "erro no servico",
    "não localizado", "nao localizado", "tente novamente",
    "excede", "limite de",
)


def mensagem_erro(page) -> str:
    """Trecho da mensagem de erro transitória na página (ou '')."""
    try:
        corpo = page.inner_text("body")
    except Exception:  # noqa: BLE001
        return ""
    low = corpo.lower()
    for frag in _ERROS_TRANSITORIOS:
        i = low.find(frag)
        if i >= 0:
            return corpo[i:i + 60].strip().replace("\n", " ")
    return ""


def _transitorio(msg: str) -> bool:
    """Erro que provavelmente passa numa nova tentativa (recalcula o ALTCHA)."""
    low = (msg or "").lower()
    extras = ("demorou", "não apareceu", "nao apareceu", "expirou")
    return any(f in low for f in _ERROS_TRANSITORIOS) or any(f in low for f in extras)


def com_retry(page, ctx, url: str, nome: str, tentativa, tentativas: int = 3):
    """Chama `tentativa(page)` (devolve Resultado); em erro transitório do TCU,
    recarrega o site e tenta de novo, até `tentativas` vezes."""
    resultado = None
    for t in range(1, tentativas + 1):
        if t > 1:
            ctx.log(f"{nome}: tentando de novo ({t}/{tentativas}) — recarregando…")
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=60_000)
                page.wait_for_timeout(3_000)
            except Exception:  # noqa: BLE001
                pass
        resultado = tentativa(page)
        if resultado.status is Status.OK or not _transitorio(resultado.mensagem):
            return resultado
    return resultado


def baixar_para(page, ctx, modulo_id: str, baixar_locator, nome: str) -> Resultado:
    """Clica no botão de baixar e salva o PDF (download, ou imprime a aba se abrir)."""
    caminho = ctx.caminho_pdf(modulo_id)
    try:
        with page.expect_download(timeout=30_000) as info:
            baixar_locator.first.click(timeout=15_000)
        info.value.save_as(str(caminho))
    except Exception:  # noqa: BLE001
        paginas = page.context.pages
        destino = paginas[-1] if len(paginas) > 1 else page
        salvar_pagina_como_pdf(destino, caminho)
    ctx.log(f"{nome}: salvo em {caminho.name}")
    return Resultado(modulo_id, Status.OK, "Documento salvo.", caminho)

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
