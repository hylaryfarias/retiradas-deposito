# Relatório diário de vendas — Grupo Ragga

São **dois envios** por dia, e cada um tem seu script:

| Envio | Quando | Script | Saída |
|---|---|---|---|
| **1. Venda bruta + entrada prevista** | de manhã, quando ela manda os PDFs | `gerar_relatorio.py` | quadrinho PNG + `texto_whatsapp.txt` |
| **2. Entradas do dia (recebimento real)** | depois, quando ela passa o que entrou | `gerar_entradas.py` | `texto_entradas.txt` |

O envio 2 é o **complemento** do 1: ele confronta o que entrou de verdade
contra a previsão que foi mandada no envio 1.

# Envio 1 — venda bruta e entrada prevista

## O que fazer quando o PDF chegar

```bash
python3 gerar_relatorio.py <pdf-do-periodo> --mes-anterior <pdf-de-um-mes-atras> --saida saida
```

Ela manda **dois** PDFs: o do período atual e o do **mesmo intervalo do mês
anterior** (ex.: 04-07/09 + 04-07/08). O segundo serve só para o voucher D+30.

Isso entrega os três arquivos em `saida/`:

| Arquivo | O que é |
|---|---|
| `vendas_card.png` | o quadrinho roxo pronto para o print do WhatsApp |
| `texto_whatsapp.txt` | o texto de venda bruta + entrada prevista |
| `formas_agrupadas.csv` | a tabela em CSV (`;` e decimal BR, abre no Excel) |

Depois: mandar o PNG e o texto no chat, com a tabela também em markdown na
resposta, e o fechamento (soma dos dias) conferido.

Flags úteis:

- `--dia 04/09/2026` — usa só aquele dia. **Sem a flag, todos os dias do PDF
  são somados num bloco único** (foi o que ela pediu: "em um dia só").
- `--mes-anterior <pdf>` — PDF do mesmo intervalo do mês anterior, de onde sai
  o voucher D+30. Sem ele, a parcela de voucher não entra.
- `--dia-previsto dd/mm/aaaa` — força a data da entrada prevista (o padrão é o
  dia seguinte ao último dia do relatório, já tratando virada de mês).
- `--b2b 1177.80` — valor do B2B da iKI, quando a base existir.
- `--a-prazo outro.csv` — outra tabela de recebíveis (padrão: `vendas_a_prazo.csv`).
- `--entrada forcar.json` — sobrescreve na mão qualquer parcela:
  `{"vendas": 0, "voucher": 0, "a_prazo": 0, "b2b": 0}`

## Regras que ela já definiu (não perguntar de novo)

1. **Descartar** as colunas `QTDE. CLIENTES` e `TICKET MÉDIO`. A tabela final
   tem só **FORMA DE PAGAMENTO · TOTAL · % DO TOTAL**.
2. **Agrupar mantendo o nome do primeiro da dupla:**
   - `TEF - DEBITO` + `CARTAO DEBITO` → **TEF - DEBITO**
   - `TEF - CREDITO` + `CARTAO CREDITO` → **TEF - CREDITO**
   - `VOUCHER IFOOD (DESCONTO)` + `IFOOD` → **VOUCHER IFOOD (DESCONTO)**
3. **Deixar separados:** `VOUCHER`, `TEF - VOUCHER` e `TEF - TICKET`. Ela
   desfez esse agrupamento de propósito — não juntar de novo.
4. Ordenar o quadrinho **do maior para o menor percentual**, com linha `Total`
   no pé.
5. Valores em **padrão brasileiro** (`R$ 1.089.716,13`).
6. **Não usar o nome da loja do cabeçalho do PDF.** O PDF vem com "ROBS", mas
   isso é erro do relatório — o valor é de **todas as filiais**. O subtítulo do
   quadrinho é sempre `Vendas de <período> · Todas as filiais`.

As regras 2 e 3 vivem no dicionário `GRUPOS` no topo de `gerar_relatorio.py`.
Mudança de agrupamento se faz lá, não na mão na resposta.

## Entrada prevista — como cada parcela é calculada

