# Funcionalidades futuras (fila)

- **Item 2 — Outros municípios/estados:** permitir escolher o município (CND Municipal)
  e o estado (CND Estadual). Cada site novo = um módulo novo + um seletor de
  município/UF na tela. O usuário tem os sites salvos; implementar quando enviar.
- **Item 5.1 — Importar planilha:** importar uma lista de CNPJs de Excel/CSV direto
  para o lote. (adiado)
- **CNPJ alfanumérico (jul/2026):** suportar CNPJ com letras (novos cadastros a partir
  de jul/2026). Mexe no núcleo (validação/DV, detecção, auto-import por dígitos, favorito).
  Prompt pronto em [`PROMPT - CNPJ alfanumerico.md`](PROMPT%20-%20CNPJ%20alfanumerico.md). **(FEITO)**
- **Suporte a CPF em todas as certidões:** ampliado de 5 para 10 (CND Federal, CNJ,
  CEIS, TCU Inidôneos/Contas, + agora **CND Trabalhista, Certificado FGTS, CND
  Municipal/POA, CND Estadual/RS, Comprovante ISSQN**). Cada um testado ao vivo com
  CPF real (Playwright). Corrigido de quebra um bug real no SEFAZ-RS (capturava a
  aba errada quando havia páginas extras abertas, gerando um PDF falso "(positiva)"
  quando a certidão exige login do titular — agora reporta erro claro). **(FEITO)**
  - **Certidão de Falência (TJRS) — NÃO dá para automatizar via CPF.** O formulário
    de Pessoa Física exige Nome da Mãe, RG (+órgão+UF) e Endereço — nenhum tem fonte
    pública para CPF (diferente do CNPJ, que vem da BrasilAPI). Pedir isso linha a
    linha não é viável no formato atual. Fica só CNPJ.
- **Perfis de download (Configurações):** criar perfis que definem quais certidões os
  chips CNPJ/CPF marcam. **(FEITO — commit "Editor de perfis de download")**
- **Redesenho das Configurações:** janela com aba lateral separando seções (Receita/API,
  Aparência/Cores); explicar a API Infosimples ("em construção") e como usá-la.
