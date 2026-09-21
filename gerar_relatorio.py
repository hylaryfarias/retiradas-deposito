#!/usr/bin/env python3
"""Gera o quadrinho de vendas por forma de pagamento + o texto do WhatsApp.

Entrada : o PDF "Vendas por forma de pagamento - por dia" do Cloud Commerce.
Saidas  : vendas_card.png, texto_whatsapp.txt e formas_agrupadas.csv.

Uso:
    python3 gerar_relatorio.py relatorio.pdf
    python3 gerar_relatorio.py relatorio.pdf --dia 04/09/2026
    python3 gerar_relatorio.py relatorio.pdf --entrada entrada.json
"""

import argparse
import csv as csvmod
import datetime
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from collections import OrderedDict

# ---------------------------------------------------------------------------
# Regras de agrupamento pedidas pela Hylary. A chave e o nome que fica na
# linha final (o nome do primeiro da dupla); os valores sao as formas que
# entram nela. Para desfazer um agrupamento, apague a linha correspondente.
# ---------------------------------------------------------------------------
GRUPOS = OrderedDict([
    ('TEF - DEBITO',             ['TEF - DEBITO', 'CARTAO DEBITO']),
    ('TEF - CREDITO',            ['TEF - CREDITO', 'CARTAO CREDITO']),
    ('VOUCHER IFOOD (DESCONTO)', ['VOUCHER IFOOD (DESCONTO)', 'IFOOD']),
])

# VOUCHER, TEF - VOUCHER e TEF - TICKET ficam separados de proposito.

# ---------------------------------------------------------------------------
# Entrada prevista. Nomes JA AGRUPADOS (portanto 'TEF - CREDITO' ja carrega
# CARTAO CREDITO dentro dele).
#
# Cartao + Pix: o que liquida rapido e entra na previsao do proximo dia.
# PAGAMENTO ONLINE fica fora daqui porque tem repasse proprio -- ver IFOOD.
CARTAO_E_PIX = ['TEF - CREDITO', 'TEF - DEBITO', 'PIX MAQUININHA']

# como cada forma aparece no texto do WhatsApp: ela pediu o previsto aberto,
# uma linha por forma, em vez de um valor unico de cartao + pix
ROTULO_TEXTO = {
    'TEF - CREDITO':  'crédito',
    'TEF - DEBITO':   'débito',
    'PIX MAQUININHA': 'Pix',
}

# ---------------------------------------------------------------------------
# Corte da meia-noite.
#
# O relatorio do Cloudfy fecha o dia as 02h: o que foi vendido depois da
# meia-noite entra no dia anterior. Para a VENDA isso esta certo -- e a mesma
# noite de operacao. Para o RECEBIMENTO nao: a adquirente carimba a transacao
# pela data do calendario, entao o cartao passado 00h30 liquida junto com o dia
# seguinte. Esse pedaco nao entra na previsao de amanha; entra na de depois.
#
# Entao o valor depois do corte sai da previsao do dia e fica GRAVADO em
# pos_meia_noite.csv, para entrar sozinho na previsao do dia seguinte.
#
# O PDF de vendas por forma de pagamento NAO tem hora: o valor depois do corte
# vem informado em --pos-meia-noite.
HORA_CORTE = '00:00'
# O Cloudfy NAO vira o dia: a venda feita depois da meia-noite continua
# gravada na data do dia anterior. Entao tudo o que tem hora antes da
# abertura das lojas e madrugada -- venda do dia seguinte no calendario.
HORA_ABERTURA = 5
POS_MEIA_NOITE_PADRAO = 'pos_meia_noite.csv'

# apelidos aceitos em --pos-meia-noite, para nao ter que digitar o nome exato
APELIDOS_FORMA = {
    'credito': 'TEF - CREDITO', 'credito ': 'TEF - CREDITO',
    'cartao credito': 'TEF - CREDITO', 'tef - credito': 'TEF - CREDITO',
    'debito': 'TEF - DEBITO', 'cartao debito': 'TEF - DEBITO',
    'tef - debito': 'TEF - DEBITO',
    'pix': 'PIX MAQUININHA', 'pix maquininha': 'PIX MAQUININHA',
}

# PAGAMENTO ONLINE e o iFood. O repasse cai na QUARTA, referente a semana
# fechada de segunda a domingo anterior (quarta 09/09 -> 31/08 a 06/09). Entao
# so entra na previsao quando o dia previsto e uma quarta-feira.
# O recebimento do iFood NAO da para tirar do Cloudfy: o PAGAMENTO ONLINE de
# lá é a venda, não o repasse, e a diferença medida foi de 24,72% (bem mais que
# a taxa). Então o valor vem NA MAO, em --ifood-valor, e chega por entidade
# (Grupo Ragga, Dell Iris). Valor informado assim JA E LIQUIDO: nao aplicar
# taxa de novo. A janela seg-dom e a regra da quarta continuam valendo para
# dizer a que semana o repasse se refere.
IFOOD_FORMA = 'PAGAMENTO ONLINE'

# datetime.date.weekday(): segunda=0 ... domingo=6
SEGUNDA, QUARTA = 0, 2

# A semana do iFood fecha no DOMINGO e o repasse cai na QUARTA. Logo:
#   - na SEGUNDA ja da para CALCULAR o valor (a semana fechou ontem), mas ele
#     NAO e entrada de segunda: e uma PREVIA do que entra na quarta. Vai no
#     texto como bloco separado, FORA do total do dia;
#   - na QUARTA o dinheiro entra de verdade e vira parcela do total, com o
#     valor real informado em --ifood-valor.
# Contar a previa de segunda dentro do total do dia contaria o mesmo dinheiro
# duas vezes -- por isso ela fica de fora da soma.

# ---------------------------------------------------------------------------
# Taxas para estimar o LIQUIDO da entrada prevista. Sao estimativas, nao a
# taxa real de cada transacao -- a taxa real sai do EDI (skill ragga-conciliacao).
# Aplicadas sobre o bruto de cada forma. Para mudar uma taxa, e aqui.
# ---------------------------------------------------------------------------
TAXAS = {
    'TEF - CREDITO': 0.0263,   # 2,63%
    'TEF - DEBITO': 0.0099,    # 0,99%
    'PIX MAQUININHA': 0.0000,  # sem taxa
}