| Parcela | De onde sai |
|---|---|
| **Cartão (D+1)** | `TEF - CREDITO` + `TEF - DEBITO` do período atual, **já agrupados** (ou seja, com CARTAO CREDITO e CARTAO DEBITO dentro), **líquidos de taxa**. |
| **Pix (D+0)** | o Pix do **próprio dia previsto**, não o do relatório: a madrugada já vendida (número real) mais a **estimativa** do resto do dia, pela mediana do mesmo dia da semana em `historico_pix.csv`. |
| **Voucher D+30** | soma de `VOUCHER` + `TEF - VOUCHER` + `TEF - TICKET` do PDF de `--mes-anterior`. Voucher liquida em 30 dias, então o previsto de hoje é a venda de voucher de um mês atrás. |
| **Repasse do iFood** | **valor informado na mão** em `--ifood-valor`, já líquido, por entidade (Grupo Ragga, Dell Iris). Cai na quarta, referente à semana segunda a domingo anterior. |
| **Vendas a prazo** | `vendas_a_prazo.csv`, os títulos cujo `VENCIMENTO` é o **dia anterior** à data prevista: é boleto, compensa em **D+1** (vence 20/09 → entra na previsão de 21/09). Fora disso a parcela não entra. |
| **B2B iKI** | ainda **sem base**. Entra só quando vier `--b2b`. |
| **Depois da meia-noite** | o que foi vendido depois do corte **sai** da previsão de amanhã e fica gravado em `pos_meia_noite.csv` para entrar sozinho na do dia seguinte. Valor informado em `--pos-meia-noite`. |

### O Pix cai no mesmo dia (D+0)

**O Pix não é D+1.** Ela confirmou em 23/09: o Pix da maquininha liquida no
mesmo dia da venda, e por isso a previsão estava saindo alta. Em 22/09 o texto
previu R$ 18.029,16 de Pix (o Pix vendido em 21/09) e caíram R$ 10.300,08 —
porque o Pix de 21/09 já tinha caído em 21/09.

Consequência: a previsão de hoje precisa do Pix de **hoje**, que de manhã ainda
não foi vendido. Ela sai de duas partes:

| Parte | De onde |
|---|---|
| **madrugada** | o que foi vendido depois da meia-noite no relatório de ontem — já é hoje no calendário, é número **real** |
| **resto do dia** | **estimativa**: mediana do mesmo dia da semana nas últimas `PIX_AMOSTRAS` (4) semanas, em `historico_pix.csv` |

O script **grava o histórico sozinho** a cada rodada (`DATA;DIURNO;MADRUGADA;TOTAL`,
com `DIURNO` = o Pix do dia fora a madrugada). Sem mesmo-dia-da-semana
suficiente ele cai para a mediana dos últimos 7 dias e **avisa no console**.

O mesmo dia da semana repete muito bem — medido entre agosto e setembro:
quarta 15.099,81 × 15.275,55 (1,2%), quinta 19.932,16 × 19.996,37 (0,3%),
segunda 16.137,65 × 16.898,14 (4,7%), sexta 24.210,28 × 22.923,79 (5,3%). O
sábado foi o pior (29.845,30 × 23.485,08, 21%).

Flags: `--pix-hoje VALOR` força a estimativa, `--sem-pix` tira a parcela,
`--historico outro.csv` aponta para outro arquivo.

> **A madrugada do Pix não é arrasto de D+1.** No `pos_meia_noite.csv` a linha
> de `PIX MAQUININHA` entra no **dia seguinte à origem, no calendário** (Pix
> cai em fim de semana também), enquanto crédito e débito continuam indo para
> o próximo dia útil + 1.

> **Fica em aberto: o dia do Pix parece fechar por volta das 23h.** Em 22/09
> caíram R$ 10.300,08 contra R$ 8.655,58 de Pix vendidos no dia de calendário.
> A diferença bate com o Pix de 21/09 vendido depois das 23h (o melhor ajuste
> deu 22h58, erro de R$ 138). **É uma amostra só** — conferir conforme ela for
> passando o recebido de cada dia, e só então mexer.

`PAGAMENTO ONLINE` **é o iFood** e fica fora da parcela diária de cartão + Pix
porque tem repasse próprio, semanal. Isso confere com o modelo dela: no print
de 27/08 o previsto (R$ 101.481,14) bate com crédito + débito + Pix
(R$ 102.999,18) e não com nada que inclua o pagamento online.

### O corte da meia-noite

**O Cloudfy não vira o dia.** Ela confirmou em 17/09: a venda feita depois da
meia-noite continua gravada na data do dia anterior, o relatório não corta às
02h nem em hora nenhuma. Para a **venda** isso está certo — é a mesma noite de
operação, e o quadrinho tem que sair assim. Para o **recebimento** não: a
adquirente carimba a transação pela data do calendário, então o cartão passado
00h30 liquida junto com o dia seguinte.

Então esse pedaço **sai da previsão de amanhã e entra na de depois de amanhã**.
O jeito certo de fazer isso é com o relatório de cupons, que traz a hora:

```bash
python3 gerar_relatorio.py 16-09.pdf --mes-anterior 16-08.pdf \
    --cupons Relatriodecuponsdevendas_*.xlsx --saida saida
```

