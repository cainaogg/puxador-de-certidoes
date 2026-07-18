"""Contratos compartilhados pelos módulos de certidão."""

from __future__ import annotations

import base64
import re
from dataclasses import dataclass, field
from datetime import date, timedelta
from enum import Enum
from pathlib import Path
from typing import Callable, Optional, Set

from .documento import Documento, DocumentoInvalido, TipoDoc, detectar


class Status(str, Enum):
    PENDENTE = "pendente"
    EXECUTANDO = "executando"
    AGUARDANDO_CAPTCHA = "aguardando_captcha"
    OK = "ok"
    ERRO = "erro"
    NAO_APLICAVEL = "nao_aplicavel"
    CANCELADO = "cancelado"
    MANUAL = "manual"  # órgão bloqueia automação; usuário emite à mão
    JA_VALIDA = "ja_valida"  # já existe uma certidão desta ainda válida; pulou


# Rótulos amigáveis exibidos na interface.
STATUS_LABEL = {
    Status.PENDENTE: "Pendente",
    Status.EXECUTANDO: "Executando…",
    Status.AGUARDANDO_CAPTCHA: "Resolva o CAPTCHA na janela…",
    Status.OK: "✓ Baixado",
    Status.ERRO: "✗ Erro",
    Status.NAO_APLICAVEL: "—",
    Status.CANCELADO: "Cancelado",
    Status.MANUAL: "⚠ Emitir manualmente",
    Status.JA_VALIDA: "♻ Já válida",
}


@dataclass
class Resultado:
    modulo_id: str
    status: Status
    mensagem: str = ""
    arquivo: Optional[Path] = None


@dataclass
class Contexto:
    """Tudo que um módulo precisa para emitir uma certidão."""

    documento: Documento
    pasta_saida: Path
    log: Callable[[str], None] = lambda msg: None
    # Sinaliza para a interface que o passo agora depende do usuário (CAPTCHA).
    aguardar_captcha: Callable[[str], None] = lambda msg: None
    # Data de nascimento (dd/mm/aaaa), só usada em consultas de CPF que a exigem
    # (ex.: CND Federal da Receita). Vazia para CNPJ.
    data_nascimento: str = ""
    # Nome informado pelo usuário na mesma linha (ex.: nome do CPF para o CNJ, que
    # não tem fonte gratuita). Vazio quando não informado.
    nome_informado: str = ""

    def caminho_pdf(self, modulo_id: str) -> Path:
        hoje = date.today().isoformat()
        self.pasta_saida.mkdir(parents=True, exist_ok=True)
        return self.pasta_saida / f"{hoje}_{modulo_id}.pdf"


def salvar_pagina_como_pdf(page, caminho: Path, *, esperar_imagens: bool = True) -> None:
    """Salva a página atual como PDF via CDP (equivale a "Imprimir > Salvar como PDF").

    page.pdf() do Playwright só funciona em modo headless; usamos o protocolo
    DevTools diretamente para imprimir em PDF com o navegador aberto. Usa A4 (padrão
    brasileiro) e espera as imagens carregarem para não perder logomarcas.
    """
    if esperar_imagens:
        try:
            page.wait_for_load_state("networkidle", timeout=15_000)
            page.wait_for_function(
                "() => Array.from(document.images).every(i => i.complete && i.naturalWidth > 0)",
                timeout=10_000,
            )
        except Exception:
            pass  # segue mesmo assim; melhor um PDF do que falhar
    client = page.context.new_cdp_session(page)
    resultado = client.send(
        "Page.printToPDF",
        {
            "printBackground": True,
            "paperWidth": 8.27,    # A4 (210 mm)
            "paperHeight": 11.69,  # A4 (297 mm)
        },
    )
    caminho.write_bytes(base64.b64decode(resultado["data"]))


def _nome_arquivo_seguro(nome: str) -> str:
    """Remove caracteres inválidos em nomes de arquivo no Windows."""
    return re.sub(r'[\\/:*?"<>|]', "-", nome).strip()


_RECAPTCHA_TOKEN_JS = (
    "() => { let m = 0; document.querySelectorAll"
    "(\"textarea[name='g-recaptcha-response']\").forEach"
    "(e => { m = Math.max(m, (e.value || '').length); }); return m; }"
)