# iFood: taxa EFETIVA MEDIDA sobre o faturado do Cloudfy (PAGAMENTO ONLINE).
#
# Nao e a soma das taxas de tabela. Medida na semana 07-13/09/2026, cruzando o
# relatorio de pedidos do iFood com o Cloudfy:
#     base Cloudfy (PAGAMENTO ONLINE)  R$ 555.505,94
#     recebido do iFood (ja liquido)   R$ 416.274,00
#     -> desconto efetivo              25,064%
#
# Os 12,02% de tabela (8% + 2,60% + 1,59%) erravam em R$ 72.451,79 nessa semana,
# porque ignoravam a taxa fixa por pedido, o incentivo promocional bancado pela
# loja e os pedidos pagos em vale.
#
# AMOSTRA DE UMA SEMANA SO. Recalibrar conforme os pares forem acumulando.
IFOOD_DESCONTO_EFETIVO = 0.25064

# Antecipacao, usada a parte: o relatorio de pedidos entrega o liquido ANTES
# dela, entao ela incide sobre aquele total. Ja esta dentro do efetivo acima.
IFOOD_ANTECIPACAO = 0.0159


def liquido_ifood(bruto):
    """Estimativa do repasse a partir do faturado do Cloudfy."""
    return bruto * (1 - IFOOD_DESCONTO_EFETIVO)


def taxa_efetiva_ifood():
    """Desconto efetivo, para exibir."""
    return IFOOD_DESCONTO_EFETIVO

# Vale-refeicao (Alelo, Pluxee, Ticket, Fepas): 6,90%. E a MAIOR taxa que o
# Grupo tem hoje entre as operadoras -- escolha conservadora, para o previsto
# nao sair otimista. Se a media real por operadora for levantada, trocar aqui.
TAXA_VOUCHER = 0.069

# Venda a prazo e B2B entram BRUTOS: sao boleto, sem adquirente no meio.

# Voucher: liquida em D+30, entao o previsto de hoje sai das vendas de voucher
# do mesmo periodo do mes anterior (--mes-anterior).
FORMAS_VOUCHER = ['VOUCHER', 'TEF - VOUCHER', 'TEF - TICKET']

# Venda a prazo (B2B das BGs, Casaria etc.): tabela de recebiveis com data de
# vencimento em vendas_a_prazo.csv. O titulo NAO entra no dia da venda -- essa ja
# foi na venda bruta -- e tambem nao entra no dia do vencimento: e BOLETO, que
# compensa em D+1. Entao o titulo entra na previsao do DIA SEGUINTE ao vencimento
# (vence 20/09 -> entra na previsao de 21/09).
A_PRAZO_COMPENSACAO = 1   # dias entre o vencimento do boleto e o credito
A_PRAZO_PADRAO = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                              'vendas_a_prazo.csv')

ROW_RE = re.compile(r'^(.+?)\s+R\$\s*([\d\.]+,\d{2})\s+([\d\.]+,?\d*)\s+R\$\s*([\d\.]+,\d{2})$')
DAY_RE = re.compile(r'^Data:\s*(\d{2}/\d{2}/\d{4})')
CNPJ_RE = re.compile(r'^\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}$')

CHROME_CANDIDATES = [
    os.environ.get('CHROME_PATH', ''),
    '/opt/pw-browsers/chromium-1194/chrome-linux/chrome',
    '/opt/pw-browsers/chromium/chrome-linux/chrome',
]


def brl(valor, casas=2):
    """1234.5 -> '1.234,50' (padrao brasileiro)."""
    return f"{valor:,.{casas}f}".replace(',', 'X').replace('.', ',').replace('X', '.')


def to_float(texto):
    """'1.234,50' -> 1234.5"""
    return float(texto.replace('.', '').replace(',', '.'))


def achar_chrome():
    for caminho in CHROME_CANDIDATES:
        if caminho and os.path.isfile(caminho):
            return caminho
    for nome in ('chromium', 'chromium-browser', 'google-chrome', 'chrome'):
        caminho = shutil.which(nome)
        if caminho:
            return caminho
    return None


def ler_pdf(caminho):
    """Devolve (dias, cnpj). dias = {'04/09/2026': {forma: total}}.

    O nome da loja no cabecalho do PDF ("ROBS") e erro do relatorio: o valor e
    de todas as filiais. Por isso nao e lido nem usado no quadrinho.
    """
    import pdfplumber

    linhas = []
    with pdfplumber.open(caminho) as pdf:
        for pagina in pdf.pages:
            linhas.extend((pagina.extract_text() or '').splitlines())

    dias, dia_atual, cnpj = OrderedDict(), None, ''
    for linha in linhas:
        linha = linha.strip()
        if not cnpj and CNPJ_RE.match(linha):
            cnpj = linha
        achou_dia = DAY_RE.match(linha)
        if achou_dia:
            dia_atual = achou_dia.group(1)
            dias.setdefault(dia_atual, OrderedDict())
            continue
        achou_linha = ROW_RE.match(linha)
        if achou_linha and dia_atual:
            forma = achou_linha.group(1).strip()
            # a coluna 2 e o TOTAL; qtde. clientes e ticket medio sao descartados
            valor = to_float(achou_linha.group(2))
            dias[dia_atual][forma] = dias[dia_atual].get(forma, 0.0) + valor
    return dias, cnpj


def ler_ifood_manual(entradas):
    """Le os --ifood-valor no formato "[ROTULO=]VALOR". Valores JA LIQUIDOS."""
    itens = []
    for bruto in entradas:
        rotulo, _, texto = bruto.rpartition('=')
        texto = texto.strip()
        try:
            valor = to_float(texto) if ',' in texto else float(texto)
        except ValueError:
            raise SystemExit(f'ERRO: valor invalido em --ifood-valor: {bruto!r}')
        itens.append((rotulo.strip() or 'repasse', valor))
    return itens


def janela_ifood(dia_previsto):
    """Semana de referencia do repasse do iFood para uma data prevista.

    Devolve (segunda, domingo) como date na SEGUNDA (estimativa do faturado
    que acabou de fechar) e na QUARTA (dia em que o repasse cai). Nos demais
    dias devolve None. Segunda e a quarta seguinte apontam para a mesma semana.
    """
    data = datetime.datetime.strptime(dia_previsto, '%d/%m/%Y').date()
    if data.weekday() == SEGUNDA:      # semana fechou ontem
        domingo = data - datetime.timedelta(days=1)
    elif data.weekday() == QUARTA:     # dia do repasse
        domingo = data - datetime.timedelta(days=3)
    else:
        return None
    return domingo - datetime.timedelta(days=6), domingo


def somar_ifood(pdfs, janela):
    """Soma PAGAMENTO ONLINE dos dias dentro da janela. Devolve (total, faltando)."""
    esperados = [janela[0] + datetime.timedelta(days=n) for n in range(7)]
    por_dia = {}
    for caminho in pdfs:
        dias, _ = ler_pdf(caminho)
        for texto_dia, formas in dias.items():
            data = datetime.datetime.strptime(texto_dia, '%d/%m/%Y').date()
            if janela[0] <= data <= janela[1]:
                por_dia[data] = formas.get(IFOOD_FORMA, 0.0)
            else:
                print(f'AVISO: {texto_dia} esta fora da janela do iFood '
                      f'({janela[0]:%d/%m} a {janela[1]:%d/%m}) e foi ignorado.',
                      file=sys.stderr)
    faltando = [d for d in esperados if d not in por_dia]
    return sum(por_dia.values()), faltando