`--cupons` lê o `Relatriodecuponsdevendas_*.xlsx` do Cloudfy (aba `Planilha`,
cabeçalho na linha 1: `Filial · Caixa · Data · Cupom · Hora · Itens · Chave ·
CPF/CNPJ · Nome do cliente · Desc. pagam. · Nr. parc · Vl. pagamento`), agrupa
as formas pelas mesmas regras de `GRUPOS` e separa sozinho o que foi vendido
**da meia-noite até `HORA_ABERTURA` (05h)**. Ele também **confere o total
contra o PDF** e avisa se divergir.

> **O relatório de cupons bate exatamente com o PDF.** Medido em 16/09/2026:
> R$ 175.023,83 nos dois, e forma a forma idêntico (17 filiais, 4.454 cupons).
> É a mesma base, só que aberta — então dá para pedir esse arquivo junto com o
> PDF e o corte sai sem ninguém digitar nada.

Medido em 16/09: R$ 3.866,81 de cartão + Pix depois da meia-noite (crédito
R$ 1.652,52, débito R$ 1.250,16, Pix R$ 964,13), de um total de R$ 11.385,50
vendidos na madrugada — o resto é pagamento online, dinheiro, a prazo e
voucher, que não entram nessa parcela.

Sem o xlsx, dá para informar na mão:

```bash
python3 gerar_relatorio.py 15-09.pdf --mes-anterior 15-08.pdf \
    --pos-meia-noite "credito=1200" --pos-meia-noite "debito=900" \
    --pos-meia-noite "pix=400" --saida saida
```

- `--pos-meia-noite` aceita `[FORMA=]VALOR` e pode repetir. As formas são
  `credito`, `debito` e `pix` (também aceita o nome completo). **Sem forma, o
  valor é rateado** entre as três na proporção do próprio dia.
- O valor é subtraído da parcela de cartão + Pix **e gravado** em
  `pos_meia_noite.csv` (`DATA DE ENTRADA;FORMA;VALOR;ORIGEM;CORTE`), com data
  de entrada = dia previsto + 1.
- No dia seguinte o script **lê esse arquivo sozinho** e a parcela entra como
  linha própria, já líquida de taxa, no console e no texto.
- Rodar o mesmo dia duas vezes **não dobra**: as linhas daquela origem são
  regravadas.
- `--corte HH:MM` só muda o rótulo (padrão `00:00`); `--sem-arrasto` ignora o
  que está guardado; `--arrasto outro.csv` aponta para outro arquivo.

> **O PDF de vendas por forma de pagamento não tem hora** — por isso o
> `--cupons`. Sem `--cupons` e sem `--pos-meia-noite` nada é separado, e o
> script **avisa** que a previsão saiu com tudo e que nada foi guardado para o
> dia seguinte.

### A regra do iFood

O fechamento do iFood é de **segunda a domingo**, e isso abre **duas** datas em
que a parcela entra:

| Dia previsto | O que é | Entra no total? | De onde |
|---|---|---|---|
| **Segunda** | **prévia**: a semana fechou domingo, então o valor já dá para calcular | **NÃO** — sai num bloco à parte do texto | faturado do Cloudfy (`--ifood`) com as taxas |
| **Quarta** | o repasse **entra de verdade** | **SIM**, é parcela do total | valor na mão (`--ifood-valor`), já líquido |

**A regra que resolve tudo: a semana fecha no domingo e o dinheiro entra na
quarta.** Segunda é só quando já dá para saber o número — não é entrada de
segunda. Por isso a prévia fica **fora do total do dia** e vai no texto como
bloco separado (`🛵 REPASSE DO IFOOD — ENTRA QUARTA dd/mm`). Somar a prévia no
total de segunda contaria o mesmo dinheiro duas vezes, já que segunda 14/09 e
quarta 16/09 apontam ambas para a semana 07/09 a 13/09.

Nos outros dias da semana não há janela, e os PDFs de `--ifood` são ignorados
com aviso.

### O relatório de pedidos do iFood (fonte certa da prévia)

A Hylary exporta toda segunda o `relatorio-pedidos_*.xlsx` do iFood, cobrindo
a semana seg–dom. **Ele traz o `VALOR LIQUIDO (R$)` pronto, por pedido** — é a
fonte da prévia de segunda, muito melhor que estimar taxa sobre o Cloudfy.

Regra de limpeza: **descartar só os `CANCELADO`**. Manter `CONCLUIDO`,
`CANCELAMENTO PARCIAL` e `CONFIRMED`.

Identidade validada em 96,3% das linhas:

```
VALOR LIQUIDO = VALOR DOS ITENS − INCENTIVO PROMOCIONAL DA LOJA + TAXAS E COMISSOES
```

#### A estrutura de taxa — o que o arquivo permite afirmar