def esperar_recaptcha(page, ctx, nome: str = "", head_start: int = 25,
                      total: int = 300) -> bool:
    """Espera o reCAPTCHA ser resolvido — pela NopeCHA OU pelo usuário na janela.

    Dá um tempo para a NopeCHA resolver sozinha (`head_start`); se demorar, avisa a
    interface (modo assistido) para o usuário clicar o captcha na janela aberta e
    segue esperando o token até `total` segundos. Retorna True assim que o token
    aparece; False se estourar o tempo. Assim, quando o solver falha, o usuário só
    clica o captcha — não precisa refazer tudo.
    """
    import time

    inicio = time.time()
    avisou = False
    while time.time() - inicio < total:
        try:
            if (page.evaluate(_RECAPTCHA_TOKEN_JS) or 0) > 20:
                return True
        except Exception:  # noqa: BLE001
            pass
        if not avisou and time.time() - inicio >= head_start:
            avisou = True
            ctx.aguardar_captcha(
                f"{nome}: se o captcha não resolver sozinho, clique nele na janela do "
                "navegador — o programa continua sozinho depois."
            )
        page.wait_for_timeout(2_500)
    return False


def emitir_e_capturar(page, ctx, modulo_id: str, nome: str, clicar, timeout: int = 45):
    """Aciona a emissão (`clicar`) e captura o documento de forma robusta.

    Cobre os dois jeitos que o SIAT/POA entrega a certidão:
      - abre em NOVA ABA (imprime a aba em PDF) — comportamento comum; e
      - vem como DOWNLOAD, inclusive quando o navegador corporativo força baixar o
        PDF por uma aba que abre e fecha na hora (Edge gerenciado da Procempa).

    Por isso o listener de download é registrado em TODAS as páginas (a atual e as
    novas abas), e a espera não quebra se a página original fechar. Os listeners
    precisam existir ANTES do clique, então `clicar` é chamado aqui dentro.
    """
    import time

    baixados: dict = {}
    novas: list = []

    def _on_download(d) -> None:
        baixados.setdefault("d", d)

    def _on_page(pg) -> None:
        novas.append(pg)
        try:
            pg.on("download", _on_download)  # a aba nova pode virar download
        except Exception:  # noqa: BLE001
            pass

    page.on("download", _on_download)
    page.context.on("page", _on_page)

    def _parar_de_escutar() -> None:
        """Remove os listeners antes de sair. `page.context` é REAPROVEITADO entre
        módulos (mesmo navegador para o lote inteiro/fila) — sem isso, um evento
        tardio do site (ex.: popup/reload atrasado) cai num listener órfão e abre
        uma aba que ninguém mais fecha, obrigando a fechar na mão."""
        try:
            page.remove_listener("download", _on_download)
        except Exception:  # noqa: BLE001
            pass
        try:
            page.context.remove_listener("page", _on_page)
        except Exception:  # noqa: BLE001
            pass

    def _fechar_novas() -> None:
        """Fecha as abas/popups que o site abriu (deixa só a página principal)."""
        for pg in list(novas):
            try:
                if pg is not page and not pg.is_closed():
                    pg.close()
            except Exception:  # noqa: BLE001
                pass

    try:
        clicar()

        caminho = ctx.caminho_pdf(modulo_id)
        fim = time.time() + timeout
        while time.time() < fim:
            # 1) Download capturado (na aba principal OU numa aba nova que baixou).
            if "d" in baixados:
                try:
                    baixados["d"].save_as(str(caminho))
                except Exception as exc:  # noqa: BLE001
                    return Resultado(modulo_id, Status.ERRO,
                                     f"Documento baixou, mas não consegui salvar: {exc}")
                _fechar_novas()
                ctx.log(f"{nome}: PDF baixado em {caminho.name}")
                return Resultado(modulo_id, Status.OK, "Documento baixado.", caminho)

            # 2) Certidão aberta numa aba viva.
            for pg in list(novas):
                try:
                    if pg.is_closed():
                        continue
                    try:
                        pg.wait_for_load_state("networkidle", timeout=8_000)
                    except Exception:  # noqa: BLE001
                        pass
                    if "d" in baixados or pg.is_closed():  # virou download no meio
                        break
                    # Se a aba É um PDF (visualizador do navegador — ex.: TJRS), baixa
                    # os bytes direto, usando a sessão/cookies do navegador. Senão
                    # (certidão em HTML — ex.: POA), imprime a página em PDF.
                    ctype = ""
                    try:
                        ctype = (pg.evaluate("() => document.contentType") or "").lower()
                    except Exception:  # noqa: BLE001
                        ctype = ""
                    if "pdf" in ctype or pg.url.lower().endswith(".pdf"):
                        resp = pg.context.request.get(pg.url)
                        caminho.parent.mkdir(parents=True, exist_ok=True)
                        caminho.write_bytes(resp.body())
                    else:
                        salvar_pagina_como_pdf(pg, caminho)
                except Exception:  # noqa: BLE001 - aba pode fechar/virar download
                    continue
                else:
                    _fechar_novas()
                    ctx.log(f"{nome}: certidão salva em {caminho.name}")
                    return Resultado(modulo_id, Status.OK, "Documento salvo.", caminho)

            # Espera curta, resiliente ao fechamento da página original.
            try:
                page.wait_for_timeout(1_000)
            except Exception:  # noqa: BLE001
                time.sleep(1.0)

        return Resultado(modulo_id, Status.ERRO,
                         "Não obtive o documento após Confirmar. Veja o print.")
    finally:
        _parar_de_escutar()


