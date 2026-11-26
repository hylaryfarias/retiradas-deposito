#!/usr/bin/env python3
"""Confere, loja a loja, se o relatorio de cupons do dia veio completo.

Contar filiais nao pega loja que veio QUASE vazia -- foi assim que a BIGG'S 07
passou batida em 18/11/2026, com R$ 1.887,41 de um dia de R$ 21 mil. E a
contagem tambem nao diz QUAL loja sumiu, que foi a pergunta dela em 26/11,
quando tres lojas (BIGG'S 05, 06 e 08) ficaram de fora do export.

Este script compara cada loja contra os PROPRIOS dias recentes, no mesmo dia da
semana, e aponta quem nao apareceu e quem veio muito abaixo do normal.

    python3 conferir_lojas.py cupons_de_hoje.xlsx acervo/ outra_pasta/

Duas armadilhas que ele ja trata, as duas aprendidas na marra:

1. **O nome da loja muda entre arquivos.** `BIGGS 05 - PORTUGAL` e
   `BIGGS 05 - ZONA SUL`, `MARITACAS` e `MARITACAS 88`, com e sem apostrofo --
   o mesmo problema que duplicou a BIGGS 10 no painel. Por isso a comparacao e
   feita por uma chave normalizada (`BIGGS 05`), nunca pelo nome cru.
2. **Os arquivos do acervo se sobrepoem.** Varios exports trazem o mesmo dia, e
   somar todos conta a venda duas vezes -- num teste isso fez um sabado
   aparecer com R$ 93 mil numa loja que faz R$ 21 mil. Para cada dia o script
   fica com UM arquivo, o que tiver mais cupons daquele dia.

O que ele afirma e o que ele so sugere:

- **FALTA e conclusivo.** A loja vendeu em todos os dias de referencia e hoje
  nao tem uma linha sequer -- isso nao acontece por acaso.
- **CURTA e so um olhar.** A mediana mistura regimes quando a loja mudou de
  tamanho: a `BIGGS 08 E 09` virou `BIGGS 08` em algum momento, entao ela
  aparece como "curta" em dias que estao certos. Antes de levar para a Hylary,
  olhar os proprios dias recentes daquela loja.
"""
import argparse, collections, datetime, glob, os, re, statistics, sys

NOME_DIA = ['seg', 'ter', 'qua', 'qui', 'sex', 'sab', 'dom']
RE_LOJA = re.compile(r'\b(BIGGS|BG|ISAIAS|IS)\s*0*(\d+)')


def brl(v):
    return f'{v:,.2f}'.replace(',', 'X').replace('.', ',').replace('X', '.')


def chave_loja(nome):
    """`BIGG'S 05 - PORTUGAL` e `BIGGS 05 - ZONA SUL` viram a mesma chave."""
    nome = (nome or '').upper().replace("'", '')
    m = RE_LOJA.search(nome)
    if m:
        prefixo = 'BIGGS' if m.group(1) in ('BIGGS', 'BG') else 'ISAIAS'
        return f'{prefixo} {int(m.group(2)):02d}'
    return nome.strip()


def ler_cupons(caminho):
    """Devolve {dia: {(chave, forma): valor}}, {dia: n_cupons}, {dia: {chave: nome}}."""
    import openpyxl
    try:
        livro = openpyxl.load_workbook(caminho, read_only=True, data_only=True)
    except Exception as erro:
        print(f'  (ignorado: {os.path.basename(caminho)} -- {erro})', file=sys.stderr)
        return {}, {}, {}
    aba = livro[livro.sheetnames[0]]
    try:
        aba.reset_dimensions()
    except AttributeError:
        pass
    linhas = aba.iter_rows(values_only=True)
    cab = [str(c or '').strip() for c in next(linhas)]
    if 'Filial' not in cab or 'Data' not in cab:
        return {}, {}, {}
    col = {c: i for i, c in enumerate(cab)}
    valores = collections.defaultdict(lambda: collections.defaultdict(float))
    cupons = collections.defaultdict(set)
    nomes = collections.defaultdict(dict)
    for linha in linhas:
        if linha is None or linha[col['Data']] in (None, ''):
            continue
        dia = str(linha[col['Data']])[:10]
        k = chave_loja(linha[col['Filial']])
        try:
            v = float(linha[col['Vl. pagamento']] or 0)
        except (TypeError, ValueError):
            continue
        forma = str(linha[col['Desc. pagam.']] or '').strip().upper()
        valores[dia][(k, forma)] += v
        cupons[dia].add(str(linha[col['Cupom']]))
        nomes[dia][k] = str(linha[col['Filial']]).strip()
    return valores, {d: len(c) for d, c in cupons.items()}, nomes


def acervo(pastas):
    """Um arquivo por dia -- o mais completo. Ver armadilha 2 no topo."""
    cand = collections.defaultdict(list)
    for pasta in pastas:
        alvos = ([pasta] if pasta.lower().endswith('.xlsx')
                 else sorted(glob.glob(os.path.join(pasta, '*.xlsx'))))
        for caminho in alvos:
            valores, n, nomes = ler_cupons(caminho)
            for dia in valores:
                cand[dia].append((n[dia], valores[dia], nomes[dia]))
    dias, nomes = {}, {}
    for dia, lista in cand.items():
        lista.sort(key=lambda x: -x[0])
        dias[dia], nomes[dia] = lista[0][1], lista[0][2]
    return dias, nomes