> **NÃO tentar decompor `TAXAS E COMISSOES` em comissão / transação /
> antecipação.** O arquivo traz **um número agregado por pedido** e não abre a
> composição. Uma tentativa anterior chegou a "10,600% × itens + taxa fixa"
> com erro de R$ 0,004, mas isso era **circular**: o ajuste foi feito num
> grupo selecionado por esse mesmo resíduo. Ajustando por loja, o percentual
> varia de **9,46% a 13,61%** com erro de ~R$ 1 por pedido — ou seja, a
> fórmula não se sustenta.

O que **é** medível, e basta para o relatório:

| Recorte | Taxa efetiva sobre os itens | Taxa média por pedido |
|---|---:|---:|
| ENTREGA (14.035 pedidos) | **20,41%** | R$ 9,41 |
| PARA RETIRAR (239 pedidos) | **12,10%** | R$ 6,27 |

**A taxa é fortemente regressiva** — quanto menor o pedido, maior a mordida:

| Itens do pedido | Taxa efetiva | Taxa por pedido |
|---|---:|---:|
| até R$ 25 | 30,27% | R$ 6,54 |
| R$ 25 a 40 | 24,31% | R$ 7,87 |
| R$ 40 a 60 | 19,85% | R$ 9,72 |
| R$ 60 a 100 | 16,97% | R$ 12,79 |
| acima de R$ 100 | 14,54% | R$ 19,60 |

A taxa por pedido sobe bem mais devagar que o valor do pedido, o que confirma
que existe **um componente fixo por pedido** — mas o tamanho exato dele não sai
deste arquivo.

#### O desconto real é ~40%, não 12%

Semana 07–13/09, pedidos liquidados:

| | | % dos itens |
|---|---:|---:|
| Valor dos itens | R$ 659.012,79 | 100% |
| − Incentivo promocional da **loja** | −R$ 110.321,83 | 16,74% |
| − Comissão + transação | −R$ 69.855,36 | 10,60% |
| − Taxa fixa por pedido | −R$ 63.648,41 | 9,66% |
| **= Valor líquido** | **R$ 397.039,13** | **60,25%** |

O incentivo promocional da loja é desconto que o Grupo banca, não taxa, mas
sai do líquido igual — e é a maior das deduções.

> **A antecipação de 1,59% não está no relatório.** O `VALOR LIQUIDO` é
> anterior a ela. Aplicar sempre no fim, sobre o total da semana.

> **Cuidado: o último dia da semana costuma vir incompleto.** Em 07–13/09,
> **803 dos 1.603 pedidos de domingo** estavam com taxa e líquido zerados (não
> liquidados). Os outros seis dias vieram completos. **Sempre conferir quantas
> linhas têm `VALOR LIQUIDO = 0` e em que dia caem**; se houver, estimar o que
> falta pela razão líquido/itens dos liquidados e avisar no chat.

#### Como montar a prévia a partir do relatório

1. Descartar só os `CANCELADO`.
2. Somar `VALOR LIQUIDO (R$)` dos pedidos liquidados.
3. Estimar as linhas com líquido zerado (o último dia costuma vir assim),
   aplicando aos itens delas a razão líquido ÷ itens dos já liquidados.
4. **Aplicar 1,59% de antecipação sobre o total.** O relatório de pedidos
   **não traz a antecipação** — ela incide depois, sobre o líquido, na média.

> **REGRA DURA: o número do iFood SEMPRE sai com a antecipação aplicada.**
> Nunca mandar o líquido cru do relatório de pedidos, nem na prévia de segunda
> nem no repasse de quarta, e nunca perguntar se aplica — ela já parametrizou
> isso. Em 14/09 a prévia foi mandada com R$ 422.999,70 (sem a antecipação) e a
> diretoria ficou esperando R$ 422 mil de um repasse de R$ 416.274,00.
>
> Para não depender de ninguém lembrar, passar o número do relatório em
> **`--ifood-liquido`**, que aplica os 1,59% sozinho e mostra a memória de
> cálculo. O `--ifood-valor` continua existindo para o **valor final**, já com
> tudo aplicado — e agora avisa no console quando é usado sozinho.
>
> ```bash
> python3 gerar_relatorio.py 15-09.pdf --mes-anterior 15-08.pdf \
>     --ifood-liquido "Semana 07 a 13/09=422999.70" --saida saida
> #   422.999,70 - 1,59% = 416.274,00
> ```

Feito em 07–13/09:

| | |
|---|---:|
| Liquidados | R$ 397.039,13 |
| + domingo estimado | R$ 25.960,57 |
| = líquido do relatório | R$ 422.999,70 |
| − antecipação 1,59% | −R$ 6.725,70 |
| **= previsão de recebimento** | **R$ 416.274,00** |

Faturamento da semana (`VALOR DOS ITENS`, sem cancelados): R$ 700.841,32.

No texto isso vai como bloco próprio, via `--ifood-valor` (a previsão já
líquida) e `--ifood-faturado` (o bruto, só para exibir):

