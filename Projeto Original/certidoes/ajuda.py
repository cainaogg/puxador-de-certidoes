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
        "preenche e emite sozinho (tipo Jurídica para CNPJ, Física para CPF); o reCAPTCHA é "
        "resolvido pela NopeCHA (ou por você, no modo assistido). O nome do CNPJ vem da base "
        "pública; para CPF, informe o nome na mesma linha (ex.: '123.456.789-00 FULANO DE "
        "TAL'). Se faltar o nome, abre o site para emissão manual.",
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
        "e Portal da Transparência (CEIS/CNEP). Só para CNPJ. Nesta versão, por padrão o "
        "programa abre o site no seu navegador para você consultar e baixar — o firewall "
        "desse serviço do TCU bloqueia qualquer navegador automatizado. Nas Configurações "
        "dá para trocar para a API da Infosimples (paga).",
    "sefaz_rs":
        "CND Estadual do RS (SEFAZ-RS): certidão de situação fiscal junto ao estado do Rio "
        "Grande do Sul — de CNPJ ou CPF. Sai do site da SEFAZ (resolve o ALTCHA sozinho). "
        "Se a certidão der positiva (há débito), o site exige login do titular — nesse "
        "caso o programa avisa e não dá para automatizar.",
    "cndt_trabalhista":
        "CND Trabalhista (CNDT/TST): certidão de débitos trabalhistas — de CNPJ ou CPF. "
        "O captcha de texto em imagem é resolvido automaticamente (OCR offline, gratuito), "
        "com novas tentativas se errar. Se não conseguir, cai no modo assistido (você digita "
        "o captcha na janela).",
    "fgts_crf":
        "Certificado de Regularidade do FGTS (CRF), emitido pela CAIXA. Mostra se a empresa "
        "(ou, no caso de CPF, o empregador doméstico) está regular com o FGTS. Sai do site "
        "da CAIXA.",
    "tjrs_falencia":
        "Certidão Judicial Cível Negativa de Falência (1º grau, TJRS). O programa preenche "
        "e emite sozinho: consulta a razão social e o endereço do CNPJ numa base pública "
        "gratuita (BrasilAPI) e preenche o formulário do TJRS (que não tem captcha). Só "
        "para CNPJ. Se a consulta pública falhar, abre o site para você preencher à mão.",
    "poa_tributos":
        "CND Municipal de Porto Alegre (débitos tributários) — de CNPJ ou CPF. Sai do "
        "site da prefeitura (SIAT); o captcha é resolvido automaticamente.",
    "poa_iss":
        "Comprovante de Inscrição no ISSQN de Porto Alegre — de CNPJ ou CPF (autônomo "
        "registrado). Documento cadastral (não tem data de validade). Sai do site da "
        "prefeitura.",
    "consulta_cnpj":
        "Consulta CNPJ (gov.br): nesta versão, por padrão o programa abre o site oficial "
        "(cnpjreva) no seu navegador para você resolver o captcha e baixar o cartão CNPJ "
        "— é a fonte oficial e bloqueia automação. Nas Configurações dá para trocar para a "
        "API da Infosimples (paga). O nome da empresa usado nas pastas vem, à parte, de uma "
        "consulta gratuita automática.",
}

# Nome curto exibido na LISTA (o órgão e os detalhes ficam no "?"/CERTIDOES).
LABELS = {
    "consulta_cnpj": "Cartão CNPJ",
    "poa_tributos": "CND Municipal (Porto Alegre)",
    "sefaz_rs": "CND Estadual (RS)",
    "receita_federal": "CND Federal",
    "cndt_trabalhista": "CND Trabalhista",
    "fgts_crf": "Certificado FGTS",
    "tjrs_falencia": "Certidão de Falência",
    "cnj_improbidade": "Improbidade e Inelegibilidade",
    "tcu_inidoneos": "Licitantes Inidôneos",
    "tcu_contas_irregulares": "Contas Julgadas Irregulares",
    "cgu_correcional": "Consulta CEIS",
    "tcu_consolidada_pj": "Consulta Consolidada",
    "poa_iss": "Comprovante ISSQN",
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