def ler_a_prazo(caminho):
    """Le a tabela de vendas a prazo. Devolve [] se o arquivo nao existir."""
    if not caminho or not os.path.isfile(caminho):
        return []
    titulos = []
    with open(caminho, newline='', encoding='utf-8') as arquivo:
        for numero, linha in enumerate(csvmod.DictReader(arquivo, delimiter=';'), start=2):
            valor = (linha.get('VALOR') or '').strip()
            vencimento = (linha.get('VENCIMENTO') or '').strip()
            if not valor or not vencimento:
                continue
            try:
                titulos.append({
                    'razao': (linha.get('RAZAO SOCIAL') or '').strip(),
                    'valor': to_float(valor),
                    'vencimento': vencimento,
                    'origem': (linha.get('ORIGEM DO CONSUMO') or '').strip(),
                })
            except ValueError:
                print(f'AVISO: valor invalido na linha {numero} de {caminho}: {valor!r}',
                      file=sys.stderr)
    return titulos


def agrupar(dias, rotulo='PDF do periodo'):
    """Consolida os dias num bloco unico e aplica GRUPOS. Valida a soma."""
    membro_para_grupo = {m: destino for destino, ms in GRUPOS.items() for m in ms}
    bruto, agrupado, composicao = OrderedDict(), OrderedDict(), OrderedDict()

    for formas in dias.values():
        for forma, valor in formas.items():
            bruto[forma] = bruto.get(forma, 0.0) + valor
            destino = membro_para_grupo.get(forma, forma)
            agrupado[destino] = agrupado.get(destino, 0.0) + valor
            composicao.setdefault(destino, OrderedDict())
            composicao[destino][forma] = composicao[destino].get(forma, 0.0) + valor

    # trava de seguranca: agrupar nao pode criar nem perder dinheiro
    if abs(sum(bruto.values()) - sum(agrupado.values())) > 0.005:
        raise SystemExit('ERRO: a soma mudou depois do agrupamento.')

    ignorados = [m for ms in GRUPOS.values() for m in ms if m not in bruto]
    if ignorados:
        print(f'AVISO: {rotulo}: formas de GRUPOS que nao aparecem nele: '
              f'{", ".join(ignorados)}', file=sys.stderr)

    return agrupado, composicao


def montar_html(linhas, total, subtitulo):
    corpo = '\n'.join(
        f'      <tr><td class="f">{forma}</td>'
        f'<td class="v">R$ {brl(valor)}</td>'
        f'<td class="p">{brl(valor / total * 100)}%</td></tr>'
        for forma, valor in linhas
    )
    return f"""<meta charset="utf-8">
<style>
  * {{ box-sizing: border-box; }}
  body {{ margin: 0; padding: 18px; background: #ffffff;
          font-family: "Segoe UI", Calibri, Arial, Helvetica, sans-serif; }}
  table {{ border-collapse: collapse; width: 620px; }}
  caption {{ background: #E4DDF6; border: 1px solid #8B76C4; border-bottom: none;
             padding: 7px 10px 8px; }}
  .t1 {{ font-size: 16px; font-weight: 700; color: #2B2140; }}
  .t2 {{ font-size: 12px; color: #6B5E8A; margin-top: 2px; }}
  th {{ background: #EDE8F9; border: 1px solid #8B76C4; color: #2B2140;
        font-size: 12.5px; font-weight: 700; padding: 6px 10px; line-height: 1.25;
        vertical-align: bottom; }}
  th.c1 {{ text-align: left; }}
  th.c2 {{ text-align: right; width: 165px; }}
  th.c3 {{ text-align: right; width: 120px; }}
  td {{ border: 1px solid #8B76C4; font-size: 13.5px; color: #1B1B1B; padding: 5px 10px; }}
  td.f {{ text-align: left; }}
  td.v, td.p {{ text-align: right; font-variant-numeric: tabular-nums; }}
  tbody tr:nth-child(even) td {{ background: #FAF8FE; }}
  tfoot td {{ background: #EDE8F9; font-weight: 700; font-size: 14px; }}
</style>
<table>
  <caption>
    <div class="t1">Composi&ccedil;&atilde;o da venda &mdash; por forma de pagamento</div>
    <div class="t2">{subtitulo}</div>
  </caption>
  <thead>
    <tr>
      <th class="c1">Forma de Pagamento</th>
      <th class="c2">Composi&ccedil;&atilde;o de Venda</th>
      <th class="c3">% Venda por<br>Forma de Pag.</th>
    </tr>
  </thead>
  <tbody>
{corpo}
  </tbody>
  <tfoot>
    <tr><td class="f">Total</td><td class="v">R$ {brl(total)}</td><td class="p">100,00%</td></tr>
  </tfoot>
</table>
"""


def renderizar_png(html, destino):
    chrome = achar_chrome()
    if not chrome:
        print('AVISO: Chromium nao encontrado; gerei so o .html.', file=sys.stderr)
        return False

    with tempfile.TemporaryDirectory() as tmp:
        pagina = os.path.join(tmp, 'card.html')
        with open(pagina, 'w') as arquivo:
            arquivo.write(html)
        subprocess.run(
            [chrome, '--headless', '--no-sandbox', '--disable-gpu', '--hide-scrollbars',
             '--force-device-scale-factor=2', '--window-size=660,900',
             f'--screenshot={destino}', f'file://{pagina}'],
            check=True, capture_output=True,
        )

    try:  # recorta a sobra branca para o print sair justo
        from PIL import Image, ImageChops
        imagem = Image.open(destino).convert('RGB')
        caixa = ImageChops.difference(imagem, Image.new('RGB', imagem.size, (255, 255, 255))).getbbox()
        if caixa:
            pad, (esq, topo, dir_, baixo) = 32, caixa
            imagem.crop((max(0, esq - pad), max(0, topo - pad),
                         min(imagem.width, dir_ + pad),
                         min(imagem.height, baixo + pad))).save(destino)
    except ImportError:
        pass
    return True


PARCELAS = ('vendas', 'pos_meia_noite', 'voucher', 'ifood', 'a_prazo', 'b2b')