def lojas_do_dia(mapa):
    tot = collections.defaultdict(float)
    for (k, _), v in mapa.items():
        tot[k] += v
    return tot


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('arquivo', help='o relatorio de cupons do dia a conferir')
    p.add_argument('acervo', nargs='*', default=[],
                   help='pastas (ou xlsx) com os relatorios dos dias anteriores')
    p.add_argument('--dia', help='dd/mm/aaaa a conferir (padrao: o unico dia do arquivo)')
    p.add_argument('--completo', type=int, default=16, metavar='N',
                   help='quantas filiais um dia precisa ter para servir de '
                        'referencia (padrao 16, que e a rede sem a BIGGS 07)')
    p.add_argument('--alerta', type=float, default=0.6, metavar='F',
                   help='abaixo desta fracao da mediana a loja e apontada (padrao 0,6)')
    p.add_argument('--janela', type=int, default=60, metavar='D',
                   help='quantos dias para tras procurar referencia (padrao 60)')
    args = p.parse_args()

    dias, nomes = acervo([args.arquivo] + args.acervo)
    hoje_valores, n_hoje, _ = ler_cupons(args.arquivo)
    if not hoje_valores:
        raise SystemExit('ERRO: nao consegui ler nenhum dia desse arquivo.')
    dia = args.dia or sorted(hoje_valores)[-1]
    if dia not in hoje_valores:
        raise SystemExit(f'ERRO: {dia} nao esta no arquivo. Dias: '
                         f'{", ".join(sorted(hoje_valores))}')
    dias[dia] = hoje_valores[dia]          # o arquivo de hoje manda no proprio dia
    alvo = datetime.datetime.strptime(dia, '%d/%m/%Y').date()
    hoje = lojas_do_dia(dias[dia])

    ref = [d for d in dias if d != dia
           and len(lojas_do_dia(dias[d])) >= args.completo
           and datetime.datetime.strptime(d, '%d/%m/%Y').date().weekday() == alvo.weekday()
           and alvo - datetime.timedelta(days=args.janela)
               <= datetime.datetime.strptime(d, '%d/%m/%Y').date() < alvo]
    ref.sort(key=lambda x: datetime.datetime.strptime(x, '%d/%m/%Y'))
    if not ref:
        raise SystemExit(f'ERRO: nenhum {NOME_DIA[alvo.weekday()]} completo nos '
                         f'ultimos {args.janela} dias para comparar. Passe mais '
                         f'pastas no acervo ou aumente --janela.')

    print(f'=== {dia} ({NOME_DIA[alvo.weekday()]}), {len(hoje)} filiais, '
          f'R$ {brl(sum(hoje.values()))}')
    print(f'    comparando com {len(ref)} {NOME_DIA[alvo.weekday()]}(s): {", ".join(ref)}')
    print()
    linhas, faltando, curtas = [], [], []
    todas = set()
    for d in ref:
        todas |= set(lojas_do_dia(dias[d]))
    for k in todas:
        amostras = [lojas_do_dia(dias[d])[k] for d in ref if lojas_do_dia(dias[d]).get(k)]
        if not amostras:
            continue
        med = statistics.median(amostras)
        v = hoje.get(k, 0.0)
        razao = v / med if med else 0
        linhas.append((razao, k, v, med))
        if v == 0:
            faltando.append((k, med))
        elif razao < args.alerta:
            curtas.append((k, v, med))
    print(f'  {"LOJA":16s} {"hoje":>13s} {"mediana":>13s}')
    for razao, k, v, med in sorted(linhas):
        if v == 0:
            marca = '   <<< NAO APARECE'
        elif razao < args.alerta:
            marca = f'   <<< so {razao * 100:.0f}% do normal'
        else:
            marca = ''
        print(f'  {k:16s} {brl(v):>13s} {brl(med):>13s} {razao * 100:7.1f}%{marca}')

    if not faltando and not curtas:
        print()
        print('  OK: nenhuma loja faltando nem muito abaixo do normal.')
        return 0
    print()
    perdido = sum(m for _, m in faltando) + sum(m - v for _, v, m in curtas)
    for k, med in sorted(faltando, key=lambda x: -x[1]):
        print(f'  FALTA  {k:16s} vale ~R$ {brl(med)} num {NOME_DIA[alvo.weekday()]} normal')
    for k, v, med in sorted(curtas, key=lambda x: -(x[2] - x[1])):
        print(f'  CURTA  {k:16s} veio R$ {brl(v)} contra ~R$ {brl(med)}'
              f'   (conferir: pode ser loja que mudou de tamanho)')
    print()
    print(f'  O dia esta ~R$ {brl(perdido)} abaixo do que seria com todas as lojas,')
    print(f'  ou seja, ele fecharia perto de R$ {brl(sum(hoje.values()) + perdido)}.')
    return 1


if __name__ == '__main__':
    raise SystemExit(main())