```bash
python3 gerar_relatorio.py 11-13-09.pdf --mes-anterior 11-13-08.pdf \
    --ifood-valor "Previsao=422239.80" --ifood-faturado 700841.32 --saida saida
```

#### Cloudfy × relatório de pedidos

`PAGAMENTO ONLINE` do Cloudfy espelha **`VALOR DOS ITENS − INCENTIVO DA LOJA`**
do iFood — não o valor líquido, e não o valor dos itens puro.

A virada de dia é às **02h**, não à meia-noite: agrupar os pedidos por
`DATA E HORA DO PEDIDO − 2h` reduz o erro diário de R$ 3.877 para R$ 2.861.

Semana 07–13/09: Cloudfy R$ 555.505,94 × iFood R$ 579.344,26 → Cloudfy fica
**4,1% abaixo** (R$ 23.838,32), dos quais R$ 2.855,21 são pedidos com
`CANCELAMENTO PARCIAL`. Sobram ~3,6% sem explicação, que encolhem ao longo da
semana (−5,9% na segunda, −0,9% no domingo) — tem cara de atraso de
lançamento, não de perda.

**A Dell'iris está nas duas fontes e não tem relatório próprio.** É uma *dark
kitchen* dentro das lojas físicas: no iFood ela aparece como 4 lojas próprias
(988 pedidos, R$ 32.559,78 na semana), e no Cloudfy o faturamento dela sai
embutido no da loja que a hospeda. Não existe e não adianta pedir um relatório
de vendas separado dela.

> **Por que a estimativa por taxa dava errado:** aplicar 12,02% sobre o
> faturado do Cloudfy deu R$ 488.726,02 para 07–13/09, contra um líquido real
> de ~R$ 422 mil. **Erro de R$ 66 mil.** Por isso a prévia de segunda passa a
> sair do `VALOR LIQUIDO` do relatório de pedidos, não de taxa sobre o Cloudfy.

**O valor NÃO sai do Cloudfy.** O `PAGAMENTO ONLINE` do relatório é a *venda*,
não o *repasse* — medido em 09/09, a diferença foi de **24,72%**, muito acima
da taxa. Ela passa o valor na mão:

```bash
python3 gerar_relatorio.py 08-09.pdf --mes-anterior 08-08.pdf \
    --ifood-valor "Grupo Ragga=401827.58" --ifood-valor "Dell Iris=22224.02" \
    --saida saida
```

- `--ifood-valor` aceita `[ROTULO=]VALOR`, pode repetir e soma tudo. O rótulo
  aparece na abertura do console. Aceita `401827.58` e `401.827,58`.
- **O valor informado assim JÁ É LÍQUIDO — nunca aplicar taxa em cima.**
  Aplicar os 12,02% de novo tiraria uns R$ 51 mil de um repasse de R$ 424 mil.
- Chega **por entidade**: Grupo Ragga e Dell Iris são CNPJs diferentes e vêm
  em valores separados. Passar cada um com seu rótulo.
- **A Dell Iris é só iFood.** Ela não tem cartão, voucher nem venda a prazo
  para entrar no previsto — o relatório do Cloudfy (CNPJ 52.934.334/0001-36)
  cobre tudo o que não é iFood. Não procurar venda da Dell Iris.
- Se a data prevista é quarta e o valor não veio, o script avisa e diz a janela
  — aí é pedir o valor antes de mandar o texto.

`--ifood <pdf>` continua existindo como **estimativa** a partir do Cloudfy (aí
sim com a taxa de 12,02%), mas `--ifood-valor` tem precedência e o script avisa
quando os dois vêm juntos. Para o número que vai para a diretoria, usar sempre
o valor informado.

### As taxas (entrada prevista LÍQUIDA)

A entrada prevista sai **líquida de taxa**, como estimativa. As taxas vivem em
`TAXAS` e `TAXA_IFOOD` no topo de `gerar_relatorio.py` — mudança de taxa se faz
lá:

| Forma | Taxa |
|---|---:|
| Crédito (`TEF - CREDITO`) | 2,63% |
| Débito (`TEF - DEBITO`) | 0,99% |
| Pix maquininha | 0% |
| Voucher | **6,90%** — a maior das operadoras |
| iFood (`PAGAMENTO ONLINE`) | **25,064% efetivos** (medido) — só na estimativa por `--ifood`; o valor de `--ifood-valor` já vem líquido |

Regras de uso:

- **Não descrever as taxas no texto do WhatsApp.** Ela pediu explicitamente:
  o texto mostra só o valor líquido. A abertura bruto → taxa → líquido sai no
  console, e vale reportar no chat.
- São **estimativas**, não a taxa real de cada transação. A taxa real sai do
  EDI — isso é a skill `ragga-conciliacao`.
