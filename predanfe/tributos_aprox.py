"""Valor aproximado dos tributos (Lei 12.741, "IBPT") como o SysPDV calcula na transmissão.

O SysPDV usa, por NCM, um % federal e um % estadual; o valor do item é
    arred(base x federal / 100) + arred(base x estadual / 100)
e as informações complementares recebem os totais federal e estadual.

Os % que ele usa não ficam gravados no banco (a tabela NCM está zerada e o
arquivo C:\\Syspdv\\<versão>.ibpt é antigo). Por isso eles são *aprendidos* das
notas já transmitidas: para cada NCM, procura-se o par (federal, estadual)
que reproduz, centavo a centavo, todos os itens do período mais recente.
NCM que nunca saiu numa nota usa o arquivo .ibpt do SysPDV como estimativa.
"""
import csv
import io
import re
import time
import zlib
from decimal import ROUND_CEILING, ROUND_HALF_UP, Decimal
from pathlib import Path

C = Decimal("0.01")
CEM = Decimal(100)
# Percentuais estaduais candidatos (os vistos nas notas e as alíquotas usuais de ICMS)
ESTADUAIS = [Decimal(x) for x in ("18", "20", "27", "0", "4", "7", "12", "17", "19", "22", "25", "28", "29",
                                  "30", "33", "35")]
ITENS_POR_NCM = 40     # quantos itens recentes de cada NCM bastam para fixar os %
NOTAS_HISTORICO = 600  # quantas notas transmitidas recentes são lidas


def arred(v):
    return v.quantize(C, ROUND_HALF_UP)


def valor_item(base, federal, estadual):
    return arred(base * federal / CEM) + arred(base * estadual / CEM)


def _faixa_federal(itens, estadual):
    """Intervalo de % federal (em centésimos) que reproduz todos os itens, ou None."""
    baixo, alto = Decimal(0), Decimal(10000)  # 0,00% a 100,00%, em centésimos de %
    for base, vtt in itens:
        if base <= 0:
            continue
        alvo = vtt - arred(base * estadual / CEM)
        # arred(base*f/100) == alvo  <=>  alvo-0,005 <= base*f/100 < alvo+0,005
        lo = (alvo - Decimal("0.005")) * CEM / base * CEM
        hi = (alvo + Decimal("0.005")) * CEM / base * CEM
        baixo, alto = max(baixo, lo), min(alto, hi)
        if baixo >= alto:
            return None
    return baixo, alto


def _pares_possiveis(itens):
    """Pares (federal, estadual) com 2 casas que reproduzem todos os itens."""
    pares = []
    for e in ESTADUAIS:
        faixa = _faixa_federal(itens, e)
        if faixa is None:
            continue
        inicio = int(faixa[0].to_integral_value(rounding=ROUND_CEILING))
        for cent in range(inicio, inicio + 6):
            f = Decimal(cent) / CEM
            if Decimal(cent) < faixa[1] and all(valor_item(b, f, e) == v for b, v in itens):
                pares.append((f, e))
    return pares