# Prazo de validade (em dias) usado SÓ como fallback quando a validade não está
# impressa no PDF. Valores pesquisados: TCU e CGU = 30 dias; Receita/CNDT = 180.
# Os que não estão aqui (POA ISS comprovante, SEFAZ, POA Tributos, TJRS) dependem
# do que vier impresso no próprio documento.
VALIDADE_DIAS = {
    "receita_federal": 180,
    "cndt_trabalhista": 180,
    "fgts_crf": 30,
    "cnj_improbidade": 30,
    "cgu_correcional": 30,
    "tcu_consolidada_pj": 30,
    "tcu_inidoneos": 30,
    "tcu_contas_irregulares": 30,
}

_DATA_RE = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{2,4})")


def _norm_data(d, mes, ano):
    """(d, mes, ano) de strings -> (ano4, mes, dia) validado, ou None. Ano 2 díg. => 20xx."""
    d, mes, ano = int(d), int(mes), int(ano)
    if ano < 100:
        ano += 2000
    try:
        date(ano, mes, d)
    except ValueError:
        return None
    return (ano, mes, d)


def _texto_pdf(caminho: Path) -> str:
    """Extrai o texto de um PDF (para achar a data de validade)."""
    from pypdf import PdfReader  # import tardio: só quando precisa

    leitor = PdfReader(str(caminho))
    return "\n".join((pagina.extract_text() or "") for pagina in leitor.pages)


def extrair_validade(texto: str) -> Optional[str]:
    """Acha a data de validade no texto de uma certidão. Retorna 'dd.mm.aaaa' ou None.

    Procura datas perto de 'válid…'/'validade'. Em faixas ('de X a Y') pega a
    última (a data-limite). Entre vários candidatos, usa a data mais distante.
    """
    candidatos = []
    for m in re.finditer(r"v[áa]lid", texto, re.IGNORECASE):
        trecho = texto[max(0, m.start() - 40): m.end() + 80]  # data pode vir antes ou depois
        for d, mes, ano in _DATA_RE.findall(trecho):
            c = _norm_data(d, mes, ano)
            if c:
                candidatos.append(c)
    if not candidatos:
        return None
    ano, mes, d = max(candidatos)  # a validade é sempre a data mais distante
    return f"{d:02d}.{mes:02d}.{ano:04d}"


def _sanitizar_pasta(nome: str) -> str:
    """Nome seguro para pasta no Windows (sem caracteres inválidos nem ponto/espaço final)."""
    nome = _nome_arquivo_seguro(nome)
    return re.sub(r"\s+", " ", nome).strip(" .")


def rotulo_documento(documento, nome: str = "") -> str:
    """Nome da pasta do documento: '<NOME> - <número>' (ou só '<número>').

    O número usa a máscara com '/' trocado por '.' (o Explorer não aceita '/').
    """
    numero = documento.formatado.replace("/", ".")
    nome = (nome or "").strip()
    return _sanitizar_pasta(f"{nome} - {numero}" if nome else numero)


