"""Testes da validação/detecção de CPF e CNPJ."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from certidoes.documento import (  # noqa: E402
    Documento,
    DocumentoInvalido,
    TipoDoc,
    detectar,
    formata,
    valida_cnpj,
    valida_cpf,
)

# Documentos válidos conhecidos (gerados; não pertencem a ninguém em particular).
CPF_VALIDO = "52998224725"
CNPJ_VALIDO = "11222333000181"


def test_cpf_valido():
    assert valida_cpf(CPF_VALIDO)
    assert valida_cpf("529.982.247-25")


def test_cpf_invalido():
    assert not valida_cpf("52998224724")  # último dígito errado
    assert not valida_cpf("11111111111")  # todos iguais
    assert not valida_cpf("123")          # tamanho errado


def test_cnpj_valido():
    assert valida_cnpj(CNPJ_VALIDO)
    assert valida_cnpj("11.222.333/0001-81")


def test_cnpj_invalido():
    assert not valida_cnpj("11222333000180")  # dígito errado
    assert not valida_cnpj("00000000000000")  # todos iguais


def test_detectar_cpf():
    doc = detectar("529.982.247-25")
    assert doc == Documento(CPF_VALIDO, TipoDoc.CPF)
    assert doc.tipo is TipoDoc.CPF


def test_detectar_cnpj():
    doc = detectar("11.222.333/0001-81")
    assert doc.tipo is TipoDoc.CNPJ
    assert doc.numero == CNPJ_VALIDO


def test_detectar_invalido_tamanho():
    with pytest.raises(DocumentoInvalido):
        detectar("12345")


def test_detectar_invalido_digito():
    with pytest.raises(DocumentoInvalido):
        detectar("52998224724")


def test_formata():
    assert formata(CPF_VALIDO) == "529.982.247-25"
    assert formata(CNPJ_VALIDO) == "11.222.333/0001-81"
    assert formata("123") == "123"
