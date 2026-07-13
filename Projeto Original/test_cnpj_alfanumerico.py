"""Testes do CNPJ alfanumérico (jul/2026) + retrocompatibilidade.

Roda direto: `.venv\\Scripts\\python.exe test_cnpj_alfanumerico.py`
"""

from certidoes.documento import (
    Documento,
    DocumentoInvalido,
    TipoDoc,
    detectar,
    formata,
    valida_cnpj,
    valida_cpf,
)

# --- Vetores conhecidos ---
CNPJ_ALFA = "12ABC34501DE35"       # exemplo oficial Serpro (DV 35)
CNPJ_NUM = "04017371000137"        # CNPJ numérico existente (DV 37)
CPF = "01629822086"                # CPF válido


def test_dv_alfanumerico():
    assert valida_cnpj(CNPJ_ALFA), "CNPJ alfanumérico oficial deveria ser válido"
    assert valida_cnpj("12.ABC.345/01DE-35"), "com máscara também"
    assert not valida_cnpj("12ABC34501DE34"), "DV errado deve falhar"
    assert not valida_cnpj("12ABC34501DE3X"), "DV não-numérico deve falhar"
    assert not valida_cnpj("1ABC34501DE35"), "13 chars deve falhar"


def test_retrocompat_numerico():
    assert valida_cnpj(CNPJ_NUM)
    assert valida_cnpj("04.017.371/0001-37")
    assert not valida_cnpj("04017371000138")  # DV errado
    assert valida_cpf(CPF)
    assert not valida_cpf("01629822087")


def test_detectar_tipo():
    assert detectar(CNPJ_ALFA).tipo is TipoDoc.CNPJ
    assert detectar("12.ABC.345/01DE-35").numero == CNPJ_ALFA  # limpo+maiúsculo
    assert detectar("12abc34501de35").numero == CNPJ_ALFA      # aceita minúsculo
    assert detectar(CNPJ_NUM).tipo is TipoDoc.CNPJ
    assert detectar("04.017.371/0001-37").numero == CNPJ_NUM
    assert detectar(CPF).tipo is TipoDoc.CPF
    assert detectar("016.298.220-86").numero == CPF


def test_detectar_com_nome_junto():
    # CPF de sócio com nome na mesma linha (usado no CNJ): nome é ignorado.
    d = detectar("016.298.220-86 FULANO DE TAL")
    assert d.tipo is TipoDoc.CPF and d.numero == CPF
    # CNPJ alfanumérico isolado continua reconhecido.
    assert detectar("  12ABC34501DE35  ").numero == CNPJ_ALFA


def test_detectar_invalido():
    for ruim in ["", "123", "abcdefghij", "00000000000000", "111.111.111-11"]:
        try:
            detectar(ruim)
            assert False, f"deveria ter falhado: {ruim!r}"
        except DocumentoInvalido:
            pass


def test_formata():
    assert formata(CNPJ_ALFA) == "12.ABC.345/01DE-35"
    assert formata(CNPJ_NUM) == "04.017.371/0001-37"
    assert formata(CPF) == "016.298.220-86"


if __name__ == "__main__":
    for nome, fn in sorted(globals().items()):
        if nome.startswith("test_") and callable(fn):
            fn()
            print(f"OK  {nome}")
    print("\nTODOS OS TESTES PASSARAM.")
