"""Detecção, validação e formatação de CPF e CNPJ."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import Optional


class TipoDoc(str, Enum):
    CPF = "cpf"
    CNPJ = "cnpj"


def _somente_digitos(valor: str) -> str:
    return re.sub(r"\D", "", valor or "")


def _limpa(valor: str) -> str:
    """Remove pontuação/espaços e devolve em MAIÚSCULAS, mantendo letras — para o
    CNPJ alfanumérico (novo formato a partir de jul/2026). CPF continua só dígitos."""
    return re.sub(r"[^0-9A-Za-z]", "", valor or "").upper()


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
    """Calcula os 2 dígitos verificadores de um CNPJ a partir dos 12 primeiros.

    Aceita o CNPJ alfanumérico (jul/2026): o valor de cada caractere é o código
    ASCII menos 48 ('0'->0 … '9'->9, 'A'->17 … 'Z'->42). Para CNPJ numérico o
    resultado é idêntico ao cálculo antigo (int(c) == ord(c)-48 para dígitos)."""
    pesos_base = [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    digitos = [ord(c) - 48 for c in base]
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
    num = _limpa(valor)
    # 12 posições alfanuméricas (0-9, A-Z) + 2 dígitos verificadores numéricos.
    if not re.fullmatch(r"[A-Z0-9]{12}[0-9]{2}", num):
        return False
    if num == num[0] * 14:
        return False
    return _digitos_verificadores_cnpj(num[:12]) == num[12:]


def formata(valor: str) -> str:
    """Formata com máscara conforme o tamanho (CPF ou CNPJ); senão devolve limpo."""
    num = _limpa(valor)
    if len(num) == 11 and num.isdigit():
        return f"{num[:3]}.{num[3:6]}.{num[6:9]}-{num[9:]}"
    if len(num) == 14:
        return f"{num[:2]}.{num[2:5]}.{num[5:8]}/{num[8:12]}-{num[12:]}"
    return num


@dataclass(frozen=True)
class Documento:
    """Um CPF ou CNPJ já validado."""

    numero: str  # CPF: só dígitos. CNPJ: alfanumérico em maiúsculas (novo formato)
    tipo: TipoDoc

    @property
    def formatado(self) -> str:
        return formata(self.numero)

    def __str__(self) -> str:
        return self.formatado


class DocumentoInvalido(ValueError):
    """Levantada quando o texto informado não é um CPF nem um CNPJ válido."""


def _classifica(limpo: str) -> Optional[Documento]:
    """Classifica um token já limpo (sem pontuação) como CPF, CNPJ ou nada."""
    if len(limpo) == 11 and limpo.isdigit() and valida_cpf(limpo):
        return Documento(limpo, TipoDoc.CPF)
    if len(limpo) == 14 and valida_cnpj(limpo):
        return Documento(limpo, TipoDoc.CNPJ)
    return None


def detectar(valor: str) -> Documento:
    """Identifica CPF (11 dígitos) ou CNPJ (14 caracteres — numérico ou o novo
    alfanumérico). Ignora texto extra na mesma linha (ex.: o nome de um sócio).
    Levanta DocumentoInvalido se não achar um documento válido."""
    doc = _classifica(_limpa(valor))
    if doc is not None:
        return doc
    # Pode haver texto junto (ex.: '123.456.789-00 FULANO'): testa cada palavra.
    for tok in re.split(r"\s+", (valor or "").strip()):
        if tok:
            doc = _classifica(_limpa(tok))
            if doc is not None:
                return doc
    raise DocumentoInvalido("Informe um CPF (11 dígitos) ou CNPJ (14 caracteres) válido.")
