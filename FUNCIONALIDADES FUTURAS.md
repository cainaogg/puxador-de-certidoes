# Funcionalidades futuras (fila)

- **Item 2 — Outros municípios/estados:** permitir escolher o município (CND Municipal)
  e o estado (CND Estadual). Cada site novo = um módulo novo + um seletor de
  município/UF na tela. O usuário tem os sites salvos; implementar quando enviar.
- **Item 5.1 — Importar planilha:** importar uma lista de CNPJs de Excel/CSV direto
  para o lote. (adiado)
  - **Certidão de Falência (TJRS) — NÃO dá para automatizar via CPF.** O formulário
    de Pessoa Física exige Nome da Mãe, RG (+órgão+UF) e Endereço — nenhum tem fonte
    pública para CPF (diferente do CNPJ, que vem da BrasilAPI). Pedir isso linha a
    linha não é viável no formato atual. Fica só CNPJ.