- **A taxa do iFood é 25,064%, MEDIDA — não é a soma das taxas de tabela.**
  Está em `IFOOD_DESCONTO_EFETIVO`. Veio de cruzar o relatório de pedidos com
  o Cloudfy na semana 07–13/09:

  | | |
  |---|---:|
  | base Cloudfy (`PAGAMENTO ONLINE`) | R$ 555.505,94 |
  | recebido do iFood (já líquido) | R$ 416.274,00 |
  | **desconto efetivo** | **25,064%** |

  Os 12,02% de tabela (8% + 2,60% + 1,59%) erravam em **R$ 72.451,79** nessa
  semana, porque ignoravam a taxa fixa por pedido, o incentivo promocional
  bancado pela loja e os pedidos pagos em vale.

  > **Amostra de uma semana só.** Recalibrar conforme os pares faturado ×
  > recebido forem acumulando. A `IFOOD_ANTECIPACAO` (1,59%) continua separada
  > porque é aplicada à parte sobre o líquido do relatório de pedidos — ela já
  > está dentro dos 25,064%.
- **Voucher: 6,90%**, em `TAXA_VOUCHER`. É a **maior taxa** que o Grupo tem
  hoje entre as operadoras de vale (Alelo, Pluxee, Ticket, Fepas) — escolha
  conservadora dela, para o previsto não sair otimista. A taxa cobre as três
  formas de `FORMAS_VOUCHER`: `VOUCHER`, `TEF - VOUCHER` e `TEF - TICKET`.
  Substituiu os 5% fictícios que valiam antes. Se um dia a média real por
  operadora for levantada, é trocar uma linha — **não perguntar a cada envio**.
- **Venda a prazo e B2B saem brutos** — são boleto, sem adquirente no meio.
- `--bruto` desliga tudo e devolve a entrada prevista no bruto, para comparar.

#### Validação contra o Sicredi (semana 08–14/09/2026)

Ela exporta o `vendas_<loja>_<data>.zip` do portal — **17 lojas**, um `.xlsx` por
loja, layout consolidado (crédito, débito, PIX e voucher no mesmo arquivo).
Cabeçalho na **linha 13**, achar pela célula `Data da venda`. **`openpyxl` não
abre** esses arquivos: usar `python-calamine`. Manter só `Aprovada` e
`Autorizada`.

Colunas que importam: `Produto`, `Bandeira`, `Status`, `Valor Bruto`,
`Valor da taxa (MDR)`, `Valor líquido`.

**As duas fontes batem — o Cloudfy é confiável:**

| Forma | Cloudfy | Sicredi bruto | Cloudfy/Sicredi |
|---|---:|---:|---:|
| Crédito | R$ 306.163,49 | R$ 307.014,01 | 99,72% |
| Débito | R$ 280.437,22 | R$ 279.031,72 | 100,50% |
| PIX | R$ 140.256,22 | R$ 140.648,89 | 99,72% |
| Voucher | R$ 47.064,03 | R$ 49.593,68 | 94,90% |
| **TOTAL** | **R$ 773.920,96** | **R$ 776.288,30** | **99,70%** |

**As taxas medidas confirmam a parametrização:**

| Forma | MDR medido | Parametrizado | Leitura |
|---|---:|---:|---|
| Débito | **1,00%** | 0,99% | confirmado |
| PIX | **0,00%** | 0% | confirmado |
| Crédito | **1,11%** | 2,63% | 2,63% = MDR + antecipação |
| Voucher | 0,05% | 6,90% | a taxa do vale **não está** neste arquivo |

O crédito **não está errado**: o MDR puro é 1,11%, e os 2,63% embutem a
antecipação automática (sem ela o crédito seria D+30). A antecipação implícita
é **1,52%**, coerente com os **1,6424%** medidos na conciliação em 14/08.

> **Falta o relatório de antecipação** para cravar a taxa da semana em vez de
> inferir. É um dos 4 relatórios do portal e não veio neste zip.

A taxa de voucher de 6,90% é cobrada **pela operadora do vale** (Alelo, Pluxee,
Ticket), fora do Sicredi — por isso aparece como 0,05% aqui.

Confere com o modelo dela: aquele print de 27/08 saiu 1,47% abaixo da soma
bruta, que era justamente o desconto de taxa.

O texto do WhatsApp só mostra as parcelas que têm número; o que está faltando
sai como aviso no console, para não mandar `[PREENCHER]` para a diretoria.
**Sempre avisar no chat o que ficou de fora.**

## vendas_a_prazo.csv

Tabela de recebíveis B2B a prazo (BGs, Casaria etc.) que ela manda de vez em
quando. Formato: `RAZAO SOCIAL;CNPJ;VALOR;VENCIMENTO;ORIGEM DO CONSUMO`, com
valor em padrão BR e vencimento `dd/mm/aaaa`.

