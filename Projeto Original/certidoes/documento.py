"""Detecção, validação e formatação de CPF e CNPJ."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum


class TipoDoc(str, Enum):
    CPF = "cpf"
    CNPJ = "cnpj"


def _somente_digitos(valor: str) -> str:
    return re.sub(r"\D", "", valor or "")


def _digitos_verificadores_cpf(base: str) -> str:
    """Calcula os 2 dígitos verificadores de um CPF a partir dos 9 primeiros."""
    digitos = [int(c) for c in base]
    for _ in range(2):
        peso = len(digitos) + 1
        soma = sum(d * (peso - i) for i, d in enumerate(digitos))
        resto = (soma * 10) % 11
        digitos.append(0 if resto == 10 else resto)
    return "".join(str(d) for d in digitos[-2:])


def _digitos_verificadores_cnpj(base: str) -> str:
    """Calcula os 2 dígitos verificadores de um CNPJ a partir dos 12 primeiros."""
    pesos_base = [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    digitos = [int(c) for c in base]
    for _ in range(2):
        pesos = pesos_base[-len(digitos):]
        soma = sum(d * p for d, p in zip(digitos, pesos))
        resto = soma % 11
        digitos.append(0 if resto < 2 else 11 - resto)
    return "".join(str(d) for d in digitos[-2:])


def valida_cpf(valor: str) -> bool:
    num = _somente_digitos(valor)
    if len(num) != 11 or num == num[0] * 11:
        return False
    return _digitos_verificadores_cpf(num[:9]) == num[9:]


def valida_cnpj(valor: str) -> bool:
    num = _somente_digitos(valor)
    if len(num) != 14 or num == num[0] * 14:
        return False
    return _digitos_verificadores_cnpj(num[:12]) == num[12:]


def formata(valor: str) -> str:
    """Formata com máscara conforme o tamanho (CPF ou CNPJ); senão devolve os dígitos."""
    num = _somente_digitos(valor)
    if len(num) == 11:
        return f"{num[:3]}.{num[3:6]}.{num[6:9]}-{num[9:]}"
    if len(num) == 14:
        return f"{num[:2]}.{num[2:5]}.{num[5:8]}/{num[8:12]}-{num[12:]}"
    return num


@dataclass(frozen=True)
class Documento:
    """Um CPF ou CNPJ já validado."""

    numero: str  # somente dígitos
    tipo: TipoDoc

    @property
    def formatado(self) -> str:
        return formata(self.numero)

    def __str__(self) -> str:
        return self.formatado


class DocumentoInvalido(ValueError):
    """Levantada quando o texto informado não é um CPF nem um CNPJ válido."""


def detectar(valor: str) -> Documento:
    """Identifica se o texto é CPF ou CNPJ válido. Levanta DocumentoInvalido caso contrário."""
    num = _somente_digitos(valor)
    if len(num) == 11:
        if not valida_cpf(num):
            raise DocumentoInvalido("CPF inválido (dígitos verificadores não conferem).")
        return Documento(num, TipoDoc.CPF)
    if len(num) == 14:
        if not valida_cnpj(num):
            raise DocumentoInvalido("CNPJ inválido (dígitos verificadores não conferem).")
        return Documento(num, TipoDoc.CNPJ)
    raise DocumentoInvalido(
        f"Informe 11 dígitos (CPF) ou 14 dígitos (CNPJ). Recebido: {len(num)} dígito(s)."
    )