class TabelaIBPT:
    """% federal/estadual por (NCM, origem nacional/importado).

    `taxas` é o par usado no valor de cada item (vTotTrib); `taxas_texto` é o
    par usado nos totais "Federais/Estaduais" das informações complementares.
    Em alguns NCMs o SysPDV usa % diferentes nos dois lugares (ex.: água
    22011000: itens 13,45+20, texto 14,21+20), por isso são aprendidos à parte.
    """

    def __init__(self, notas, arquivo_ibpt=None):
        """notas: lista (mais recente primeiro) de dicts com 'itens' [(ncm, importado, base, vtt)],
        'F', 'E' (totais do texto, ou None)."""
        self.taxas = {}
        self.taxas_texto = {}
        self._pares_itens = {}
        self.arquivo = arquivo_ibpt or {}
        por_chave = {}
        for n in notas:
            for ncm, imp, base, vtt in n["itens"]:
                lista = por_chave.setdefault((ncm, imp), [])
                if len(lista) < ITENS_POR_NCM and vtt is not None:
                    lista.append((base, vtt))
        for chave, itens in por_chave.items():
            # período mais recente em que um mesmo par explica tudo
            usados = itens
            pares = _pares_possiveis(usados)
            while not pares and len(usados) > 1:
                usados = usados[: max(1, len(usados) // 2)]
                pares = _pares_possiveis(usados)
            if pares:
                self._pares_itens[chave] = pares
        # Quando vários pares explicam os itens (NCM com pouco histórico), fica o
        # par que serve para mais NCMs da empresa (ex.: 13,45+18 nos alimentos).
        self.frequencia = {}
        for pares in self._pares_itens.values():
            for p in pares:
                self.frequencia[p] = self.frequencia.get(p, 0) + 1
        for chave, pares in self._pares_itens.items():
            self.taxas[chave] = max(pares, key=lambda p: (self.frequencia.get(p, 0), -pares.index(p)))
        self.estadual_comum = self._estadual_mais_comum()
        self._aprender_texto(notas)
        # quando vários pares explicam os itens, fica o mesmo do texto (se servir)
        for chave, pares in self._pares_itens.items():
            if self.taxas_texto.get(chave) in pares:
                self.taxas[chave] = self.taxas_texto[chave]

    # ---------------------------------------------------------- texto

    def _aprender_texto(self, notas, voltas=6):
        """% do texto por NCM. Cada NCM escolhe, entre os pares que aparecem nas
        notas (ex.: 13,45+18, 14,21+20, 23,37+27), o que faz mais notas baterem
        exatamente no texto; repete até estabilizar (vários NCMs por nota)."""
        self.taxas_texto = dict(self.taxas)
        com_texto = [n for n in notas[:300] if n["F"] is not None]
        if not com_texto:
            return
        # pares candidatos: os dos itens e os lidos direto de notas com um só NCM
        candidatos = set(self.taxas.values())
        for n in com_texto:
            chaves = {(i[0], i[1]) for i in n["itens"]}
            if len(chaves) == 1:
                par = self._par_de_nota_unica(n)
                if par:
                    candidatos.add(par)
                    self.taxas_texto[chaves.pop()] = par
        candidatos = sorted(candidatos)
        por_chave = {}
        for n in com_texto:
            for ncm, imp, *_ in n["itens"]:
                por_chave.setdefault((ncm, imp), []).append(n)

        for _ in range(voltas):
            mudou = False
            for chave, notas_chave in por_chave.items():
                atual = self.taxas_texto.get(chave)
                if atual is None:
                    continue

                def nota(par):
                    exatas, erro = 0, Decimal(0)
                    for n in notas_chave:
                        F, E, completo = self._totais(n["itens"], {chave: par}, texto=True)
                        if completo:
                            exatas += F == n["F"] and E == n["E"]
                            erro += abs(F - n["F"]) + abs(E - n["E"])
                    return (-exatas, erro, -self.frequencia.get(par, 0), par != atual)
                melhor = min(candidatos, key=nota)
                if nota(melhor)[0] == 0:
                    # nenhuma nota bate exatamente: sem evidência, o texto usa o par dos itens
                    melhor = self.taxas.get(chave, atual)
                if melhor != atual:
                    self.taxas_texto[chave] = melhor
                    mudou = True
            if not mudou:
                break

    @staticmethod
    def _par_de_nota_unica(n):
        """Nota com um só NCM: o par (federal, estadual) do texto sai direto dela."""
        achados = []
        for e in ESTADUAIS:
            if sum(arred(b * e / CEM) for _, _, b, *_ in n["itens"]) != n["E"]:
                continue
            base = sum(b for _, _, b, *_ in n["itens"])
            if not base:
                continue
            aprox = (n["F"] * CEM / base).quantize(C)
            for f in (aprox - C, aprox, aprox + C):
                if sum(arred(b * f / CEM) for _, _, b, *_ in n["itens"]) == n["F"]:
                    achados.append((f, e))
                    break
        return achados[0] if len(achados) == 1 else None

    def _totais(self, itens, troca=None, texto=False):
        tabela = self.taxas_texto if texto else self.taxas
        F = E = Decimal(0)
        completo = True
        for ncm, imp, base, *_ in itens:
            par = (troca or {}).get((ncm, imp)) or tabela.get((ncm, imp))
            if par is None:
                completo = False
                continue
            F += arred(base * par[0] / CEM)
            E += arred(base * par[1] / CEM)
        return F, E, completo

    def _estadual_mais_comum(self):
        contagem = {}
        for _, e in self.taxas.values():
            contagem[e] = contagem.get(e, 0) + 1
        return max(contagem, key=contagem.get) if contagem else None

    # ---------------------------------------------------------- consulta

    def taxa(self, ncm, importado=False, texto=False):
        """(federal, estadual, origem) — origem: 'notas', 'arquivo' ou None (desconhecido).

        NCM sem histórico: federal do arquivo .ibpt do SysPDV e o estadual mais
        usado nas notas (o estadual do arquivo, de 2024, está desatualizado).
        """
        par = (self.taxas_texto if texto else self.taxas).get((ncm, importado))
        if par:
            return par[0], par[1], "notas"
        arq = self.arquivo.get(ncm)
        if arq:
            nac, imp, est = arq
            return (imp if importado else nac), (self.estadual_comum if self.estadual_comum is not None else est), \
                "arquivo"
        return None, None, None


# ---------------------------------------------------------------- leitura

RE_TEXTO = re.compile(r"Federais R\$ ([\d.,]+) \(([\d,]+)%\).*?Estaduais R\$ ([\d.,]+) \(([\d,]+)%\)")


def _br(s):
    return Decimal(s.replace(".", "").replace(",", "."))


def ler_nota_xml(xml):
    """Itens e totais do IBPT de um XML oficial (para aprender)."""
    itens = []
    for det in re.findall(r"<det nItem.*?</det>", xml, re.S):
        ncm = re.search(r"<NCM>(.*?)</NCM>", det)
        vprod = re.search(r"<vProd>(.*?)</vProd>", det)
        vdesc = re.search(r"<vDesc>(.*?)</vDesc>", det)
        vtt = re.search(r"<vTotTrib>(.*?)</vTotTrib>", det)
        orig = re.search(r"<orig>(.*?)</orig>", det)
        if not (ncm and vprod):
            continue
        base = Decimal(vprod.group(1)) - (Decimal(vdesc.group(1)) if vdesc else 0)
        itens.append((ncm.group(1), (orig.group(1) if orig else "0") in ("1", "2", "3", "8"), base,
                      Decimal(vtt.group(1)) if vtt else None))
    inf = re.search(r"<infCpl>(.*?)</infCpl>", xml, re.S)
    m = RE_TEXTO.search(inf.group(1)) if inf else None
    return {"itens": itens, "F": _br(m.group(1)) if m else None, "E": _br(m.group(3)) if m else None}


def ler_arquivo_ibpt(versao, pasta=Path(r"C:\Syspdv")):
    """Arquivo .ibpt do SysPDV (zlib + CSV). Usado só para NCM sem histórico."""
    caminho = Path(pasta) / f"{versao}.ibpt"
    if not versao or not caminho.exists():
        return {}
    try:
        texto = zlib.decompress(caminho.read_bytes()).decode("latin-1")
    except (OSError, zlib.error):
        return {}
    tabela = {}
    # Os mesmos % se repetem em milhares de NCMs: cada combinação de textos vira um
    # único trio de Decimal, compartilhado (a tabela cai de ~4,4 MB para ~1 MB).
    trios = {}
    for c in csv.reader(io.StringIO(texto), delimiter=";"):
        if len(c) > 7 and c[2] == "0" and c[1].strip() == "":
            textos = (c[4], c[5], c[6])
            trio = trios.get(textos)
            if trio is None:
                try:
                    trio = trios[textos] = (Decimal(c[4]), Decimal(c[5]), Decimal(c[6]))
                except ArithmeticError:
                    continue
            tabela[c[0]] = trio
    return tabela


_cache = {"quando": 0.0, "tabela": None}


def tabela_atual(cur, validade_seg=600):
    """Tabela aprendida das notas transmitidas (guardada por 10 minutos)."""
    if _cache["tabela"] is not None and time.time() - _cache["quando"] < validade_seg:
        return _cache["tabela"]
    cur.execute(f"""SELECT FIRST {NOTAS_HISTORICO} NFSXMLEMINFE FROM NOTAFISCAL
                    WHERE NFSXMLEMINFE IS NOT NULL AND NFSTIP <> 'CAN' AND NFSFINNFE <> '4'
                    ORDER BY NFSDATAUT DESC""")
    notas = []
    for (blob,) in cur.fetchall():
        dados = blob.read() if hasattr(blob, "read") else blob
        notas.append(ler_nota_xml(dados.decode("utf-8", "replace")))
    cur.execute("SELECT FIRST 1 PRPVERARQIBPT FROM PROPRIO")
    linha = cur.fetchone()
    tabela = TabelaIBPT(notas, ler_arquivo_ibpt((linha[0] or "").strip() if linha else ""))
    _cache.update(quando=time.time(), tabela=tabela)
    return tabela