Estado atual: **26 títulos, R$ 53.102,69**, assim distribuídos:

| Vencimento | Títulos | Valor |
|---|---:|---:|
| 14/09/2026 | 22 | R$ 38.482,02 |
| 20/09/2026 | 3 | R$ 12.748,67 |
| 28/09/2026 | 1 | R$ 1.872,00 |

Quando ela mandar títulos novos, acrescentar linhas no arquivo e commitar.

**O que entra e o que não entra** quando ela manda a planilha do B2B:

- entra o que está **A RECEBER com data futura** — é caixa que ainda vai cair;
- **não entra permuta** (HELP DESK, ALISON CECOTTI): é troca, não é dinheiro;
- **não entra linha zerada** (consumo de colaboradores antes do fechamento,
  cliente sem consumo no mês);
- **não entra o que já está RECEBIDO**, e o que está **VENCIDO ou A RECEBER com
  data passada fica de fora** até ela dar uma data nova — a parcela só entra no
  dia exato do vencimento, então uma data velha nunca mais apareceria.

**É boleto, então compensa em D+1 do pagamento** — e **vencimento em fim de
semana só é pago no próximo dia útil**. Ela confirmou isso em 21/09, com os
títulos que venceram no domingo 20/09: os clientes pagam na segunda e o
dinheiro cai na terça, então a parcela foi para 22/09 e não para 21/09.

A conta é `próximo dia útil do vencimento + A_PRAZO_COMPENSACAO`, pulando o
fim de semana de novo no fim — está em `entrada_do_boleto()`, e o intervalo
vive em `A_PRAZO_COMPENSACAO`, no topo de `gerar_relatorio.py`.

Cuidado para **não contar em dobro**: a venda a prazo já entrou na venda bruta
no dia da venda; o que entra aqui é o **caixa** na compensação. São coisas
diferentes, e é por isso que `VENDA A PRAZO` não está em `CARTAO_E_PIX`.

## Conferências que o script já faz

- A soma antes e depois do agrupamento tem de ser idêntica (erro se divergir).
- Avisa se alguma forma de `GRUPOS` não apareceu no PDF do dia.
- Imprime o total de cada dia para bater com o rodapé do PDF.
- Avisa quando o período do mês anterior tem número de dias diferente do atual
  (aí o voucher D+30 sai desproporcional).
- Mostra os vencimentos da tabela, com a data em que cada um entra (D+1),
  quando nenhum boleto compensa na data prevista.

Se o PDF vier sem nenhum dia reconhecido, o layout do Cloud Commerce mudou —
conferir `ROW_RE` e `DAY_RE`.

## Ambiente

- `pdfplumber` para ler o PDF. Se der `ModuleNotFoundError: _cffi_backend`,
  rodar `pip install --force-reinstall cffi`.
- Chromium para o PNG (usa `/opt/pw-browsers/chromium-1194/chrome-linux/chrome`
  ou o que estiver no PATH; dá para apontar com `CHROME_PATH`). Sem Chromium o
  script salva `vendas_card.html` em vez do PNG.
- `pillow` (opcional) para recortar a sobra branca do print.

# Envio 2 — entradas do dia (recebimento real)

Quando ela passar os valores que entraram:

```bash
python3 gerar_entradas.py --data 04/09/2026 --previsao 110000 \
    --pix 24739.28 --debito 44730.61 --credito 46217.25 \
    --voucher 6730.53 --b2b 1045.86 --saida saida
```

Ou com `--dados recebimentos.json`:

```json
{
  "data": "04/09/2026",
  "previsao": 110000.00,
  "recebido": {"PIX": 24739.28, "Débito": 44730.61, "Crédito": 46217.25,
               "Voucher": 6730.53, "B2B": 1045.86},
  "total_informado": 128115.36
}
```

Formas disponíveis, na ordem em que saem no texto: `--pix`, `--debito`,
`--credito`, `--voucher`, `--b2b`, `--dinheiro`, `--online`. Só as que forem
passadas aparecem na mensagem.

## Regras do envio 2

1. **`--previsao` é a previsão que foi mandada para aquele dia** no envio 1 —
   não recalcular por outro caminho. Sem ela o script para: comparar
   recebimento com uma previsão inventada é pior do que não mandar nada.
2. **O `VALOR RECEBIDO` é sempre a soma das formas.** Nunca digitar um total à
   parte. Se ela informar um total, passar em `--total-informado`: o script
   confere e avisa se não fechar, mas o texto sai com a soma.
3. O tom muda sozinho conforme o resultado: acima da previsão sai `✅` +
   `🟢 ... ACIMA` + 🚀 no resumo; abaixo sai `⚠️` + `🔴 ... ABAIXO` e um resumo
   sem comemoração; empate sai `⚪ EM LINHA COM A PREVISÃO`.
