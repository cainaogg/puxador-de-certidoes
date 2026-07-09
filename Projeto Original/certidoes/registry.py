"""Catálogo de todas as certidões (implementadas e planejadas)."""

from __future__ import annotations

from typing import List

from .base import ModuloCertidao
from .documento import TipoDoc
from .modulos.cgu import CGUCorrecional
from .modulos.cndt import CNDT
from .modulos.cnj import CNJImprobidade
from .modulos.consulta_cnpj import ConsultaCNPJ
from .modulos.fgts import FGTS
from .modulos.poa_iss import POAISS
from .modulos.poa_tributos import POATributos
from .modulos.receita_federal import ReceitaFederal
from .modulos.sefaz_rs import SefazRS
from .modulos.tcu_consolidada import TCUConsolidada
from .modulos.tcu_contas_irregulares import TCUContasIrregulares
from .modulos.tcu_inidoneos import TCUInidoneos
from .modulos.tjrs_falencia import TJRSFalencia

AMBOS = frozenset({TipoDoc.CPF, TipoDoc.CNPJ})
SO_CNPJ = frozenset({TipoDoc.CNPJ})


def _planejado(
    id: str,
    nome: str,
    url: str,
    *,
    aceita=AMBOS,
    captcha: bool = False,
) -> ModuloCertidao:
    """Cria um item ainda não implementado (aparece na tela, mas desabilitado)."""
    m = ModuloCertidao()
    m.id = id
    m.nome = nome
    m.descricao = "Ainda não implementado — planejado para as próximas etapas."
    m.url = url
    m.aceita = aceita
    m.requer_captcha = captcha
    m.implementado = False
    return m


# Ordem definida pelo usuário (2026-06-22).
REGISTRY: List[ModuloCertidao] = [
    ConsultaCNPJ(),          # 1 - Consulta CNPJ
    POATributos(),           # 2 - CND Municipal (POA)
    SefazRS(),               # 3 - CND Estadual (RS)
    ReceitaFederal(),        # 4 - CND Federal
    CNDT(),                  # 5 - CND Trabalhista
    FGTS(),                  # 6 - Certificado FGTS
    TJRSFalencia(),          # 7 - Certidão Judicial Cível Negativa - Falência
    CNJImprobidade(),        # 8 - Improbidade Administrativa
    TCUInidoneos(),          # 9 - Licitantes Inidôneos
    TCUContasIrregulares(),  # 10 - Contas Julgadas Irregulares
    CGUCorrecional(),        # 11 - Consulta CEIS
    TCUConsolidada(),        # 12 - Consulta Consolidada TCU
    POAISS(),                # 13 - Comprovante ISSQN
]


def por_id(modulo_id: str) -> ModuloCertidao:
    for m in REGISTRY:
        if m.id == modulo_id:
            return m
    raise KeyError(modulo_id)
