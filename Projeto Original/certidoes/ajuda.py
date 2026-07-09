"""Textos de ajuda exibidos na interface (Projeto Original)."""

from __future__ import annotations

# Explicação curta de cada certidão (chave = id do módulo).
CERTIDOES = {
    "receita_federal":
        "CND Federal (RFB/PGFN): certidão de débitos relativos a tributos federais e à "
        "Dívida Ativa da União. Nesta versão, por padrão o programa abre o site da Receita "
        "no seu navegador para você emitir na mão (a Receita bloqueia automação). Nas "
        "Configurações você pode optar por baixar pela API paga (Infosimples) informando o "
        "token. Para CPF, sempre abre o site (a Receita pede a data de nascimento).",
    "cnj_improbidade":
        "Certidão Negativa de Improbidade Administrativa e Inelegibilidade (CNJ). O programa "
        "abre o site do CNJ no seu navegador para você preencher os dados e gerar a certidão "
        "(tipo Jurídica para CNPJ, Física para CPF).",
    "tcu_inidoneos":
        "Certidão Negativa de Licitantes Inidôneos (TCU): diz se há impedimento de "
        "participar de licitações. Sai do site do TCU; o desafio anti-robô (ALTCHA) é "
        "resolvido sozinho.",
    "tcu_contas_irregulares":
        "Certidão Negativa de Contas Julgadas Irregulares (TCU): diz se há contas julgadas "
        "irregulares com decisão definitiva. Sai do site do TCU (ALTCHA automático).",
    "cgu_correcional":
        "Consulta CEIS / Certidão Negativa Correcional (CGU): verifica os cadastros de "
        "empresas/pessoas inidôneas e punidas (CEIS, CNEP, CEPIM). Modo assistido: abre o "
        "site e você resolve o captcha de imagem na janela.",
    "tcu_consolidada_pj":
        "Consulta Consolidada de Pessoa Jurídica (TCU): relatório único que reúne TCU, CNJ "
        "e Portal da Transparência (CEIS/CNEP). Só para CNPJ; sai do site do TCU.",
    "sefaz_rs":
        "CND Estadual do RS (SEFAZ-RS): certidão de situação fiscal junto ao estado do Rio "
        "Grande do Sul. Sai do site da SEFAZ (resolve o ALTCHA sozinho).",
    "cndt_trabalhista":
        "CND Trabalhista (CNDT/TST): certidão de débitos trabalhistas. Modo assistido: o "
        "captcha de imagem é resolvido por você na janela que abre.",
    "fgts_crf":
        "Certificado de Regularidade do FGTS (CRF), emitido pela CAIXA. Mostra se a empresa "
        "está regular com o FGTS. Sai do site da CAIXA.",
    "tjrs_falencia":
        "Certidão Judicial Cível Negativa de Falência (1º grau, TJRS). O programa abre o "
        "site do TJRS no seu navegador para você preencher os dados (razão social, CNPJ e "
        "endereço) e gerar a certidão. Só para CNPJ.",
    "poa_tributos":
        "CND Municipal de Porto Alegre (débitos tributários). Sai do site da prefeitura "
        "(SIAT); o captcha é resolvido automaticamente.",
    "poa_iss":
        "Comprovante de Inscrição no ISSQN de Porto Alegre. Documento cadastral (não tem "
        "data de validade). Sai do site da prefeitura.",
    "consulta_cnpj":
        "Consulta CNPJ (gov.br): abre o site oficial (cnpjreva) no seu navegador para você "
        "resolver o captcha e baixar o cartão CNPJ — é a fonte oficial e bloqueia automação. "
        "O nome da empresa usado nas pastas vem, à parte, de uma consulta gratuita automática.",
}

# Explicação geral do programa (Original).
PROGRAMA = (
    "PUXADOR DE CERTIDÕES\n\n"
    "O que faz: você informa um ou mais CNPJ/CPF, marca as certidões desejadas e o "
    "programa baixa as que dá para automatizar, já renomeando cada arquivo para o nome do "
    "documento + a data de validade (ex.: 'CND Trabalhista val. 19.12.2026.pdf').\n\n"
    "Diferença desta versão: é gratuita sempre que possível. As que os órgãos não deixam "
    "automatizar (Receita, CNJ, TJRS) abrem no seu navegador para você emitir na mão; "
    "algumas (CGU, CNDT) abrem uma janela para você resolver o captcha (modo assistido). "
    "A Receita pode, opcionalmente, usar a API paga (Infosimples) — ver Configurações.\n\n"
    "Busca em lote: digite vários documentos, um por linha. O programa processa todos de "
    "um número, depois passa para o próximo. Pode misturar CNPJ e CPF. Cada documento vai "
    "para uma pasta própria (com o número no nome).\n\n"
    "CPF: alguns documentos também saem para CPF (CND Federal, CNJ, CEIS e as duas do TCU). "
    "A CND Federal de CPF abre o site da Receita (lá você informa CPF e data de nascimento).\n\n"
    "Configurações: como emitir a Receita (navegador ou API + token).\n\n"
    "Clique no '?' de cada certidão para saber o que ela é.\n\n"
    "——————————————————————————————\n"
    "Desenvolvido por Cainã Gomes Süffert.\n"
    "Contato: caina@outlook.com"
)