# Palavras em maiúsculas que aparecem nas certidões mas NÃO são nome de titular.
_BOILERPLATE = {
    "NÃO", "NAO", "CONSTA", "CPF", "CNPJ", "CERTIDÃO", "CERTIDAO", "NEGATIVA",
    "POSITIVA", "CONTAS", "JULGADAS", "IRREGULARES", "TCU", "CGU", "CNJ", "RFB",
    "PGFN", "CADASTRO", "CADIRREG", "UNIÃO", "UNIAO", "TRIBUNAL", "FEDERAL",
    "RECEITA", "NADA", "LICITANTES", "INIDÔNEOS", "INIDONEOS", "ADMINISTRAÇÃO",
    "ADMINISTRACAO", "PÚBLICA", "PUBLICA", "DÍVIDA", "DIVIDA", "ATIVA", "DÉBITOS",
    "DEBITOS", "RESPONSÁVEIS", "RESPONSAVEIS", "MINISTÉRIO", "MINISTERIO",
    "FAZENDA", "NACIONAL", "SECRETARIA", "PROCURADORIA", "GERAL", "IMPROBIDADE",
    "ADMINISTRATIVA", "INELEGIBILIDADE", "EFEITOS", "RELATIVOS", "TRIBUTOS",
}


def extrair_nome_titular(texto: str, documento) -> str:
    """Acha o nome do titular (pessoa) numa certidão. Best-effort; '' se não achar.

    O texto extraído de PDF costuma vir com a ordem embaralhada (o nome fica solto,
    longe do número). Então pegamos a maior frase em MAIÚSCULAS, perto do número,
    descartando o texto padrão das certidões (NÃO CONSTA, CADASTRO, etc.).
    """
    pos = texto.find(documento.formatado)
    janela = texto[max(0, pos - 110): pos + 50] if pos != -1 else texto
    frase_re = re.compile(r"[A-ZÀ-ÖØ-Þ][A-ZÀ-ÖØ-Þ']+(?:\s+[A-ZÀ-ÖØ-Þ'][A-ZÀ-ÖØ-Þ']+)+")
    melhor = ""
    for m in frase_re.finditer(janela):
        frase = re.sub(r"\s+", " ", m.group(0)).strip()
        if any(p in _BOILERPLATE for p in frase.split()):
            continue
        if len(frase) > len(melhor):
            melhor = frase
    return melhor if len(melhor) >= 5 else ""


def nome_documento(nome: str) -> str:
    """Nome do documento sem o código do órgão no último parêntese.

    Ex.: 'CND Trabalhista (CNDT)' -> 'CND Trabalhista';
         'CND Estadual (RS) (SEFAZ-RS)' -> 'CND Estadual (RS)'.
    """
    return re.sub(r"\s*\([^()]*\)\s*$", "", nome).strip()


