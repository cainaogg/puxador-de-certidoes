# Histórico de mudanças

Este arquivo resume o que mudou em cada versão do **Puxador de Certidões**
(apenas a versão original em Python).

## [2.4.0] — 2026-07-19

### Verificação de atualização + auto-atualização
- O sino agora também avisa quando há uma **versão nova no GitHub**, com um
  botão **Atualizar** que baixa o `.exe` sozinho. Ao terminar, você escolhe
  **Reiniciar** (aplica e reabre na hora) ou **Cancelar** (continua usando —
  a troca acontece sozinha na próxima vez que fechar o programa).

### Certidões pela API (Infosimples) — Cartão CNPJ, TCU e CPF na Receita
- **Cartão CNPJ** e **Consulta Consolidada (TCU)** ganham a opção **Baixar
  pela API** em Configurações › Preferência de Download, igual a Receita
  Federal já tinha — alternativa paga que não depende de captcha nem de
  navegador.
- A **Consulta Consolidada (TCU)** também passou a abrir no seu navegador por
  padrão (em vez de tentar sozinha): o firewall desse serviço específico do
  TCU bloqueia qualquer navegador automatizado, mesmo com histórico real —
  testado antes de desistir da automação.
- **CND Federal para CPF** agora também funciona pela API (antes só CNPJ) —
  basta informar a data de nascimento na lista de documentos, do jeito que
  o programa já pedia para a emissão manual.
- Corrigido um recibo que a Infosimples às vezes devolve em HTML em vez de
  PDF — o programa detecta e converte para PDF de verdade antes de salvar.

### Correções
- **Perfil de download vazando entre CNPJ e CPF.** Uma certidão marcada no
  perfil só para CNPJ (ex.: Comprovante ISSQN) podia ser emitida também para
  os CPFs do mesmo lote — o programa só olhava se o site aceitava aquele tipo
  de documento, não o que o perfil realmente pedia. Corrigido.
- **Importador da pasta Downloads** agora vigia a sessão inteira (não só
  depois que tudo termina) — documentos manuais são movidos e renomeados
  assim que você baixa, mesmo com o resto do lote ainda rodando. Ganha mais
  3 minutos de tolerância depois que a sessão acaba.
- **Pasta de downloads do navegador agora é configurável** (Configurações ›
  Preferência de Download) — útil se o seu navegador salva em outro lugar
  que não a Downloads padrão do Windows.
- **Configurações vazando da janela.** A tela de Configurações podia ficar
  maior que a própria janela do programa; agora se ajusta ao tamanho dela. O
  sino também parou de responder a clique por trás da tela de Configurações.

## [2.3.0] — 2026-07-18

### Sino de notificações de vencimento
- **Avisa sozinho ao abrir o programa.** Um sino no canto superior direito mostra
  quantas certidões já baixadas estão vencidas ou vencendo nos próximos 15 dias —
  sem precisar clicar em nada.
- **Lista com detalhe e exclusão.** Clique no sino para ver uma notificação por
  linha; clique numa linha para ver empresa, documento e data de vencimento, com
  um botão para excluir o aviso. Abrir o sino zera o contador, mas a lista continua
  disponível para consulta.
- **Botão "Verificar validade" refeito.** Não pede mais uma pasta — dispara a
  mesma checagem automática na hora, sob demanda, e abre o sino com o resultado.

### Fila única de captchas no fim do lote
- As certidões que **sempre** exigem você (CND Federal, Cartão CNPJ e CEIS) não
  interrompem mais o lote espalhadas ao longo da execução. O programa baixa
  primeiro tudo que consegue sozinho, de todos os CNPJs/CPFs, e só depois te
  chama para essas três — de uma vez, sentado, em vez de aos poucos.

### Botão "Atualizar processo"
- Escolhe a pasta de uma empresa/pessoa já processada, reconhece o CNPJ/CPF pelo
  nome da pasta e refaz a busca — como o programa já pula sozinho o que ainda
  está válido, na prática só baixa o que venceu ou nunca saiu.

### Nomenclatura dos Documentos
- **Configurações › Nomenclatura dos Documentos** (nova aba): escolha como cada
  certidão é nomeada no arquivo final. Clique num documento na lista, escreva o
  nome de sua preferência e salve — ou restaure o padrão do programa quando
  quiser. Vale tanto para a renomeação automática quanto para o botão
  **"Renomear Documentos"** (antigo "Escanear baixados", que ganhou esse nome
  porque é exatamente o que ele faz).

