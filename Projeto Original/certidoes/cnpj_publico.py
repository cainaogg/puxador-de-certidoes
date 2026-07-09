"""Consulta de dados cadastrais de CNPJ em APIs públicas GRATUITAS.

Usa os dados abertos da Receita Federal via BrasilAPI (e minhareceita.org como
reserva) — sem captcha, sem login e sem custo. Serve para:
  - preencher razão social/endereço onde é necessário (ex.: TJRS), sem gastar
    crédito de API paga;
  - gerar um PDF "Consulta CNPJ" com todos os dados (via fpdf2, sem navegador).
"""

from __future__ import annotations

import json
import urllib.request
from datetime import date
from pathlib import Path
from typing import Optional

from .documento import formata

FONTES = [
    "https://brasilapi.com.br/api/cnpj/v1/{cnpj}",
    "https://minhareceita.org/{cnpj}",
]
CNPJREVA_URL = "https://solucoes.receita.fazenda.gov.br/Servicos/cnpjreva/"


def consultar(cnpj_digitos: str) -> Optional[dict]:
    """Busca os dados do CNPJ numa API pública gratuita. None se nenhuma responder."""
    cnpj = "".join(filter(str.isdigit, cnpj_digitos))
    for url in FONTES:
        try:
            req = urllib.request.Request(
                url.format(cnpj=cnpj), headers={"User-Agent": "Mozilla/5.0"}
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                dados = json.loads(resp.read().decode("utf-8"))
            if dados.get("razao_social") or dados.get("nome"):
                return dados
        except Exception:  # noqa: BLE001 - tenta a próxima fonte
            continue
    return None


def _data_br(iso: str) -> str:
    """'2007-12-13' -> '13/12/2007' (devolve o original se não casar)."""
    try:
        a, m, d = (iso or "")[:10].split("-")
        return f"{d}/{m}/{a}"
    except Exception:  # noqa: BLE001
        return iso or ""


def _moeda(valor) -> str:
    try:
        n = float(valor)
        return "R$ " + f"{n:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception:  # noqa: BLE001
        return str(valor or "")


def _telefone(ddd_numero: str) -> str:
    s = "".join(filter(str.isdigit, ddd_numero or ""))
    if len(s) >= 10:
        return f"({s[:2]}) {s[2:-4]}-{s[-4:]}"
    return ddd_numero or ""


def endereco_completo(d: dict) -> str:
    """Monta o endereço numa linha a partir do dict da API."""
    tipo = d.get("descricao_tipo_de_logradouro") or ""
    logr = " ".join(filter(None, [tipo, d.get("logradouro") or ""])).strip()
    partes = [logr]
    if d.get("numero"):
        partes.append(f"nº {d['numero']}")
    if d.get("complemento"):
        partes.append(str(d["complemento"]))
    linha1 = ", ".join(p for p in partes if p)
    bairro = d.get("bairro") or ""
    cidade = f"{d.get('municipio') or ''}/{d.get('uf') or ''}".strip("/")
    cep = d.get("cep") or ""
    cep_fmt = f"{cep[:5]}-{cep[5:]}" if len(cep) == 8 else cep
    cauda = ", ".join(p for p in [bairro, cidade, f"CEP {cep_fmt}" if cep_fmt else ""] if p)
    return " - ".join(p for p in [linha1, cauda] if p)


def nome_e_endereco(cnpj_digitos: str) -> tuple[str, str]:
    """Retorna (razão social, endereço) ou ('','') se a consulta falhar."""
    d = consultar(cnpj_digitos)
    if not d:
        return "", ""
    return (d.get("razao_social") or d.get("nome") or ""), endereco_completo(d)


def _l1(texto: str) -> str:
    """Garante que o texto seja codificável nas fontes-core do PDF (latin-1)."""
    return (texto or "").encode("latin-1", "replace").decode("latin-1")


def gerar_pdf(cnpj_digitos: str, caminho: Path) -> bool:
    """Gera o PDF 'Consulta CNPJ' com os dados públicos. True se gerou."""
    d = consultar(cnpj_digitos)
    if not d:
        return False

    from fpdf import FPDF  # import tardio

    pdf = FPDF(format="A4")
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    larg = pdf.w - 2 * pdf.l_margin

    def titulo(txt):
        pdf.set_font("Helvetica", "B", 15)
        pdf.set_text_color(20, 60, 120)
        pdf.multi_cell(larg, 8, _l1(txt), new_x="LMARGIN", new_y="NEXT")
        pdf.set_text_color(0, 0, 0)

    def secao(txt):
        pdf.ln(2)
        pdf.set_font("Helvetica", "B", 11)
        pdf.set_fill_color(230, 235, 245)
        pdf.cell(larg, 7, _l1(" " + txt), fill=True, new_x="LMARGIN", new_y="NEXT")
        pdf.ln(1)

    def campo(rotulo, valor):
        if not valor:
            return
        pdf.set_font("Helvetica", "B", 10)
        pdf.cell(42, 6, _l1(rotulo), new_x="END", new_y="LAST")
        pdf.set_font("Helvetica", "", 10)
        pdf.multi_cell(larg - 42, 6, _l1(str(valor)), new_x="LMARGIN", new_y="NEXT")

    cnpj_fmt = formata(cnpj_digitos)
    titulo("CONSULTA CNPJ")
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(110, 110, 110)
    pdf.multi_cell(larg, 5, _l1("Dados cadastrais - fonte: dados abertos da Receita "
                                "Federal (BrasilAPI). Documento sem valor de certidão oficial."),
                   new_x="LMARGIN", new_y="NEXT")
    pdf.set_text_color(0, 0, 0)
    pdf.ln(2)

    secao("Identificação")
    campo("CNPJ:", cnpj_fmt)
    campo("Razão social:", d.get("razao_social") or d.get("nome"))
    campo("Nome fantasia:", d.get("nome_fantasia"))
    campo("Matriz/Filial:", d.get("descricao_identificador_matriz_filial"))

    secao("Situação cadastral")
    campo("Situação:", d.get("descricao_situacao_cadastral"))
    campo("Data da situação:", _data_br(d.get("data_situacao_cadastral", "")))
    campo("Motivo:", d.get("descricao_motivo_situacao_cadastral"))
    campo("Abertura:", _data_br(d.get("data_inicio_atividade", "")))

    secao("Natureza e porte")
    campo("Natureza jurídica:", d.get("natureza_juridica"))
    campo("Porte:", d.get("porte"))
    campo("Capital social:", _moeda(d.get("capital_social")))
    campo("Simples Nacional:", "Optante" if d.get("opcao_pelo_simples") else "Não optante")
    campo("MEI:", "Optante" if d.get("opcao_pelo_mei") else "Não optante")

    secao("Endereço e contato")
    campo("Endereço:", endereco_completo(d))
    campo("Telefone:", _telefone(d.get("ddd_telefone_1", "")))
    campo("E-mail:", d.get("email"))

    secao("Atividade econômica")
    cnae = d.get("cnae_fiscal")
    campo("Principal:", f"{cnae} - {d.get('cnae_fiscal_descricao','')}" if cnae else "")
    secundarios = d.get("cnaes_secundarios") or []
    if secundarios and secundarios[0].get("codigo"):
        pdf.set_font("Helvetica", "B", 10)
        pdf.cell(larg, 6, _l1("Secundárias:"), new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "", 9)
        for s in secundarios[:25]:
            pdf.multi_cell(larg, 5, _l1(f"  - {s.get('codigo')} - {s.get('descricao','')}"),
                           new_x="LMARGIN", new_y="NEXT")

    socios = d.get("qsa") or []
    if socios:
        secao("Quadro de sócios e administradores")
        pdf.set_font("Helvetica", "", 9)
        for s in socios:
            nome = s.get("nome_socio") or s.get("nome") or ""
            qual = s.get("qualificacao_socio") or ""
            pdf.multi_cell(larg, 5, _l1(f"  - {nome}" + (f" ({qual})" if qual else "")),
                           new_x="LMARGIN", new_y="NEXT")

    pdf.ln(4)
    pdf.set_font("Helvetica", "I", 8)
    pdf.set_text_color(120, 120, 120)
    pdf.multi_cell(larg, 4, _l1(
        f"Gerado em {date.today().strftime('%d/%m/%Y')} a partir dos dados abertos da "
        f"Receita Federal. Para o comprovante oficial, use {CNPJREVA_URL}"))

    caminho.parent.mkdir(parents=True, exist_ok=True)
    pdf.output(str(caminho))
    return True