def normaliza_forma(texto):
    """Aceita 'credito', 'Cartao Debito', 'PIX' e devolve o nome ja agrupado."""
    limpo = ' '.join(texto.strip().lower().split())
    limpo = (limpo.replace('é', 'e').replace('É', 'e')
                  .replace('ó', 'o').replace('í', 'i').replace('á', 'a'))
    if limpo in APELIDOS_FORMA:
        return APELIDOS_FORMA[limpo]
    for forma in CARTAO_E_PIX:
        if limpo == forma.lower():
            return forma
    raise SystemExit(f'ERRO: forma "{texto}" nao vale em --pos-meia-noite. '
                     f'Use credito, debito ou pix.')


def ler_pos_meia_noite_args(entradas, agrupado):
    """--pos-meia-noite [FORMA=]VALOR -> {forma: valor}.

    Sem forma, o valor e rateado entre credito, debito e pix na proporcao do
    proprio dia -- e o melhor palpite quando so se sabe o total do periodo.
    """
    porforma, solto = {}, 0.0
    for bruto in entradas:
        rotulo, _, valor = bruto.rpartition('=')
        try:   # aceita 1.652,52 e 1652.52
            numero = to_float(valor) if ',' in valor else float(valor)
        except Exception:
            raise SystemExit(f'ERRO: nao entendi o valor em --pos-meia-noite {bruto!r}.')
        if rotulo.strip():
            forma = normaliza_forma(rotulo)
            porforma[forma] = porforma.get(forma, 0.0) + numero
        else:
            solto += numero

    if solto:
        base = sum(agrupado.get(f, 0.0) for f in CARTAO_E_PIX)
        if base <= 0:
            raise SystemExit('ERRO: sem cartao e pix no dia para ratear o '
                             '--pos-meia-noite sem forma.')
        for forma in CARTAO_E_PIX:
            peso = agrupado.get(forma, 0.0) / base
            if peso:
                porforma[forma] = porforma.get(forma, 0.0) + solto * peso

    for forma, valor in porforma.items():
        if valor > agrupado.get(forma, 0.0) + 0.005:
            raise SystemExit(f'ERRO: --pos-meia-noite de {forma} (R$ {brl(valor)}) '
                             f'e maior que a venda do dia (R$ {brl(agrupado.get(forma, 0.0))}).')
    return porforma


def ler_cupons(caminho):
    """Le o Relatriodecuponsdevendas_*.xlsx: cupom a cupom, com hora e forma.

    Devolve (dias, madrugada, total_geral):

    dias      -> {dd/mm/aaaa: {forma CRUA: valor}}, no mesmo formato que
                 ler_pdf() entrega, para passar pelo mesmo agrupar()
    madrugada -> {forma JA AGRUPADA: valor} do que foi vendido da meia-noite
                 ate HORA_ABERTURA: ja e o dia seguinte no calendario e
                 liquida com ele
    total     -> soma de tudo, para conferir com o PDF quando os dois vierem
    """
    try:
        import openpyxl
    except ImportError:
        raise SystemExit('ERRO: ler cupons precisa do openpyxl (pip install openpyxl).')

    wb = openpyxl.load_workbook(caminho, read_only=True, data_only=True)
    ws = wb[wb.sheetnames[0]]
    try:                      # alguns exports vem sem a dimensao declarada
        ws.reset_dimensions()
    except AttributeError:
        pass
    linhas = ws.iter_rows(values_only=True)
    cab = [str(c or '').strip().lower() for c in next(linhas)]

    def coluna(*nomes):
        for i, titulo in enumerate(cab):
            if any(titulo.startswith(n) for n in nomes):
                return i
        raise SystemExit(f'ERRO: coluna {nomes[0]!r} nao achada em {caminho}. '
                         f'Cabecalho: {", ".join(cab)}')

    cD, cH = coluna('data'), coluna('hora')
    cF, cV = coluna('desc. pagam', 'forma'), coluna('vl. pagamento', 'valor')

    dias, madrugadas, total = OrderedDict(), OrderedDict(), 0.0
    for linha in linhas:
        if not linha or linha[cV] is None:
            continue
        valor = float(linha[cV] or 0)
        forma = str(linha[cF] or '').strip().upper()
        bruto = linha[cD]
        dia = (bruto.strftime('%d/%m/%Y') if hasattr(bruto, 'strftime')
               else str(bruto).strip())
        formas = dias.setdefault(dia, OrderedDict())
        formas[forma] = formas.get(forma, 0.0) + valor
        total += valor

        hora = str(linha[cH] or '00:00:00')[:2]
        if hora.isdigit() and int(hora) < HORA_ABERTURA:
            agrupada = forma
            for destino, membros in GRUPOS.items():
                if forma in membros:
                    agrupada = destino
                    break
            doDia = madrugadas.setdefault(dia, OrderedDict())
            doDia[agrupada] = doDia.get(agrupada, 0.0) + valor

    def chave(d):
        try:
            return datetime.datetime.strptime(d, '%d/%m/%Y')
        except ValueError:
            return datetime.datetime.min
    dias = OrderedDict(sorted(dias.items(), key=lambda i: chave(i[0])))
    # num bloco de varios dias, so a madrugada do ultimo dia fica para o dia
    # seguinte: as do meio do periodo liquidam dentro do proprio bloco
    ultimo = list(dias)[-1] if dias else None
    return dias, madrugadas.get(ultimo, OrderedDict()), total


def ler_fonte(caminho):
    """Le o dia a dia do PDF ou do xlsx de cupons, o que vier."""
    if caminho.lower().endswith(('.xlsx', '.xls')):
        dias, madrugada, _total = ler_cupons(caminho)
        return dias, None, madrugada
    dias, cnpj = ler_pdf(caminho)
    return dias, cnpj, None


def proximo_util(data):
    """Sabado e domingo nao tem credito: joga para a segunda."""
    while data.weekday() >= 5:
        data += datetime.timedelta(days=1)
    return data


def ler_arrasto(caminho):
    """Le o arquivo de vendas depois do corte que ficaram para o dia seguinte."""
    if not os.path.exists(caminho):
        return []
    registros = []
    with open(caminho, encoding='utf-8') as arquivo:
        for numero, linha in enumerate(arquivo, 1):
            linha = linha.strip()
            if not linha or linha.upper().startswith('DATA DE ENTRADA'):
                continue
            partes = linha.split(';')
            if len(partes) < 4:
                print(f'AVISO: linha {numero} de {caminho} ignorada: {linha!r}',
                      file=sys.stderr)
                continue
            registros.append({'entrada': partes[0].strip(), 'forma': partes[1].strip(),
                              'valor': to_float(partes[2]), 'origem': partes[3].strip(),
                              'corte': partes[4].strip() if len(partes) > 4 else HORA_CORTE})
    return registros