def so_letras_numeros(texto: str) -> str:
    """Deixa só letras e números (sem acento nem símbolos), com espaços simples.

    Usado em formulários que rejeitam caracteres especiais (TJRS, CNJ).
    """
    import unicodedata
    t = unicodedata.normalize("NFKD", texto or "").encode("ascii", "ignore").decode("ascii")
    t = re.sub(r"[^0-9A-Za-z ]+", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def nome_para_tipo(nome: str, tipo: Optional[TipoDoc]) -> str:
    """Ajusta o token CNPJ/CPF do nome conforme o documento consultado.

    Os nomes-base são escritos para CNPJ; quando a consulta é de um CPF, troca
    'CNPJ' por 'CPF' (ex.: 'Consulta CEIS CNPJ (CGU)' -> 'Consulta CEIS CPF (CGU)').
    """
    if tipo is TipoDoc.CPF:
        return re.sub(r"\bCNPJ\b", "CPF", nome)
    return nome


def nome_arquivo_certidao(nome_modulo: str, validade: Optional[str],
                          tipo: Optional[TipoDoc] = None) -> str:
    """Monta o nome final: '<documento> val. <dd.mm.aaaa>.pdf' (ou só '<documento>.pdf').

    Se `tipo` for CPF, o token 'CNPJ' do nome vira 'CPF'.
    """
    base = _nome_arquivo_seguro(nome_documento(nome_para_tipo(nome_modulo, tipo)))
    return f"{base} val. {validade}.pdf" if validade else f"{base}.pdf"


def renomear_com_validade(caminho: Path, modulo, documento=None) -> Path:
    """Renomeia o PDF baixado para '<documento> val. <validade>.pdf'.

    Validade: 1) extraída do próprio PDF; 2) senão, emissão (hoje) + prazo padrão
    de `VALIDADE_DIAS`. Se não houver nenhuma, fica só '<documento>.pdf'. O token
    CNPJ/CPF do nome segue o tipo de `documento`. Não sobrescreve um arquivo já
    existente com o mesmo nome.
    """
    try:
        texto = _texto_pdf(caminho)
    except Exception:  # noqa: BLE001 - PDF ilegível não deve quebrar o lote
        texto = ""
    validade = extrair_validade(texto)
    if not validade:
        dias = VALIDADE_DIAS.get(getattr(modulo, "id", ""))
        if dias:
            validade = (date.today() + timedelta(days=dias)).strftime("%d.%m.%Y")

    tipo = getattr(documento, "tipo", None)
    nome = nome_arquivo_certidao(modulo.nome, validade, tipo)
    # Marca quando é POSITIVA (tem débito/pendência) — ex.: "Certidão Positiva com
    # Efeitos de Negativa". Assim dá pra ver de cara quem tem pendência.
    if re.search(r"CERTID[ÃA]O\s+POSITIVA", texto, re.IGNORECASE):
        nome = (nome.replace(" val. ", " (positiva) val. ") if " val. " in nome
                else nome[:-4] + " (positiva).pdf")
    destino = caminho.with_name(nome)
    if destino == caminho:
        return caminho
    if destino.exists():
        destino.unlink()
    caminho.rename(destino)
    return destino


_VAL_RE = re.compile(r"val\. (\d{2})\.(\d{2})\.(\d{4})")


def _data_de_nome(nome: str):
    """Extrai a data de 'val. dd.mm.aaaa' do nome do arquivo. None se não houver."""
    m = _VAL_RE.search(nome)
    if not m:
        return None
    d, mes, ano = m.groups()
    try:
        return date(int(ano), int(mes), int(d))
    except ValueError:
        return None


def _data_do_arquivo(p: Path):
    """Validade do arquivo: do nome ('val. …') ou, se faltar, lida do próprio PDF."""
    d = _data_de_nome(p.name)
    if d is None:
        try:
            v = extrair_validade(_texto_pdf(p))
        except Exception:  # noqa: BLE001
            v = None
        d = _data_de_nome(f"val. {v}") if v else None
    return d


# Ordem no PDF unido, por um trecho do NOME do arquivo (confiável, sem ler o PDF).
_ORDEM_NOME = [
    "CND Municipal", "CND Estadual", "CND Federal", "CND Trabalhista",
    "Certificado FGTS", "Falência", "Improb", "Licitantes Inidôneos",
    "Contas Julgadas Irregulares", "Consulta CEIS", "Consulta Consolidada",
    "Comprovante ISS",
]


def _ordem_por_nome(p: Path) -> int:
    for i, frag in enumerate(_ORDEM_NOME):
        if frag in p.name:
            return i
    return len(_ORDEM_NOME)


def juntar_pdfs(pdfs, destino_pasta: Path) -> Optional[Path]:
    """Junta os PDFs (na ordem de `_ORDEM_NOME`) num único 'Certidões val. <a que
    vence antes>.pdf' em `destino_pasta`. Ignora um PDF já unido. None se < 2 PDFs."""
    from pypdf import PdfWriter  # import tardio

    pdfs = [Path(p) for p in pdfs if not Path(p).name.upper().startswith("CERTIDÕES")]
    if len(pdfs) < 2:
        return None
    pdfs.sort(key=_ordem_por_nome)
    datas = [d for d in (_data_do_arquivo(p) for p in pdfs) if d]
    sufixo = f" val. {min(datas).strftime('%d.%m.%Y')}" if datas else ""  # a que vence antes
    destino = destino_pasta / f"CERTIDÕES{sufixo}.pdf"
    escritor = PdfWriter()
    for p in pdfs:
        try:
            escritor.append(str(p))
        except Exception:  # noqa: BLE001 - um PDF quebrado não derruba o resto
            pass
    if len(escritor.pages) == 0:
        return None
    with open(destino, "wb") as f:
        escritor.write(f)
    return destino


def consolidar_pdfs(pasta: Path) -> Optional[Path]:
    """Junta todos os PDFs de certidão de uma pasta (usado após baixar um lote)."""
    return juntar_pdfs(sorted(pasta.glob("*.pdf")), pasta)


def certidao_valida_existente(pasta_base: Path, documento, modulo, margem_dias: int = 0,
                              documento_pasta=None):
    """Acha um PDF DESTA certidão, DESTE documento, ainda não vencido.

    Olha todas as pastas de `pasta_base` cujo nome contém o número do documento
    (inclui pastas já renomeadas para 'NOME - número') e suas subpastas datadas.
    Considera válida a que vence daqui a mais de `margem_dias` dias. Devolve
    (caminho, data) da que vence mais longe, ou None. Documentos sem data de
    validade no nome (ex.: comprovante ISS, cartão CNPJ) nunca contam como válidos.

    `documento_pasta`: quando as certidões deste documento ficam na pasta de OUTRO
    (ex.: CPF de sócio na pasta do CNPJ), passe o dono aqui para buscar na pasta certa.
    """
    if not pasta_base.exists():
        return None
    numero = (documento_pasta or documento).formatado.replace("/", ".")
    base_nome = nome_documento(nome_para_tipo(modulo.nome, getattr(documento, "tipo", None)))
    if not base_nome:
        return None
    limite = date.today() + timedelta(days=margem_dias)
    melhor = None
    for docdir in pasta_base.iterdir():
        if not docdir.is_dir() or numero not in docdir.name:
            continue
        for pdf in docdir.rglob("*.pdf"):
            if pdf.name.upper().startswith("CERTIDÕES") or not pdf.name.startswith(base_nome):
                continue
            d = _data_do_arquivo(pdf)
            if d is not None and d >= limite and (melhor is None or d > melhor[1]):
                melhor = (pdf, d)
    return melhor


def verificar_vencimentos(base: Path, dias: int = 15):
    """Certidões (pelo nome 'val. dd.mm.aaaa') vencidas ou a vencer em <= `dias`.

    Devolve lista de (caminho, data, dias_restantes) ordenada pela data.
    """
    hoje = date.today()
    achados = []
    for pdf in base.rglob("*.pdf"):
        if pdf.name.upper().startswith("CERTIDÕES"):
            continue  # o PDF unido não é uma certidão individual
        d = _data_do_arquivo(pdf)
        if d is not None and (d - hoje).days <= dias:
            achados.append((pdf, d, (d - hoje).days))
    achados.sort(key=lambda t: t[1])
    return achados


def documento_no_texto(texto: str):
    """Primeiro CPF/CNPJ válido no texto (para o Escanear achar o dono do PDF)."""
    for m in re.finditer(r"\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}|\d{3}\.\d{3}\.\d{3}-\d{2}", texto or ""):
        try:
            return detectar(m.group(0))
        except DocumentoInvalido:
            continue
    return None


# Palavra-chave (MAIÚSCULAS) -> id do módulo, do mais específico ao mais genérico.
_CHAVES_CERTIDAO = [
    ("tcu_consolidada_pj", "CONSULTA CONSOLIDADA"),
    ("tcu_contas_irregulares", "CONTAS JULGADAS IRREGULARES"),
    ("tcu_inidoneos", "LICITANTES INIDÔNEOS"),
    ("cnj_improbidade", "IMPROBIDADE"),
    ("cndt_trabalhista", "DÉBITOS TRABALHISTAS"),
    ("fgts_crf", "REGULARIDADE DO FGTS"),
    ("tjrs_falencia", "FALÊNCIA"),
    ("cgu_correcional", "CORRECIONAL"),
    ("cgu_correcional", "CEIS"),
    ("receita_federal", "DÍVIDA ATIVA DA UNIÃO"),
    ("poa_iss", "INSCRIÇÃO NO ISS"),
    ("poa_iss", "ISSQN"),
    ("poa_tributos", "DÉBITOS TRIBUTÁRIOS"),
    # "SITUAÇÃO FISCAL" aparece na CND Municipal também, então não serve p/ SEFAZ.
    ("consulta_cnpj", "CADASTRO NACIONAL DA PESSOA JUR"),  # cartão CNPJ oficial
    ("consulta_cnpj", "COMPROVANTE DE INSCRIÇÃO"),
    ("consulta_cnpj", "CONSULTA CNPJ"),
]


def identificar_certidao(texto: str) -> Optional[str]:
    """Descobre qual certidão é o PDF, pelo texto. id do módulo ou None.

    Normaliza espaços (o texto de PDF quebra frases em várias linhas), senão frases
    como 'DÍVIDA ATIVA DA UNIÃO' não casam.
    """
    up = re.sub(r"\s+", " ", (texto or "").upper())
    for mid, chave in _CHAVES_CERTIDAO:
        if chave in up:
            return mid
    return None


def salvar_screenshot_erro(nome_certidao: str, pasta: Path) -> Path:
    """Tira um print da TELA INTEIRA (com a barra de tarefas/relógio do Windows).

    Usado quando uma certidão não pôde ser emitida, para registrar a tela do erro
    com data/hora visível. Nome: '<certidão> erro download <dia.mês.ano>.jpg'.
    """
    from PIL import ImageGrab  # import tardio: só precisa quando há erro

    data = date.today().strftime("%d.%m.%Y")
    nome = _nome_arquivo_seguro(f"{nome_certidao} erro download {data}.jpg")
    pasta.mkdir(parents=True, exist_ok=True)
    caminho = pasta / nome
    imagem = ImageGrab.grab()  # tela primária inteira, incluindo a barra do Windows
    imagem.convert("RGB").save(caminho, "JPEG", quality=90)
    return caminho


class ModuloCertidao:
    """Classe base para cada certidão. Subclasses implementam `executar`."""

    id: str = ""
    nome: str = ""
    descricao: str = ""
    url: str = ""
    requer_captcha: bool = False
    implementado: bool = False
    # True quando o órgão bloqueia automação (hCaptcha Enterprise: Receita, CGU):
    # o programa não tenta — apenas avisa para emitir manualmente.
    manual: bool = False
    # True quando o módulo usa a API (Infosimples) em vez do navegador: não precisa
    # de página/navegador e, em erro, não tira print da tela.
    usa_api: bool = False
    aceita: Set[TipoDoc] = frozenset({TipoDoc.CPF, TipoDoc.CNPJ})

    def aplica_para(self, tipo: TipoDoc) -> bool:
        return tipo in self.aceita

    def executar(self, page, ctx: Contexto) -> Resultado:  # pragma: no cover - abstrato
        raise NotImplementedError


if __name__ == "__main__":  # autoteste rápido dos helpers novos
    assert _data_de_nome("CND Estadual val. 25.07.2026.pdf") == date(2026, 7, 25)
    assert _data_de_nome("Consulta CNPJ.pdf") is None
    assert identificar_certidao("... LICITANTES INIDÔNEOS ...") == "tcu_inidoneos"
    assert identificar_certidao("CERTIDÃO POSITIVA ... DÍVIDA ATIVA DA UNIÃO") == "receita_federal"
    assert identificar_certidao("texto qualquer") is None
    assert extrair_validade("Esta certidão é válida até 28/8/2026.") == "28.08.2026"
    assert extrair_validade("30/07/2026Esta certidão é válida até:") == "30.07.2026"
    assert extrair_validade("Validade: 21/06/2026 a 20/07/2026") == "20.07.2026"
    assert extrair_validade("sem validade aqui") is None
    assert documento_no_texto("... CNPJ: 03.790.392/0001-28 ...") is not None

    # certidao_valida_existente: acha a válida e ignora a vencida
    import tempfile
    from types import SimpleNamespace
    doc = detectar("03.790.392/0001-28")
    mod = SimpleNamespace(nome="CND Trabalhista (CNDT)")
    hoje = date.today()
    with tempfile.TemporaryDirectory() as td:
        base_dir = Path(td)
        pasta = base_dir / f"EMPRESA X - 03.790.392.0001-28" / "2026-01-01"
        pasta.mkdir(parents=True)
        futura = (hoje + timedelta(days=90)).strftime("%d.%m.%Y")
        (pasta / f"CND Trabalhista val. {futura}.pdf").write_bytes(b"%PDF-1.4")
        achado = certidao_valida_existente(base_dir, doc, mod)
        assert achado is not None and achado[1] == hoje + timedelta(days=90)
        # outra certidão do mesmo doc não deve casar
        assert certidao_valida_existente(base_dir, doc, SimpleNamespace(nome="CND Federal CNPJ (RFB/PGFN)")) is None
        # vencida não conta
        for p in pasta.glob("*.pdf"):
            p.unlink()
        passada = (hoje - timedelta(days=1)).strftime("%d.%m.%Y")
        (pasta / f"CND Trabalhista val. {passada}.pdf").write_bytes(b"%PDF-1.4")
        assert certidao_valida_existente(base_dir, doc, mod) is None
    print("base.py autoteste OK")
