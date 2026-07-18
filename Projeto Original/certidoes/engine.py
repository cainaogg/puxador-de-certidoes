"""Motor de automação: roda os módulos selecionados com um navegador Playwright.

Projetado para ser executado em uma thread separada da interface. Toda
comunicação com a tela acontece via callbacks (que a GUI agenda no thread
principal com `after`).
"""

from __future__ import annotations

import tempfile
import threading
from datetime import date
from pathlib import Path
from typing import Callable, List, Union

from playwright.sync_api import sync_playwright

from . import cnpj_publico, paths
from .base import (
    Contexto,
    ModuloCertidao,
    Resultado,
    Status,
    _texto_pdf,
    certidao_valida_existente,
    extrair_nome_titular,
    renomear_com_validade,
    rotulo_documento,
    salvar_screenshot_erro,
)
from .documento import Documento, TipoDoc

# on_status recebe (modulo_id, Status simples) ou (modulo_id, Resultado completo).
StatusCb = Callable[[str, Union[Status, Resultado]], None]
LogCb = Callable[[str], None]

# Ordem de preferência de navegador. O Chromium embutido do Playwright pode falhar
# em alguns Windows (erro "side-by-side"), então tentamos primeiro o navegador já
# instalado no sistema (Edge vem por padrão no Windows 11; Chrome se houver).
CANAIS_NAVEGADOR = [
    ("msedge", "Microsoft Edge (do sistema)"),
    ("chrome", "Google Chrome (do sistema)"),
    (None, "Chromium embutido (Playwright)"),
]

# Argumento que oculta a flag de automação (alguns órgãos, como a CGU, bloqueiam
# navegadores automatizados via WAF/CloudFront com erro 403).
ARGS_NAVEGADOR = ["--disable-blink-features=AutomationControlled"]

# Script injetado em toda página para remover marcas de automação (anti-bot).
STEALTH_JS = """
Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
Object.defineProperty(navigator, 'languages', {get: () => ['pt-BR', 'pt', 'en']});
Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
window.chrome = window.chrome || {runtime: {}};
"""

# Extensão NopeCHA (resolve reCAPTCHA/hCaptcha automaticamente). Se a pasta existir,
# é carregada; senão o programa funciona normalmente (captchas em modo assistido).
PASTA_EXTENSAO = paths.base_recursos() / "vendor" / "nopecha_ext"


_CACHE_NOME: dict = {}


def _nome_entidade(documento: Documento) -> str:
    """Razão social do CNPJ (API pública gratuita, com cache). CPF -> '' (sem fonte gratuita)."""
    if documento.tipo is not TipoDoc.CNPJ:
        return ""
    chave = documento.numero
    if chave not in _CACHE_NOME:
        try:
            nome, _ = cnpj_publico.nome_e_endereco(chave)
            _CACHE_NOME[chave] = (nome or "").strip()
        except Exception:  # noqa: BLE001
            _CACHE_NOME[chave] = ""
    return _CACHE_NOME[chave]


def pasta_do_documento(base: Path, documento: Documento, nome: str = "") -> Path:
    return base / rotulo_documento(documento, nome) / date.today().isoformat()


def _pasta_do_grupo(base: Path, dono: Documento) -> Path:
    """Pasta '<base>/<pasta do dono>/<hoje>', reusando a pasta-mãe existente do dono
    (que pode já estar renomeada para 'NOME - número'). Assim as certidões de um CPF
    de sócio caem na MESMA pasta do CNPJ."""
    numero_fmt = dono.formatado.replace("/", ".")
    if base.exists():
        for d in sorted(base.iterdir()):
            if d.is_dir() and numero_fmt in d.name:
                return d / date.today().isoformat()
    return base / rotulo_documento(dono, "") / date.today().isoformat()