### Correções
- **Abas órfãs em POA/TJRS/CNJ.** Depois de baixar, algumas certidões pareciam
  "reabrir e tentar de novo" até um clique manual na janela. Corrigido em duas
  frentes: os escutadores de página que causavam a aba fantasma agora são
  removidos corretamente, e o programa simula um clique na janela antes de
  fechá-la (sem risco — o arquivo já foi salvo nesse momento).
- **Duas janelas abrindo ao mesmo tempo.** Um clique duplo (ou usar "Atualizar
  processo" durante uma busca em andamento) podia disparar dois lotes em
  paralelo, cada um com seu próprio navegador. Agora uma segunda tentativa é
  rejeitada com um aviso, enquanto a primeira continua normalmente.
- **Popup de "Traduzir esta página?"** desabilitado — não aparece mais durante
  a automação.

## [2.2.0] — 2026-07-15

### Perfis de download
- **Editor de perfis (Configurações › Perfis).** Um perfil define quais certidões
  os chips **CNPJ** e **CPF** marcam de uma vez na lista. Dá para criar quantos
  perfis quiser (ex.: "Inexigibilidade" com só 3 documentos), escolher o ativo e
  trocar quando quiser. O perfil **Padrão** é fixo (todas as de CNPJ + todas as de
  CPF) e serve de referência — não pode ser editado nem excluído.
- **Indicador do perfil ativo** sempre visível ao lado de "Certidões", e um aviso
  (toast) ao ativar, salvar ou excluir um perfil.

### Lista de certidões reformulada
- **Nomes mais curtos** na lista (o órgão foi para o "?" de cada uma) — ex.:
  "CND Federal" em vez de "CND Federal CNPJ (RFB/PGFN)".
- **Etiquetas CNPJ/CPF** em cada linha, mostrando para quem aquela certidão serve.
- **Botões "Marcar: CNPJ / CPF"** no topo da lista substituem o antigo "Marcar
  todas" — cada um liga/desliga de forma independente (dá para combinar os dois).

### Certidões de CPF — de 5 para 10
Testadas uma a uma com documento real, passaram a aceitar **CPF** além de CNPJ:
**CND Trabalhista (CNDT/TST)**, **CND Municipal (Porto Alegre)**, **CND Estadual
(SEFAZ-RS)**, **Certificado FGTS (Caixa)** e **Comprovante ISSQN (Porto Alegre)**.
Somadas às 5 que já aceitavam CPF (CND Federal, Improbidade/CNJ, CEIS, e as duas
do TCU), chegam a **10 das 13 certidões**. As 3 que ficam só para CNPJ (Cartão
CNPJ, Certidão de Falência do TJRS e Consulta Consolidada do TCU) são assim por
natureza do próprio serviço ou por falta de dado público equivalente para CPF.

### Configurações redesenhadas
- Janela com **abas laterais** (Perfis, Preferência de Download, API Infosimples,
  Aparência) em vez de um formulário único.
- Aba da **API Infosimples** explica o que ela faz, como criar a conta (com R$
  100 de crédito) e como configurar — sinalizada como recurso em construção.

### Correções
- **SEFAZ-RS (CND Estadual):** corrigido um caso em que, ao consultar uma
  certidão que dá **positiva** (há débito), o site exige login do titular e o
  programa podia confundir a tela de aviso com a certidão em si. Agora reporta
  um erro claro em vez de gerar um arquivo incorreto.

## [2.1.0] — 2026-07-13

### Nova interface
- **Interface visual reformulada.** A tela foi redesenhada do zero (HTML/CSS
  modernos), fiel ao design: tipografia, ícones, espaçamentos e a lista de
  certidões com visual mais limpo. O motor que baixa as certidões é o mesmo —
  só a aparência e a usabilidade mudaram.
- **Tema claro/escuro.** Botão sol/lua no menu lateral alterna entre os dois
  temas; a escolha fica salva.
- **Cor de destaque personalizável.** Em Configurações há um seletor com 6
  cores para a cor de destaque da interface.
- **Botão do site em cada certidão.** Cada linha da lista tem um botão que abre
  o site oficial daquela certidão no navegador — útil para as que exigem
  emissão manual.
- **Cores no verificador de validade.** Ao escanear os vencimentos, cada
  documento aparece colorido: verde (ok), amarelo (vence em até 7 dias) e
  vermelho (vencido).

### Correções
- **Botão "Abrir pasta" volta a funcionar no executável.** No .exe ele não abria
  a pasta de downloads; agora abre pelo Explorer do Windows.
- **Importa o Cartão CNPJ sozinho.** O novo Cartão CNPJ da Receita imprime o
  número com espaços, o que impedia o reconhecimento na pasta Downloads. Agora
  ele é reconhecido pelos dígitos, movido e renomeado como as demais.

### Compatibilidade
- **CNPJ alfanumérico (jul/2026).** Reconhece e valida o novo formato de CNPJ com
  letras — 12 posições alfanuméricas + 2 dígitos verificadores (cálculo por
  ASCII−48, módulo 11), conforme o Anexo Único da IN RFB nº 2.119. Os CNPJs
  numéricos que já existem continuam funcionando igual.

### Observações
- A interface abre em uma **janela de aplicativo do Edge do Windows**,
  independente do seu navegador padrão (mesmo que use Chrome ou Firefox).
- Na **primeira abertura** o programa leva alguns segundos para carregar (o
  executável se descompacta a cada início) — isso é normal.

## [1.1.0] — 2026-07-09

### Novidades
- **Sócio majoritário na pasta do CNPJ.** Um CPF colocado logo abaixo de um CNPJ
  na lista é tratado como sócio daquela empresa: todas as certidões dele (as
  automáticas e as importadas) vão para a MESMA pasta do CNPJ.
- **Importa sozinho os documentos da Receita.** Cartão CNPJ e CND Federal abrem no
  seu navegador (a Receita bloqueia automação). Agora, quando você os baixa, o
  programa os encontra na pasta Downloads pelo conteúdo (reconhece a certidão e o
  CNPJ/CPF dentro dela), move para a pasta certa e renomeia com a validade — sem
  clicar em nada. Só toca em PDFs recentes, reconhecidos e que casam com a sessão.
- **Certidão de Improbidade (CNJ) automática.** Antes abria o site para
  preenchimento manual. Agora preenche e emite sozinho; o reCAPTCHA é resolvido
  pela NopeCHA (ou por você, no modo assistido). O nome do CNPJ vem da base
  pública; para **CPF** (sócio majoritário), informe o nome na mesma linha do CPF
  (ex.: `123.456.789-00 FULANO DE TAL`).
- **CND Trabalhista (CNDT/TST) com captcha automático.** O captcha de texto em
  imagem do TST passa a ser resolvido **sozinho** (OCR offline e gratuito, com
  novas tentativas se errar). Antes era assistido (você digitava). Se o OCR não
  estiver disponível, cai no modo assistido.
- **Certidão de Falência (TJRS) automática.** Antes o programa abria o site para
  você preencher à mão. Agora ele consulta a razão social e o endereço do CNPJ
  numa base pública gratuita (BrasilAPI) e **preenche e emite sozinho** — o site
  do TJRS não tem captcha. Se a consulta pública falhar, cai no modo manual.
- **Não rebaixar o que ainda é válido.** Antes de baixar, o programa verifica se
  já existe aquela mesma certidão **ainda não vencida** e, se houver, pula (badge
  "Já válida"). Economiza tempo e captcha — inclusive nas manuais.
- **Autoria e contato** na tela de Ajuda.
- **Ícone próprio** do executável.

### Correções
- **TCU (Inidôneos, Contas Julgadas, Consulta Consolidada): novas tentativas.**
  Em rede lenta/proxy (ex.: trabalho), a plataforma do TCU às vezes falha de forma
  intermitente ("captcha expirou", "erro no serviço", "não localizado", ou fica
  processando). Agora o programa **tenta de novo automaticamente** (recarrega e
  recalcula o ALTCHA), o que costuma resolver esses erros passageiros.
- **Abas extras fechadas.** Depois de baixar/emitir uma certidão que abre em nova
  aba (ex.: TJRS), o programa fecha as abas/popups que sobraram.
- **CND Municipal e Comprovante ISS (Porto Alegre).** Em navegador corporativo
  que força o PDF a **baixar** por uma aba que abre e fecha na hora (ex.: Edge
  gerenciado de intranet), o programa não capturava o arquivo e dava erro
  (`TargetClosedError`). Agora captura o download em **qualquer aba** e também
  suporta a certidão que abre como PDF numa aba nova.

### Desempenho
- **Início mais rápido.** Antes, ao começar um CNPJ, o programa ficava parado
  (às vezes >1 min, em rede lenta/proxy) consultando a razão social só para
  nomear a pasta. Agora a pasta é criada na hora (com o número) e o download
  começa imediatamente; o nome ("NOME - número") é aplicado no fim. O tempo
  limite da consulta também caiu de 30s para 12s por fonte.

## [1.0.0] — 2026-07

### Base
- Baixa em lote as certidões de um ou mais CNPJ/CPF, renomeando cada arquivo com
  a data de validade e organizando por documento.
- Interface em **modo escuro** com badges de status, ícones, fonte Inter e
  abertura centralizada.
- Utilitários: escanear PDFs baixados, verificador de vencimentos e juntar PDFs.
- Resolve captchas com a extensão NopeCHA (modo assistido quando necessário).