def gravar_arrasto(caminho, registros, origem, porforma, entrada_em, corte):
    """Regrava o arquivo trocando as linhas desta origem -- rodar duas vezes
    o mesmo dia nao pode dobrar o valor."""
    mantidos = [r for r in registros if r['origem'] != origem]
    novos = [{'entrada': entrada_em, 'forma': forma, 'valor': valor,
              'origem': origem, 'corte': corte}
             for forma, valor in porforma.items() if valor]
    todos = mantidos + novos
    todos.sort(key=lambda r: (datetime.datetime.strptime(r['entrada'], '%d/%m/%Y'),
                              r['forma']))
    with open(caminho, 'w', encoding='utf-8') as arquivo:
        arquivo.write('DATA DE ENTRADA;FORMA;VALOR;ORIGEM;CORTE\n')
        for r in todos:
            arquivo.write(f'{r["entrada"]};{r["forma"]};{brl(r["valor"])};'
                          f'{r["origem"]};{r["corte"]}\n')
    return novos


def calcular_entrada(agrupado, agrupado_anterior, titulos, dia_previsto,
                     ifood=None, b2b=None, override=None, liquido=True,
                     ifood_manual=None, ifood_entra=True, arrasto=None):
    """Monta as parcelas da entrada prevista.

    vendas   -> credito + debito + pix do periodo atual (venda bruta)
    voucher  -> voucher do mesmo periodo do mes anterior (D+30)
    ifood    -> repasse do iFood, so quando a data prevista e QUARTA

    Com liquido=True (padrao) cartao, voucher e a estimativa de iFood saem
    liquidos das taxas. Venda a prazo e B2B saem brutos (boleto).
    a_prazo  -> boletos que venceram no dia anterior (compensam em D+1)
    b2b      -> iKI Produtos Alimenticios; None enquanto nao houver base
    """
    # boleto compensa em D+1: o que entra hoje venceu ontem
    venc_alvo = (datetime.datetime.strptime(dia_previsto, '%d/%m/%Y').date()
                 - datetime.timedelta(days=A_PRAZO_COMPENSACAO)).strftime('%d/%m/%Y')
    vencendo = [t for t in titulos if t['vencimento'] == venc_alvo]

    # detalhe por forma, para poder auditar bruto -> taxa -> liquido
    detalhe = []
    for forma in CARTAO_E_PIX:
        bruto = agrupado.get(forma, 0.0)
        taxa = TAXAS.get(forma, 0.0) if liquido else 0.0
        detalhe.append((forma, bruto, taxa, bruto * (1 - taxa)))

    # valor informado na mao ja vem liquido: taxa zero, sem bruto de referencia
    if ifood_manual:
        taxa_ifood, ifood_bruto = 0.0, None
        ifood_valor = sum(valor for _, valor in ifood_manual)
    else:
        taxa_ifood, ifood_bruto = (taxa_efetiva_ifood() if liquido else 0.0), ifood
        ifood_valor = None if ifood is None else (liquido_ifood(ifood) if liquido else ifood)
    # arrasto: vendas depois do corte da meia-noite do dia anterior, que
    # liquidam junto com hoje
    detalhe_arrasto = []
    for forma, bruto in (arrasto or []):
        taxa = TAXAS.get(forma, 0.0) if liquido else 0.0
        detalhe_arrasto.append((forma, bruto, taxa, bruto * (1 - taxa)))

    entrada = {
        'vendas': sum(item[3] for item in detalhe),
        'detalhe_vendas': detalhe,
        'pos_meia_noite': (sum(item[3] for item in detalhe_arrasto)
                           if detalhe_arrasto else None),
        'detalhe_arrasto': detalhe_arrasto,
        'ifood_bruto': ifood_bruto,
        'taxa_ifood': taxa_ifood,
        'ifood_manual': ifood_manual or [],
        'voucher': (sum(agrupado_anterior.get(f, 0.0) for f in FORMAS_VOUCHER)
                    * (1 - (TAXA_VOUCHER if liquido else 0.0))
                    if agrupado_anterior is not None else None),
        'taxa_voucher': TAXA_VOUCHER if liquido else 0.0,
        'ifood': ifood_valor,
        'a_prazo': sum(t['valor'] for t in vencendo) if vencendo else None,
        'b2b': b2b,
        'titulos_a_prazo': vencendo,
        'vencimento_a_prazo': venc_alvo,
    }
    if override:
        entrada.update({k: v for k, v in override.items() if k in PARCELAS})
    # Na segunda o iFood e so previa do que cai na quarta: sai do total.
    if not ifood_entra:
        entrada['ifood_previa'] = entrada['ifood']
        entrada['ifood'] = None
    else:
        entrada['ifood_previa'] = None

    entrada['total'] = sum(entrada[p] for p in PARCELAS if entrada[p] is not None)
    return entrada