def nomear_pasta_mae(pasta: Path, documento: Documento, on_log: LogCb) -> Path:
    """Renomeia a pasta-mãe (base/<rótulo>) de `pasta` para '<NOME> - <número>'.

    Nome: CNPJ pela API pública gratuita; CPF pelo nome impresso numa certidão da
    pasta. Só age se a pasta-mãe pertencer a este documento (contém o número), para
    não renomear pasta errada. Devolve `pasta` (nova ou a mesma).
    """
    numero_fmt = documento.formatado.replace("/", ".")
    docfolder = pasta.parent  # base/<rótulo>
    if numero_fmt not in docfolder.name:
        return pasta  # segurança: só a pasta do próprio documento

    nome = _nome_entidade(documento)  # CNPJ -> API gratuita; CPF -> ""
    if not nome and documento.tipo is TipoDoc.CPF:
        for pdf in sorted(pasta.glob("*.pdf")):
            try:
                nome = extrair_nome_titular(_texto_pdf(pdf), documento)
            except Exception:  # noqa: BLE001
                nome = ""
            if nome:
                break
    if not nome:
        return pasta

    novo_doc = docfolder.parent / rotulo_documento(documento, nome)
    if novo_doc == docfolder or novo_doc.exists():
        return pasta
    try:
        docfolder.rename(novo_doc)
        on_log(f"Pasta renomeada: {novo_doc.name}")
        return novo_doc / pasta.name
    except Exception as exc:  # noqa: BLE001
        on_log(f"Não consegui renomear a pasta ({exc}).")
        return pasta


def _abrir_contexto(pw, on_log: LogCb):
    """Abre um navegador visível (contexto persistente) carregando a extensão NopeCHA.

    Tenta Edge → Chrome → Chromium embutido. Se a extensão não estiver presente,
    abre sem ela (captchas ficam em modo assistido).
    """
    usar_ext = PASTA_EXTENSAO.exists()
    args = list(ARGS_NAVEGADOR)
    if usar_ext:
        args += [
            f"--disable-extensions-except={PASTA_EXTENSAO}",
            f"--load-extension={PASTA_EXTENSAO}",
        ]
    ultimo_erro = None
    for canal, descricao in CANAIS_NAVEGADOR:
        try:
            perfil = tempfile.mkdtemp(prefix="certidoes_")
            kwargs = {
                "user_data_dir": perfil,
                "headless": False,
                "args": args,
                "accept_downloads": True,
                "locale": "pt-BR",
            }
            if canal:
                kwargs["channel"] = canal
            contexto = pw.chromium.launch_persistent_context(**kwargs)
            extra = " + NopeCHA (resolve captchas)" if usar_ext else ""
            on_log(f"Navegador: {descricao}{extra}.")
            contexto.add_init_script(STEALTH_JS)
            return contexto
        except Exception as exc:  # noqa: BLE001
            ultimo_erro = exc
            on_log(f"Navegador {descricao} indisponível ({type(exc).__name__}); tentando outro…")
    raise RuntimeError(
        f"Nenhum navegador pôde ser aberto. Último erro: {ultimo_erro}"
    )