4. **Sempre reportar no chat** a diferença entre previsto e recebido, e por
   forma quando der, para ela ver de onde veio o desvio.

## Sobre o exemplo de 04/09

Os valores daquele modelo **não são reais** — ela confirmou que era só para
mostrar o formato. Por isso a soma das formas (R$ 123.463,53) não fechava com
o total do texto (R$ 128.115,36). Não é para caçar essa diferença.

A trava do `--total-informado` continua valendo para os envios de verdade: se
a soma não fechar com o total que ela passar, avisar antes de mandar.

# Retiradas para depósito (sangria)

Ela exporta o `Relatriodesangriassuprimentos_*.xlsx` do PDV quando precisa
casar o dinheiro depositado com o que a loja sangrou. Abre com `openpyxl`,
aba `Planilha`, cabeçalho na linha 1:
`Filial · Caixa · Data · Valor · Motivo/Descrição · Usuário · Usuário autorizador`.

**Ela quer SÓ o consolidado por loja.** Não mandar o detalhe lançamento a
lançamento nem a quebra por dia, a não ser que peça. Formato:

| Loja | Retiradas | Valor | % |

## Como classificar

O campo é texto livre e vem escrito de vários jeitos, com erro de digitação.
A regra que funciona:

1. **Entra**: a descrição contém `depósito`/`deposito` **e não** contém
   suprimento. Aparece como `RETIRADA DEPOSITO`, `RETIRADA DEPOSITO R$450,00.`,
   `Retirada deposito no valor de R$900,00. Autorizado pelo gerente Gabriel.`
2. **Entra também**: a descrição é exatamente `RETIRADA`, sem destino — ela
   decidiu em 15/09 que esses contam como depósito.
3. **Fica de fora** todo o resto.

> **A armadilha: "retirada" sozinha quase nunca é depósito.** A maioria são
> `RETIRADA PARA SUPRIMENTO DO CAIXA`, dinheiro passando de um caixa para
> outro, que nunca sai da loja. Filtrar por "retirada" na semana 07–14/09
> contaria R$ 15.240,00 de transferência interna como depósito.

Grafias de suprimento já vistas, todas no mesmo relatório: `SUPRIMENTO`,
`SUPLIMENTO`, `SUPPRIMENTO`, `SUUPRIMENTO`, `suplimento`. O casamento por
`supr|supl|suppr|suup` pega todas.

Outras categorias que aparecem e ficam de fora: pagamento a freelancer,
compra/despesa (gelo, arroz, café, pit stop), reembolso e estorno a cliente,
pagamento de entregador por fora quando a TAON está sem limite.

## A descrição manda — e vai furar às vezes

**Classificar sempre pela descrição, e só por ela.** A descrição erra em alguns
casos: em 13/09 a BIGGS 13 registrou `RETIRADA SUPRIMENTO CAIXA E DELIVERY
DIURNO` (R$ 2.350,00) e era depósito — o operador ia suprir o caixa, não
precisou, e depositou.

Isso é **normal e esperado**, e a Hylary já decidiu como lidar: **ela acha
esses casos quando o valor cai no extrato.** Consequências para mim:

- **não propor lista de "suspeitos"** nem pedir confirmação de lançamentos que
  a descrição classifica como suprimento — ela não quer esse ruído;
- **não tentar adivinhar** por valor alto ou por padrão de caixa;
- quando ela apontar um furo, **incluir aquele lançamento** e seguir.

## O painel

O de:para virou painel, em **https://retiradas-deposito.vercel.app** (código em
`hylaryfarias/retiradas-deposito`, arquivo `index.html`).

- **Cada semana é uma aba**, com os próprios arquivos, observações e situação.
  Nada é compartilhado entre abas; o upload vai para a aba que estiver aberta.
- **O nome da aba define o período**: `07/09 a 13/09` corta da sangria o que
  for de fora. O extrato **não** é filtrado por data, porque o depósito cai
  depois — às vezes na semana seguinte.
- **Fonte 3 · Suprimentos** é o export do PDV filtrado em suprimento. Ele
  entra **na mesma lista da sangria**, com um selo `suprimento` na linha, para
  a pesquisa varrer os dois de uma vez. Vem **tudo desmarcado**: nada dali
  conta no quadro. Marcar uma linha é o jeito de corrigir o furo da descrição
  — aquele lançamento passa a contar como depósito da loja. É o caso da
  BIGGS 13 de 13/09.
- Um escreve, o time lê: quem tem o token publica; quem abre o link só olha.

## Conciliação

Pergunta sobre **por que** o dinheiro entra assim (taxas, prazos, EDI, vales,
Sicredi/Fiserv) não é este relatório — usar a skill `ragga-conciliacao`.