def montar_texto(dias_usados, total, entrada, dia_previsto):
    """Texto pronto para colar no WhatsApp.

    So entram no texto as parcelas que tem numero. O que falta sai no console,
    para nao mandar "[PREENCHER]" para a diretoria.
    """
    primeiro, ultimo = dias_usados[0], dias_usados[-1]

    if primeiro == ultimo:
        cabecalho = f'📊 *VENDA BRUTA DO DIA | {primeiro[:5]}*'
        referencia = 'do dia'
    else:
        cabecalho = f'📊 *VENDA BRUTA | {primeiro[:5]} a {ultimo[:5]}*'
        referencia = 'do período'

    partes = [cabecalho, '', f'R$ {brl(total)}', '',
              f'💰 *ENTRADA PREVISTA PRO DIA {dia_previsto[:5]}*', '',
              f'*R$ {brl(entrada["total"])}*', '']

    # a madrugada do dia anterior entra somada a forma dela: em linha separada
    # confunde quem le na ponta. A memoria de calculo fica no console.
    por_forma = OrderedDict()
    for forma, _bruto, _taxa, liq in entrada['detalhe_vendas']:
        por_forma[forma] = por_forma.get(forma, 0.0) + liq
    for forma, _bruto, _taxa, liq in entrada.get('detalhe_arrasto') or []:
        por_forma[forma] = por_forma.get(forma, 0.0) + liq
    for forma, liq in por_forma.items():
        if not liq:
            continue
        rotulo = ROTULO_TEXTO.get(forma, forma.title())
        partes.append(f'· R$ {brl(liq)} de {rotulo} {referencia};')

    if entrada['voucher'] is not None:
        partes.append(f'· R$ {brl(entrada["voucher"])} de recebimento de períodos '
                      f'anteriores (Voucher D+30);')

    if entrada['ifood'] is not None:
        janela = entrada['janela_ifood']
        referencia = (f', referente a {janela[0]:%d/%m} a {janela[1]:%d/%m}'
                      if janela else '')
        partes.append(f'· R$ {brl(entrada["ifood"])} de repasse do iFood'
                      f'{referencia};')

    if entrada['a_prazo'] is not None:
        quantos = len(entrada['titulos_a_prazo'])
        venc = entrada.get('vencimento_a_prazo', dia_previsto)
        partes.append(f'· R$ {brl(entrada["a_prazo"])} de vendas a prazo com '
                      f'vencimento em {venc[:5]} ({quantos} títulos);')

    if entrada['b2b'] is not None:
        partes.append(f'· R$ {brl(entrada["b2b"])} referente a iKI Produtos '
                      f'Alimentícios – B2B.')

    partes[-1] = partes[-1].rstrip(';') + '.'  # a ultima linha fecha com ponto

    # A previa do iFood fica FORA do total: o dinheiro so entra na quarta.
    if entrada.get('ifood_previa') is not None:
        janela = entrada['janela_ifood']
        partes += ['', f'🛵 *IFOOD — SEMANA {janela[0]:%d/%m} A {janela[1]:%d/%m}*', '']
        if entrada.get('ifood_faturado'):
            partes.append(f'· Faturamento: R$ {brl(entrada["ifood_faturado"])}')
        partes += [f'· Previsão de recebimento: *R$ {brl(entrada["ifood_previa"])}*',
                   f'· Entra na quarta, {entrada["data_repasse"]:%d/%m}.']

    return '\n'.join(partes) + '\n'


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('pdf', metavar='ARQUIVO',
                        help='PDF de vendas por forma de pagamento ou o xlsx '
                             'de cupons (do xlsx sai tambem o corte da madrugada)')
    parser.add_argument('--dia', help='usar so este dia (dd/mm/aaaa); padrao: todos somados')
    parser.add_argument('--saida', default='.', help='pasta de saida (padrao: atual)')
    parser.add_argument('--mes-anterior', dest='mes_anterior',
                        help='PDF do MESMO periodo do mes anterior, para o voucher D+30')
    parser.add_argument('--ifood', action='append', default=[], metavar='PDF',
                        help='PDF(s) cobrindo a semana seg-dom do repasse do iFood; '
                             'pode repetir a flag. So vale quando a data prevista e quarta')
    parser.add_argument('--ifood-valor', dest='ifood_valores', action='append',
                        default=[], metavar='[ROTULO=]VALOR',
                        help='repasse do iFood JA LIQUIDO, informado na mao; pode repetir '
                             '(ex.: --ifood-valor "Grupo Ragga=401827.58"). Tem precedencia '
                             'sobre --ifood')
    parser.add_argument('--ifood-liquido', dest='ifood_liquido', action='append',
                        default=[], metavar='[ROTULO=]VALOR',
                        help='liquido do relatorio de pedidos, ANTES da antecipacao: '
                             'o script aplica os 1,59% sozinho. Use este em vez de '
                             '--ifood-valor quando o numero vier do relatorio.')
    parser.add_argument('--ifood-faturado', dest='ifood_faturado', type=float,
                        help='faturamento bruto da semana do iFood, para mostrar junto da previa')
    parser.add_argument('--b2b', type=float, help='valor do B2B da iKI, quando houver base')
    parser.add_argument('--a-prazo', dest='a_prazo', default=A_PRAZO_PADRAO,
                        help='CSV de vendas a prazo (padrao: vendas_a_prazo.csv do projeto)')
    parser.add_argument('--dia-previsto', dest='dia_previsto',
                        help='data da entrada prevista (dd/mm/aaaa); padrao: dia seguinte')
    parser.add_argument('--bruto', action='store_true',
                        help='nao aplicar taxas: entrada prevista no bruto')
    parser.add_argument('--entrada', help='JSON para forcar vendas, voucher, a_prazo ou b2b')
    parser.add_argument('--pos-meia-noite', dest='pos_meia_noite', action='append',
                        default=[], metavar='[FORMA=]VALOR',
                        help='venda feita depois do corte (entra na previsao do dia '
                             'seguinte, nao na de amanha). Aceita credito=, debito=, '
                             'pix= ou so o total, que e rateado. Pode repetir.')
    parser.add_argument('--cupons', metavar='XLSX',
                        help='Relatriodecuponsdevendas_*.xlsx do Cloudfy: o corte '
                             'da meia-noite sai dele, sem informar valor na mao')
    parser.add_argument('--corte', default=HORA_CORTE, metavar='HH:MM',
                        help=f'horario do corte (padrao: {HORA_CORTE})')
    parser.add_argument('--arrasto', default=POS_MEIA_NOITE_PADRAO, metavar='CSV',
                        help=f'arquivo do arrasto (padrao: {POS_MEIA_NOITE_PADRAO})')
    parser.add_argument('--sem-arrasto', dest='sem_arrasto', action='store_true',
                        help='ignora o que ficou gravado de ontem')
    args = parser.parse_args()

    dias, cnpj, madrugada_fonte = ler_fonte(args.pdf)
    if not dias:
        raise SystemExit(f'ERRO: nenhum dia encontrado em {args.pdf}. O layout mudou?')

    if args.dia:
        if args.dia not in dias:
            raise SystemExit(f'ERRO: {args.dia} nao esta no PDF. '
                             f'Dias disponiveis: {", ".join(dias)}')
        dias = OrderedDict([(args.dia, dias[args.dia])])

    agrupado, composicao = agrupar(dias)
    total = sum(agrupado.values())
    linhas = sorted(agrupado.items(), key=lambda item: -item[1])  # maior -> menor
    dias_usados = list(dias)

    periodo = (f'{dias_usados[0]}' if len(dias_usados) == 1
               else f'{dias_usados[0][:5]} a {dias_usados[-1]}')
    subtitulo = f'Vendas de {periodo} &middot; Todas as filiais'

    os.makedirs(args.saida, exist_ok=True)
    png = os.path.join(args.saida, 'vendas_card.png')
    html = montar_html(linhas, total, subtitulo)
    if not renderizar_png(html, png):
        with open(os.path.join(args.saida, 'vendas_card.html'), 'w') as arquivo:
            arquivo.write(html)

    agrupado_anterior = None
    if args.mes_anterior:
        # o mes anterior pode vir como PDF ou como o xlsx de cupons -- os dois
        # trazem a mesma coisa, e dela so sai o voucher D+30
        dias_ant, _cnpj_ant, _mad_ant = ler_fonte(args.mes_anterior)
        if not dias_ant:
            raise SystemExit(f'ERRO: nenhum dia em {args.mes_anterior}.')
        agrupado_anterior, _ = agrupar(dias_ant, 'fonte do mes anterior')
        dias_ant_usados = list(dias_ant)
        if len(dias_ant_usados) != len(dias_usados):
            print(f'AVISO: o periodo atual tem {len(dias_usados)} dia(s) e o do mes '
                  f'anterior {len(dias_ant_usados)}. O voucher D+30 fica desproporcional.',
                  file=sys.stderr)

    if args.dia_previsto:
        dia_previsto = args.dia_previsto
    else:  # dia seguinte ao ultimo do relatorio, respeitando virada de mes
        ultimo = datetime.datetime.strptime(dias_usados[-1], '%d/%m/%Y').date()
        dia_previsto = (ultimo + datetime.timedelta(days=1)).strftime('%d/%m/%Y')

    janela = janela_ifood(dia_previsto)
    ifood_manual = ler_ifood_manual(args.ifood_valores)
    # o relatorio de pedidos nao traz a antecipacao: aplicar SEMPRE, aqui, para
    # nao depender de ninguem lembrar na hora do envio
    antecipado = []
    for rotulo, valor in ler_ifood_manual(args.ifood_liquido):
        final = valor * (1 - IFOOD_ANTECIPACAO)
        antecipado.append((rotulo, valor, final))
        ifood_manual.append((f'{rotulo} (-1,59% antecip.)', final))
    ifood, ifood_faltando = None, []
    if args.ifood_valores and not args.ifood_liquido:
        print('AVISO: --ifood-valor entra como valor FINAL. Se esse numero saiu do '
              'relatorio de pedidos, ele ainda nao tem a antecipacao de 1,59% -- '
              'use --ifood-liquido para o script aplicar.', file=sys.stderr)

    if ifood_manual and args.ifood:
        print('AVISO: --ifood-valor tem precedencia; os PDFs de --ifood foram ignorados.',
              file=sys.stderr)
    elif ifood_manual:
        pass
    elif args.ifood and janela is None:
        print(f'AVISO: {dia_previsto} nao e segunda nem quarta, entao nao ha semana '
              f'de iFood fechada. Os PDFs de --ifood foram ignorados.', file=sys.stderr)
    elif args.ifood:
        ifood, ifood_faltando = somar_ifood(args.ifood, janela)
        if ifood_faltando:
            print(f'AVISO: faltam dias na janela do iFood '
                  f'({janela[0]:%d/%m} a {janela[1]:%d/%m}): '
                  f'{", ".join(f"{d:%d/%m}" for d in ifood_faltando)}. '
                  f'O repasse esta SUBESTIMADO.', file=sys.stderr)
    elif janela is not None:
        dia_semana = datetime.datetime.strptime(dia_previsto, '%d/%m/%Y').date().weekday()
        if dia_semana == SEGUNDA:
            print(f'AVISO: {dia_previsto} e segunda: a semana do iFood '
                  f'({janela[0]:%d/%m} a {janela[1]:%d/%m}) fechou ontem. Passe os PDFs '
                  f'em --ifood para estimar o faturado com taxa.', file=sys.stderr)
        else:
            print(f'AVISO: {dia_previsto} e quarta: o repasse do iFood '
                  f'({janela[0]:%d/%m} a {janela[1]:%d/%m}) cai hoje. Informe o valor '
                  f'real em --ifood-valor.', file=sys.stderr)

    titulos = ler_a_prazo(args.a_prazo)
    override = json.load(open(args.entrada)) if args.entrada else None
    data_prevista = datetime.datetime.strptime(dia_previsto, '%d/%m/%Y').date()

    # --- corte da meia-noite -------------------------------------------------
    # o que passou depois do corte sai da previsao de amanha e fica gravado
    # para entrar na de depois de amanha
    agrupado_previsao = dict(agrupado)
    registros = ler_arrasto(args.arrasto)
    gravados = []
    if args.cupons:
        _dias_c, madrugada_fonte, geral = ler_cupons(args.cupons)
        if abs(geral - total) > 0.01:
            print(f'AVISO: o relatorio de cupons soma R$ {brl(geral)} e o PDF '
                  f'R$ {brl(total)} (diferenca de R$ {brl(geral - total)}). '
                  f'Sao do mesmo periodo?', file=sys.stderr)
        else:
            print(f'Cupons conferem com o PDF: R$ {brl(geral)}')

    # a madrugada sai do xlsx, seja ele a fonte principal ou o --cupons
    if madrugada_fonte and not args.pos_meia_noite:
        for forma in CARTAO_E_PIX:
            valor = madrugada_fonte.get(forma, 0.0)
            if valor:
                args.pos_meia_noite.append(f'{forma}={valor:.2f}')

    if args.pos_meia_noite:
        porforma = ler_pos_meia_noite_args(args.pos_meia_noite, agrupado)
        for forma, valor in porforma.items():
            agrupado_previsao[forma] = agrupado_previsao.get(forma, 0.0) - valor
        entra_em = proximo_util(data_prevista
                                + datetime.timedelta(days=1)).strftime('%d/%m/%Y')
        gravados = gravar_arrasto(args.arrasto, registros, dias_usados[-1],
                                  porforma, entra_em, args.corte)
        registros = ler_arrasto(args.arrasto)
    else:
        print('AVISO: nada em --pos-meia-noite. A previsao esta com TUDO o que o '
              'relatorio traz, inclusive a venda feita depois da meia-noite, e nada '
              'foi guardado para a previsao do dia seguinte.', file=sys.stderr)

    arrasto, origem_arrasto = [], ''
    if not args.sem_arrasto:
        dearrastar = [r for r in registros if r['entrada'] == dia_previsto]
        porforma_hoje = OrderedDict()
        for r in dearrastar:
            porforma_hoje[r['forma']] = porforma_hoje.get(r['forma'], 0.0) + r['valor']
            origem_arrasto = r['origem']
        arrasto = [(forma, valor) for forma, valor in porforma_hoje.items()]
    eh_segunda = data_prevista.weekday() == SEGUNDA
    entrada = calcular_entrada(agrupado_previsao, agrupado_anterior, titulos,
                               dia_previsto, ifood, args.b2b, override,
                               liquido=not args.bruto, ifood_manual=ifood_manual,
                               ifood_entra=not eh_segunda, arrasto=arrasto)
    entrada['origem_arrasto'] = origem_arrasto
    entrada['janela_ifood'] = janela
    # na segunda o repasse cai na quarta seguinte
    entrada['data_repasse'] = (data_prevista + datetime.timedelta(days=2)
                               if eh_segunda else None)
    entrada['ifood_faturado'] = args.ifood_faturado

    txt = os.path.join(args.saida, 'texto_whatsapp.txt')
    with open(txt, 'w') as arquivo:
        arquivo.write(montar_texto(dias_usados, total, entrada, dia_previsto))

    csv = os.path.join(args.saida, 'formas_agrupadas.csv')
    with open(csv, 'w') as arquivo:
        arquivo.write('FORMA DE PAGAMENTO;TOTAL;% DO TOTAL;COMPOSICAO\n')
        for forma, valor in sorted(agrupado.items(), key=lambda item: -item[1]):
            partes = composicao[forma]
            comp = (' + '.join(f'{s} R$ {brl(v)}'
                               for s, v in sorted(partes.items(), key=lambda i: -i[1]))
                    if len(partes) > 1 else '')
            arquivo.write(f'{forma};{brl(valor)};{brl(valor / total * 100)};{comp}\n')
        arquivo.write(f'TOTAL GERAL;{brl(total)};100,00;\n')

    print(f'Dias no arquivo: {", ".join(dias_usados)}')
    for dia, formas in dias.items():
        print(f'  {dia}: R$ {brl(sum(formas.values()))}')
    print(f'\n{len(linhas)} linhas apos o agrupamento | VENDA BRUTA R$ {brl(total)}')

    rotulo = 'BRUTA' if args.bruto else 'LIQUIDA (estimativa)'
    print(f'\nENTRADA PREVISTA PARA {dia_previsto} -- {rotulo}')
    print(f'  {"":28} {"bruto":>14} {"taxa":>7} {"liquido":>14}')
    for forma, bruto, taxa, liq in entrada['detalhe_vendas']:
        print(f'  {forma:<28} {brl(bruto):>14} {brl(taxa * 100)+"%":>7} {brl(liq):>14}')
    print(f'  {"= cartao + pix":<28} {"":>14} {"":>7} {brl(entrada["vendas"]):>14}')

    if gravados:
        total_corte = sum(r['valor'] for r in gravados)
        print(f'    (-) depois das {args.corte} de {dias_usados[-1][:5]}: '
              f'R$ {brl(total_corte)} -- guardado para {gravados[0]["entrada"]}')

    if entrada.get('pos_meia_noite') is not None:
        print(f'  depois da meia-noite de {origem_arrasto} (liquida hoje)')
        for forma, bruto, taxa, liq in entrada['detalhe_arrasto']:
            print(f'    {forma:<26} {brl(bruto):>14} {brl(taxa * 100)+"%":>7} {brl(liq):>14}')
        print(f'  {"= depois da meia-noite":<28} {"":>14} {"":>7} '
              f'{brl(entrada["pos_meia_noite"]):>14}')
    elif not args.sem_arrasto:
        proximas = sorted({r['entrada'] for r in registros})
        if proximas:
            print(f'  depois da meia-noite         nada guardado para {dia_previsto}')
            print(f'    datas guardadas: {", ".join(proximas)}')

    if agrupado_anterior is None:
        print('  voucher D+30                 FALTA --mes-anterior')
    else:
        print(f'  voucher D+30 ({dias_ant_usados[0]} a {dias_ant_usados[-1]})')
        bruto_voucher = sum(agrupado_anterior.get(f, 0.0) for f in FORMAS_VOUCHER)
        for forma in FORMAS_VOUCHER:
            if forma in agrupado_anterior:
                print(f'    {forma:<26} {brl(agrupado_anterior[forma]):>14}')
        print(f'  {"= voucher D+30":<28} {brl(bruto_voucher):>14} '
              f'{brl(entrada["taxa_voucher"] * 100)+"%":>7} {brl(entrada["voucher"]):>14}')

    if entrada['ifood_previa'] is not None:
        print(f'  PREVIA iFood (NAO entra hoje)    {brl(entrada["ifood_bruto"] or 0):>10} '
              f'{brl(entrada["taxa_ifood"] * 100)+"%":>7} {brl(entrada["ifood_previa"]):>14}')
        print(f'    semana {janela[0]:%d/%m} a {janela[1]:%d/%m}, '
              f'cai na quarta {entrada["data_repasse"]:%d/%m}')
    elif entrada['ifood'] is None:
        print('  repasse iFood                '
              + ('fora de segunda/quarta' if janela is None else 'FALTA --ifood'))
    elif entrada['ifood_manual']:
        print(f'  repasse iFood (na mao, ja liquido)')
        for rotulo, bruto, final in antecipado:
            print(f'    {rotulo:<26} {brl(bruto):>14} '
                  f'{brl(IFOOD_ANTECIPACAO * 100)+"%":>7} {brl(final):>14}')
        # os que vieram por --ifood-liquido ja apareceram com a memoria de calculo
        for rotulo, valor in entrada['ifood_manual']:
            if rotulo.endswith('(-1,59% antecip.)'):
                continue
            print(f'    {rotulo:<26} {"":>14} {"":>7} {brl(valor):>14}')
        print(f'  {"= repasse iFood":<28} {"":>14} {"":>7} {brl(entrada["ifood"]):>14}')
        if janela is not None:
            print(f'    referente a {janela[0]:%d/%m} a {janela[1]:%d/%m}')
    else:
        print(f'  {"repasse iFood":<28} {brl(entrada["ifood_bruto"]):>14} '
              f'{brl(entrada["taxa_ifood"] * 100)+"%":>7} {brl(entrada["ifood"]):>14}')
        print(f'    {janela[0]:%d/%m} a {janela[1]:%d/%m}'
              + (f', faltam {len(ifood_faltando)} dia(s)' if ifood_faltando else ''))

    venc_alvo = entrada.get('vencimento_a_prazo', dia_previsto)
    if entrada['a_prazo'] is None:
        print(f'  vendas a prazo               nenhum boleto venceu em {venc_alvo} '
              f'(entraria hoje, D+1)')
        proximos = sorted({t['vencimento'] for t in titulos},
                          key=lambda d: datetime.datetime.strptime(d, '%d/%m/%Y'))
        if proximos:
            entradas = ', '.join(
                f'{d} (entra {(datetime.datetime.strptime(d, "%d/%m/%Y").date() + datetime.timedelta(days=A_PRAZO_COMPENSACAO)):%d/%m})'
                for d in proximos)
            print(f'    vencimentos na tabela: {entradas}')
    else:
        print(f'  {"vendas a prazo (boleto D+1)":<28} R$ {brl(entrada["a_prazo"]):>13} '
              f'({len(entrada["titulos_a_prazo"])} titulos, venc. {venc_alvo})')

    print(f'  {"B2B iKI":<28} '
          f'{"SEM BASE" if entrada["b2b"] is None else "R$ " + brl(entrada["b2b"])}')
    print(f'  {"TOTAL PREVISTO":<28} {"":>14} {"":>7} {brl(entrada["total"]):>14}')

    print(f'\nGerado:\n  {png}\n  {txt}\n  {csv}')


if __name__ == '__main__':
    main()