def executar_lote(
    documento: Documento,
    modulos: List[ModuloCertidao],
    pasta_base: Path,
    on_log: LogCb,
    on_status: StatusCb,
    cancel_event: threading.Event,
    data_nascimento: str = "",
    nome_informado: str = "",
    documento_pasta: Documento = None,
    contexto_compartilhado=None,
) -> List[Resultado]:
    """Executa cada módulo em sequência. Abre o navegador só se algum módulo precisar
    (módulos de API não usam navegador).

    `documento_pasta`: dono da pasta (ex.: o CNPJ, quando `documento` é o CPF de um
    sócio majoritário). Se None, a pasta é a do próprio `documento`.

    `contexto_compartilhado`: se informado, reusa esse contexto Playwright já aberto
    em vez de abrir/fechar um novo (quem chamou é responsável por fechá-lo depois).
    Usado para processar uma fila de várias consultas manuais (ex.: CEIS) sem
    reabrir o navegador a cada uma.
    """
    # A pasta é a do "dono" do grupo (o CNPJ, no caso de CPF de sócio) — reusa a
    # pasta-mãe existente (mesmo já renomeada). O nome bonito é aplicado no FIM.
    dono = documento_pasta or documento
    pasta = _pasta_do_grupo(pasta_base, dono)
    pasta.mkdir(parents=True, exist_ok=True)
    resultados: List[Resultado] = []
    on_log(f"Pasta de saída: {pasta}")

    # Certidões que já estão válidas (serão puladas) — calcula uma vez, no disco
    # (busca na pasta do grupo/dono).
    existentes = {
        m.id: certidao_valida_existente(pasta_base, documento, m, documento_pasta=dono)
        for m in modulos
    }

    # Precisa de navegador? Só se houver módulo de navegador que NÃO será pulado.
    precisa_navegador = any(
        not getattr(m, "manual", False) and not getattr(m, "usa_api", False)
        and not existentes.get(m.id)
        for m in modulos
    )

    def rodar(context) -> None:
        for modulo in modulos:
            if cancel_event.is_set():
                res = Resultado(modulo.id, Status.CANCELADO, "Cancelado pelo usuário.")
                on_status(modulo.id, res)
                resultados.append(res)
                continue

            # Já existe uma certidão desta ainda válida? Pula (economiza tempo/captcha).
            existente = existentes.get(modulo.id)
            if existente:
                pdf_ok, dval = existente
                res = Resultado(modulo.id, Status.JA_VALIDA,
                                f"Já válida até {dval.strftime('%d/%m/%Y')}.", pdf_ok)
                on_log(f"{modulo.nome}: já válida até {dval.strftime('%d/%m/%Y')} "
                       f"(em {pdf_ok.parent.name}) — pulei.")
                on_status(modulo.id, res)
                resultados.append(res)
                continue

            # Órgãos que bloqueiam automação (hCaptcha Enterprise): não tenta.
            if getattr(modulo, "manual", False):
                res = Resultado(
                    modulo.id, Status.MANUAL,
                    "Este órgão bloqueia automação — emita manualmente no seu navegador.",
                )
                on_log(f"{modulo.nome}: emitir manualmente (o órgão bloqueia automação).")
                on_status(modulo.id, res)
                resultados.append(res)
                continue

            on_status(modulo.id, Status.EXECUTANDO)
            eh_api = getattr(modulo, "usa_api", False)
            page = None if eh_api else context.new_page()
            if page is not None:
                try:
                    # Sem foco, o Chromium trata a aba como "em segundo plano" e
                    # desacelera seus timers/navegação — só andava de verdade se o
                    # usuário clicasse na janela. Traz para frente logo ao criar.
                    page.bring_to_front()
                except Exception:  # noqa: BLE001
                    pass

            def aguardar_captcha(msg: str, _mid=modulo.id) -> None:
                on_status(_mid, Status.AGUARDANDO_CAPTCHA)
                on_log(msg)

            ctx = Contexto(
                documento=documento,
                pasta_saida=pasta,
                log=on_log,
                aguardar_captcha=aguardar_captcha,
                data_nascimento=data_nascimento,
                nome_informado=nome_informado,
            )
            try:
                res = modulo.executar(page, ctx)
            except Exception as exc:  # noqa: BLE001 - registra qualquer falha
                res = Resultado(modulo.id, Status.ERRO, f"{type(exc).__name__}: {exc}")

            # Print da tela só para módulos de navegador (API não tem tela).
            if res.status is Status.ERRO and not eh_api and page is not None:
                try:
                    page.bring_to_front()
                    page.wait_for_timeout(600)
                except Exception:
                    pass
                try:
                    img = salvar_screenshot_erro(modulo.nome, pasta)
                    on_log(f"{modulo.nome}: print do erro salvo em '{img.name}'")
                except Exception as exc:  # noqa: BLE001
                    on_log(f"{modulo.nome}: não consegui salvar o print ({exc}).")

            # Renomeia o PDF baixado para "<documento> val. <validade>.pdf".
            if res.status is Status.OK and res.arquivo:
                try:
                    novo = renomear_com_validade(Path(res.arquivo), modulo, documento)
                    if novo != res.arquivo:
                        res.arquivo = novo
                        on_log(f"{modulo.nome}: salvo como '{novo.name}'")
                except Exception as exc:  # noqa: BLE001
                    on_log(f"{modulo.nome}: não consegui renomear o arquivo ({exc}).")

            on_status(modulo.id, res)
            resultados.append(res)
            if page is not None:
                try:
                    page.close()
                except Exception:
                    pass

    if contexto_compartilhado is not None:
        rodar(contexto_compartilhado)  # quem chamou abre/fecha o navegador
    elif precisa_navegador:
        with sync_playwright() as pw:
            context = _abrir_contexto(pw, on_log)
            try:
                rodar(context)
            finally:
                try:
                    context.close()
                except Exception:
                    pass
    else:
        on_log("Sem navegador: todas as consultas são por API.")
        rodar(None)

    # No fim, nomeia a pasta-mãe do dono (razão social do CNPJ / titular do CPF).
    on_log("Nomeando a pasta pela razão social/titular…")
    pasta = nomear_pasta_mae(pasta, dono, on_log)

    return resultados
