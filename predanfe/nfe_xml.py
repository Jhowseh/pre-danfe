"""Monta um XML de NF-e (4.00, sem assinatura) a partir das tabelas do SysPDV.

O XML serve só para desenhar o pré-DANFE. O mapeamento dos campos foi tirado
de notas reais já autorizadas (o XML gravado em NOTAFISCAL.NFSXMLEMINFE).
"""
import re
import unicodedata
import xml.etree.ElementTree as ET
from datetime import datetime, time
from decimal import ROUND_HALF_DOWN, ROUND_HALF_UP, Decimal

import tributos_aprox
from banco import linhas_dict

NS = "http://www.portalfiscal.inf.br/nfe"
ZERO = Decimal("0")
BLOCO = object()  # marca "elemento sem texto próprio" em _Montador.sub

# ---------------------------------------------------------------- consultas

SQL_NOTA = """
SELECT NFSCTR, NFSNUM, NFSSER, NFSTIP, NFSTNF, CFOCOD, OPECOD, CLICOD, FORCOD,
       NFSDATEMI, NFSDATSAI, NFSHORSAI, NFSFINNFE, NFSAMBNFE, NFSTIPPAGTO,
       NFSCLIDES, NFSCLIEND, NFSCLINUM, NFSCLICMP, NFSCLIBAI, NFSCLICID, NFSCLIEST,
       NFSCLICEP, NFSCLITEL, NFSCLICPFCGC, NFSCLIRGCGF, NFSCLIPFPJ,
       NFSVLR, NFSDCN, NFSVLRBASEICMS, NFSVLRICMS, NFSBASSUBS, NFSVLRSUBS, NFSVLRIPI,
       NFSVLRFRT, NFSVLRSEG, NFSVLROUTRAS, NFSVLRACR, NFSICMFCPST,
       NFSCIFFOB, NFSPLC, NFSPLCEST, NFSQTD, NFSESP, NFSMARCA, NFSPESBRT, NFSPESLIQ,
       NFSOBS1, NFSOBS2, NFSOBS3, NFSOBS4, NFSOBS5, NFSOBS6, NFSOBSERVACAO,
       NFSSTATNFE, NFSACAONFE, NFSCHVNFE, NFSPROTNFE,
       NFSBCIBSCBS, NFSVLRIBSUF, NFSVLRIBS, NFSVLRCBS,
       IIF(NFSXMLEMINFE IS NULL, 'N', 'S') AS TEM_XML
  FROM NOTAFISCAL
 WHERE NFSCTR = ?
"""

SQL_ITENS = """
SELECT I.INFSEQ, I.PROCOD, I.INFPRODES, NULLIF(TRIM(I.INFNCM), '') AS INFNCM, P.PRONCM,
       I.CFOCOD, I.INFUND,
       COALESCE(U.UNDPAD, I.INFUND) AS UNIDADE, P.PROCEST,
       I.INFQTDEMB, I.INFVLREMB, I.INFVLRTOT, I.INFVLRDCN, I.INFVLRFRT, I.INFVLRSEG, I.INFVLROUTRAS,
       I.INFTABA, I.INFTABB, I.INFCSOSN, I.INFBASEICMS, I.INFALQ, I.INFPERRED, I.INFVLRIMP,
       I.INFBASSUBS, I.INFVLRSUBS, I.INFALQST, I.INFALQFCP, I.INFICMFCP, I.INFICMFCPST,
       I.INFBASEIPI, I.INFVLRIPI,
       I.INFCSTPIS, I.INFBASEPIS, I.INFALQPIS, I.INFVLRPIS,
       I.INFCSTCOFINS, I.INFBASECOFINS, I.INFALQCOFINS, I.INFVLRCOFINS,
       I.CSTIBSCBSCOD, I.CLATRBCOD, I.INFBCIBSCBS, I.INFALQIBSUF, I.INFVLRIBSUF, I.INFALQCBS, I.INFVLRCBS
  FROM ITEM_NOTA_FISCAL I
  LEFT JOIN PRODUTO P ON P.PROCOD = I.PROCOD
  LEFT JOIN UNIDADE U ON U.UNDCOD = I.INFUND
 WHERE I.NFSCTR = ?
 ORDER BY I.INFSEQ
"""

# Só dados cadastrais: PROPRIO também guarda senhas e o certificado.
SQL_EMITENTE = """
SELECT FIRST 1 PRPDES, PRPFAN, PRPCGC, PRPIERG, PRPINCMUN, PRPEND, PRPNUM, PRPCMP,
       PRPBAI, PRPMUN, PRPCODIBGE, PRPUF, PRPCEP, PRPTEL, PRPCRT, PRPREGFED
  FROM PROPRIO ORDER BY PRPCOD
"""

SQL_CLIENTE = "SELECT CLICODIGOIBGE, CLIEMAIL FROM CLIENTE WHERE CLICOD = ?"
SQL_CIDADES_UF = "SELECT CODIBGE, CODIBGECID FROM FISCO_CODIGOIBGE WHERE CODIBGEUF = ?"

# Código IBGE das UFs (2 primeiros dígitos do código do município).
COD_UF = {
    "RO": "11", "AC": "12", "AM": "13", "RR": "14", "PA": "15", "AP": "16", "TO": "17",
    "MA": "21", "PI": "22", "CE": "23", "RN": "24", "PB": "25", "PE": "26", "AL": "27",
    "SE": "28", "BA": "29", "MG": "31", "ES": "32", "RJ": "33", "SP": "35", "PR": "41",
    "SC": "42", "RS": "43", "MS": "50", "MT": "51", "GO": "52", "DF": "53",
}
SQL_CFOP = "SELECT CFODES FROM CFOP WHERE CFOCOD = ?"
SQL_TRANSP = """
SELECT FORDES, FORCGC, FORCGF, FOREND, FORNUM, FORCID, FOREST FROM FORNECEDOR WHERE FORCOD = ?
"""
SQL_REFERENCIAS = """
SELECT NFRFORCOD, NFRENTSER, NFRENTDOC, NFRENTTNF FROM NOTAFISCAL_REFERENCIA WHERE NFSCTR = ?
"""
SQL_CHAVES_REF = "SELECT NFRCHVAVS FROM NOTAFISCAL_REFERENCIA WHERE NFSCTR = ? ORDER BY NFRSEQ"
SQL_NCM_ENTRADA = """
SELECT FIRST 1 ITENCM FROM ITEM_ENTRADA
 WHERE FORCOD = ? AND ENTSER = ? AND ENTDOC = ? AND ENTTNF = ? AND PROCOD = ?
   AND COALESCE(TRIM(ITENCM), '') <> ''
"""


def _todos(cur, sql, params=()):
    cur.execute(sql, params)
    return linhas_dict(cur)


def _um(cur, sql, params=()):
    regs = _todos(cur, sql, params)
    return regs[0] if regs else {}


def sem_acento(s):
    return unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().upper().strip()


def cod_municipio(cur, cidade, uf, reserva=None):
    """Código IBGE pelo nome da cidade + UF (como o SysPDV faz); senão, o do cadastro."""
    if uf in COD_UF and cidade:
        alvo = sem_acento(cidade)
        for cod, nome in _todos_tuplas(cur, SQL_CIDADES_UF, (uf,)):
            if sem_acento(nome) == alvo:
                return COD_UF[uf] + cod.strip()
    return reserva


def _todos_tuplas(cur, sql, params=()):
    cur.execute(sql, params)
    return cur.fetchall()


def carregar_nota(cur, nfsctr, tabela_ibpt=None):
    """Lê do banco tudo o que o pré-DANFE precisa de uma nota.

    tabela_ibpt: % do IBPT aprendidos das notas transmitidas (padrão: os atuais).
    """
    nota = _um(cur, SQL_NOTA, (nfsctr,))
    if not nota:
        raise ValueError(f"Nota NFSCTR={nfsctr} não encontrada.")
    cliente = _um(cur, SQL_CLIENTE, (nota["CLICOD"],)) if nota["CLICOD"] else {}
    cliente["CMUN"] = cod_municipio(cur, nota["NFSCLICID"], nota["NFSCLIEST"], cliente.get("CLICODIGOIBGE"))

    # NCM: o do item; se vazio, o da nota de entrada referenciada (devoluções);
    # por último, o do cadastro do produto.
    refs = _todos_tuplas(cur, SQL_REFERENCIAS, (nfsctr,))
    itens = _todos(cur, SQL_ITENS, (nfsctr,))
    for it in itens:
        if not it["INFNCM"]:
            for ref in refs:
                achado = _todos_tuplas(cur, SQL_NCM_ENTRADA, (*ref, it["PROCOD"]))
                if achado:
                    it["INFNCM"] = achado[0][0].strip()
                    break
        it["INFNCM"] = it["INFNCM"] or it["PRONCM"]

    return {
        "nota": nota,
        "itens": itens,
        "emitente": _um(cur, SQL_EMITENTE),
        "cliente": cliente,
        "cfop": _um(cur, SQL_CFOP, (nota["CFOCOD"],)),
        "transp": _um(cur, SQL_TRANSP, (nota["FORCOD"],)) if nota["FORCOD"] else {},
        "chaves_ref": [r[0].strip() for r in _todos_tuplas(cur, SQL_CHAVES_REF, (nfsctr,)) if r[0] and r[0].strip()],
        "ibpt": tabela_ibpt if tabela_ibpt is not None else tributos_aprox.tabela_atual(cur),
    }


# ---------------------------------------------------------------- utilidades


def dec(v):
    return Decimal(str(v)) if v is not None else ZERO


# Alíquotas de PIS/COFINS (CST 01) pelo regime federal da empresa (PROPRIO.PRPREGFED)
ALIQUOTAS_PIS_COFINS = {"R": (Decimal("1.65"), Decimal("7.60")),   # lucro real (não cumulativo)
                        "P": (Decimal("0.65"), Decimal("3.00"))}   # lucro presumido (cumulativo)
RE_TEXTO_IBPT = re.compile(r"Val Aprox Tributos Federais R\$ [\d.,]+(?: \([\d.,]+%\))?\s*"
                           r"Val Aprox Tributos Estaduais R\$ [\d.,]+(?: \([\d.,]+%\))?\s*Fonte: IBPT")


def moeda_br(v):
    """1234.5 -> '1234,50' (formato do texto do IBPT nas notas: sem ponto de milhar)."""
    return f"{tributos_aprox.arred(dec(v)):.2f}".replace(".", ",")


def limpar_texto(s):
    """Como o texto sai no XML: sem acentos, hífen vira espaço, linhas e espaços juntados."""
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode()
    return " ".join(s.replace("-", " ").split())


def fmt(v, casas=2):
    q = Decimal(1).scaleb(-casas)
    return str(dec(v).quantize(q, rounding=ROUND_HALF_UP))


def so_digitos(s):
    return re.sub(r"\D", "", s or "")


def data_hora(d, h):
    """Data do banco + hora -> '2026-06-05T12:02:30-03:00'."""
    if d is None:
        return None
    dia = d.date() if isinstance(d, datetime) else d
    hora = h if isinstance(h, time) else time(0, 0)
    return datetime.combine(dia, hora.replace(microsecond=0)).isoformat() + "-03:00"


def dv_chave(chave43):
    """Dígito verificador da chave de acesso (módulo 11, pesos 2 a 9)."""
    soma, peso = 0, 2
    for c in reversed(chave43):
        soma += int(c) * peso
        peso = 2 if peso == 9 else peso + 1
    resto = soma % 11
    return 0 if resto < 2 else 11 - resto


def chave_acesso(cuf, emissao, cnpj, serie, numero, cnf, modelo="55", tp_emis="1"):
    base = f"{cuf}{emissao:%y%m}{cnpj:0>14}{modelo}{int(serie):03d}{int(numero):09d}{tp_emis}{int(cnf):08d}"
    return base + str(dv_chave(base))


class _Montador:
    """Ajuda a montar elementos pulando campos vazios."""

    def __init__(self):
        ET.register_namespace("", NS)

    @staticmethod
    def sub(pai, tag, texto=BLOCO, obrigatorio=False, **attrs):
        """Sem `texto`: cria um bloco. Com texto vazio: não cria o campo."""
        if texto is BLOCO:
            return ET.SubElement(pai, f"{{{NS}}}{tag}", attrs)
        if texto in (None, "") and not obrigatorio:
            return None
        el = ET.SubElement(pai, f"{{{NS}}}{tag}", attrs)
        if texto not in (None, ""):
            el.text = str(texto)
        return el

    def grupo(self, pai, tag, campos):
        """campos: lista de (tag, valor). Só cria o grupo se algum valor existir."""
        if not any(v not in (None, "") for _, v in campos):
            return None
        g = ET.SubElement(pai, f"{{{NS}}}{tag}")
        for t, v in campos:
            self.sub(g, t, v)
        return g


# ---------------------------------------------------------------- XML


def montar_xml(dados, aviso=None):
    """Retorna (xml_str, chave, avisos). `aviso` vai no início das informações complementares."""
    n, emi, cli = dados["nota"], dados["emitente"], dados["cliente"]
    m = _Montador()
    sub = m.sub
    avisos = []

    cuf = (emi.get("PRPCODIBGE") or "25")[:2]
    emissao = n["NFSDATEMI"] or datetime.now()
    cnf = int(n["NFSCTR"])  # o SysPDV usa o NFSCTR como código numérico da chave
    cnpj = so_digitos(emi["PRPCGC"])
    chave = chave_acesso(cuf, emissao, cnpj, n["NFSSER"], n["NFSNUM"], cnf)
    if n.get("NFSCHVNFE") and n["NFSCHVNFE"].strip() != chave:
        avisos.append(f"Chave gravada no banco ({n['NFSCHVNFE'].strip()}) difere da calculada ({chave}).")

    raiz = ET.Element(f"{{{NS}}}NFe")
    inf = sub(raiz, "infNFe", Id=f"NFe{chave}", versao="4.00")

    # ide
    cfop_nota = (n["CFOCOD"] or "").strip()[:4]
    uf_dest = n["NFSCLIEST"] or ""
    doc_dest = so_digitos(n["NFSCLICPFCGC"])
    ie_dest = so_digitos(n["NFSCLIRGCGF"]) if (n["NFSCLIRGCGF"] or "").upper() != "ISENTO" else ""
    ide = sub(inf, "ide")
    for tag, val in [
        ("cUF", cuf), ("cNF", f"{cnf:08d}"),
        ("natOp", (dados["cfop"].get("CFODES") or "")[:60]),
        ("mod", "55"), ("serie", int(n["NFSSER"])), ("nNF", int(n["NFSNUM"])),
        ("dhEmi", data_hora(n["NFSDATEMI"], n["NFSHORSAI"])),
        ("dhSaiEnt", data_hora(n["NFSDATSAI"], n["NFSHORSAI"])),
        ("tpNF", "0" if cfop_nota[:1] in ("1", "2", "3") else "1"),
        ("idDest", "3" if cfop_nota[:1] in ("3", "7") else ("1" if uf_dest == emi["PRPUF"] else "2")),
        ("cMunFG", emi["PRPCODIBGE"]), ("tpImp", "1"), ("tpEmis", "1"), ("cDV", chave[-1]),
        ("tpAmb", n["NFSAMBNFE"] or "1"), ("finNFe", n["NFSFINNFE"] or "1"),
        ("indFinal", "1" if len(doc_dest) == 11 or not ie_dest else "0"),
        ("indPres", "1"), ("procEmi", "0"), ("verProc", "PreDanfe"),
    ]:
        sub(ide, tag, val)

    # emitente
    em = sub(inf, "emit")
    sub(em, "CNPJ", cnpj)
    sub(em, "xNome", emi["PRPDES"])
    sub(em, "xFant", emi["PRPFAN"])
    m.grupo(em, "enderEmit", [
        ("xLgr", emi["PRPEND"]), ("nro", emi["PRPNUM"]), ("xCpl", emi["PRPCMP"]),
        ("xBairro", emi["PRPBAI"]), ("cMun", emi["PRPCODIBGE"]), ("xMun", emi["PRPMUN"]),
        ("UF", emi["PRPUF"]), ("CEP", so_digitos(emi["PRPCEP"])), ("cPais", "1058"),
        ("xPais", "BRASIL"), ("fone", so_digitos(emi["PRPTEL"])),
    ])
    sub(em, "IE", so_digitos(emi["PRPIERG"]))
    sub(em, "IM", emi.get("PRPINCMUN"))
    sub(em, "CRT", emi["PRPCRT"] or "3")

    # destinatário
    de = sub(inf, "dest")
    sub(de, "CPF" if len(doc_dest) == 11 else "CNPJ", doc_dest)
    sub(de, "xNome", n["NFSCLIDES"])
    m.grupo(de, "enderDest", [
        ("xLgr", n["NFSCLIEND"]), ("nro", n["NFSCLINUM"] or "SN"), ("xCpl", n["NFSCLICMP"]),
        ("xBairro", n["NFSCLIBAI"]), ("cMun", cli.get("CMUN")), ("xMun", n["NFSCLICID"]),
        ("UF", uf_dest), ("CEP", so_digitos(n["NFSCLICEP"])), ("cPais", "1058"),
        ("xPais", "BRASIL"), ("fone", so_digitos(n["NFSCLITEL"])),
    ])
    sub(de, "indIEDest", "1" if ie_dest else "9")
    sub(de, "IE", ie_dest)

    # itens
    tot = {k: ZERO for k in ("vProd", "vPIS", "vCOFINS", "vFCP", "vTotTrib", "F", "E")}
    crt_simples = (emi["PRPCRT"] or "3") in ("1", "2")
    # PIS/COFINS de CST 01: o SysPDV grava a base ao salvar, mas a alíquota e o
    # valor só na transmissão, pelo regime federal da empresa.
    aliq_regime = ALIQUOTAS_PIS_COFINS.get((emi.get("PRPREGFED") or "").strip())
    devolucao = (n["NFSFINNFE"] or "1") == "4"
    ibpt = None if devolucao else dados.get("ibpt")  # devolução não leva tributos aproximados
    ibpt_estimado, ibpt_sem = set(), set()
    for i, it in enumerate(dados["itens"], start=1):
        det = sub(inf, "det", nItem=str(i))
        pr = sub(det, "prod")
        procod = (it["PROCOD"] or "").strip()
        # No banco o total do item já vem sem o desconto; no XML, vProd é
        # quantidade x unitário e o desconto vai separado em vDesc.
        v_prod = (dec(it["INFQTDEMB"]) * dec(it["INFVLREMB"])).quantize(Decimal("0.01"), ROUND_HALF_UP)
        for tag, val in [
            ("cProd", procod[-13:]), ("cEAN", "SEM GTIN"), ("xProd", it["INFPRODES"]),
            ("NCM", it["INFNCM"]), ("CEST", it["PROCEST"]), ("CFOP", (it["CFOCOD"] or "")[:4]),
            ("uCom", it["UNIDADE"]), ("qCom", fmt(it["INFQTDEMB"], 3)),
            ("vUnCom", fmt(it["INFVLREMB"], 8)), ("vProd", fmt(v_prod)),
            ("cEANTrib", "SEM GTIN"), ("uTrib", it["UNIDADE"]), ("qTrib", fmt(it["INFQTDEMB"], 3)),
            ("vUnTrib", fmt(it["INFVLREMB"], 10)),
        ]:
            sub(pr, tag, val)
        for tag, campo in (("vFrete", "INFVLRFRT"), ("vSeg", "INFVLRSEG"),
                           ("vDesc", "INFVLRDCN"), ("vOutro", "INFVLROUTRAS")):
            if dec(it[campo]) > 0:
                sub(pr, tag, fmt(it[campo]))
        sub(pr, "indTot", "1")
        tot["vProd"] += v_prod
        liquido = v_prod - dec(it["INFVLRDCN"]).quantize(Decimal("0.01"), ROUND_HALF_UP)
        if liquido != dec(it["INFVLRTOT"]):
            avisos.append(f"Item {i}: quantidade x unitário - desconto = {liquido}, "
                          f"mas o total gravado é {fmt(it['INFVLRTOT'])}.")

        imp = sub(det, "imposto")
        orig, cst = it["INFTABA"] or "0", (it["INFTABB"] or "").strip()
        # valor aproximado dos tributos (IBPT), como o SysPDV calcula ao transmitir
        if ibpt is not None:
            ncm = (it["INFNCM"] or "").strip()
            importado = orig.strip() in ("1", "2", "3", "8")
            f, e, origem = ibpt.taxa(ncm, importado)
            if f is None:
                ibpt_sem.add(ncm)
            else:
                if origem == "arquivo":
                    ibpt_estimado.add(ncm)
                v_tt = tributos_aprox.valor_item(liquido, f, e)
                sub(imp, "vTotTrib", fmt(v_tt))
                tot["vTotTrib"] += v_tt
                ft, et, _ = ibpt.taxa(ncm, importado, texto=True)
                tot["F"] += tributos_aprox.arred(liquido * ft / 100)
                tot["E"] += tributos_aprox.arred(liquido * et / 100)
        icms = sub(imp, "ICMS")
        if crt_simples:
            g = sub(icms, f"ICMSSN{(it['INFCSOSN'] or '102').strip()}", obrigatorio=True)
            sub(g, "orig", orig)
            sub(g, "CSOSN", (it["INFCSOSN"] or "").strip())
        else:
            nome = {"40": "40", "41": "40", "50": "40"}.get(cst, cst or "90")
            g = sub(icms, f"ICMS{nome}", obrigatorio=True)
            sub(g, "orig", orig)
            sub(g, "CST", cst)
        if dec(it["INFBASEICMS"]) > 0 or dec(it["INFVLRIMP"]) > 0:
            sub(g, "modBC", "3")
            if dec(it["INFPERRED"]) > 0:
                sub(g, "pRedBC", fmt(it["INFPERRED"], 4))
            sub(g, "vBC", fmt(it["INFBASEICMS"]))
            sub(g, "pICMS", fmt(it["INFALQ"]))
            sub(g, "vICMS", fmt(it["INFVLRIMP"]))
        if dec(it["INFICMFCP"]) > 0:
            sub(g, "pFCP", fmt(it["INFALQFCP"]))
            sub(g, "vFCP", fmt(it["INFICMFCP"]))
            tot["vFCP"] += dec(it["INFICMFCP"])
        if dec(it["INFBASSUBS"]) > 0 or dec(it["INFVLRSUBS"]) > 0:
            sub(g, "modBCST", "4")
            sub(g, "vBCST", fmt(it["INFBASSUBS"]))
            sub(g, "pICMSST", fmt(it["INFALQST"]))
            sub(g, "vICMSST", fmt(it["INFVLRSUBS"]))

        if dec(it["INFVLRIPI"]) > 0:
            ipi = sub(imp, "IPI")
            sub(ipi, "cEnq", "999")
            gi = sub(ipi, "IPITrib")
            sub(gi, "CST", "50")
            base = dec(it["INFBASEIPI"])
            sub(gi, "vBC", fmt(base))
            sub(gi, "pIPI", fmt(dec(it["INFVLRIPI"]) * 100 / base if base else 0))
            sub(gi, "vIPI", fmt(it["INFVLRIPI"]))

        for indice, (trib, pre) in enumerate((("PIS", "PIS"), ("COFINS", "COFINS"))):
            cst_t = (it[f"INFCST{pre}"] or "").strip() or "99"
            base_t, aliq_t, valor_t = dec(it[f"INFBASE{pre}"]), dec(it[f"INFALQ{pre}"]), dec(it[f"INFVLR{pre}"])
            if cst_t in ("01", "02"):
                if cst_t == "01" and aliq_regime:
                    aliq_t = aliq_regime[indice]
                # meio centavo exato arredonda para baixo (como o SysPDV: 1,995 -> 1,99)
                valor_t = (base_t * aliq_t / 100).quantize(Decimal("0.01"), ROUND_HALF_DOWN)
            el = sub(imp, trib)
            if cst_t in ("01", "02"):
                g = sub(el, f"{trib}Aliq")
                sub(g, "CST", cst_t)
                sub(g, "vBC", fmt(base_t))
                sub(g, f"p{trib}", fmt(aliq_t, 4))
                sub(g, f"v{trib}", fmt(valor_t))
            elif cst_t in ("04", "05", "06", "07", "08", "09"):
                sub(sub(el, f"{trib}NT"), "CST", cst_t)
            else:
                g = sub(el, f"{trib}Outr")
                sub(g, "CST", cst_t)
                sub(g, "vBC", fmt(base_t))
                sub(g, f"p{trib}", fmt(aliq_t, 4))
                sub(g, f"v{trib}", fmt(valor_t))
            tot[f"v{trib}"] += valor_t

        if it.get("CSTIBSCBSCOD"):
            ib = sub(imp, "IBSCBS")
            sub(ib, "CST", it["CSTIBSCBSCOD"])
            sub(ib, "cClassTrib", it["CLATRBCOD"])
            g = sub(ib, "gIBSCBS")
            sub(g, "vBC", fmt(it["INFBCIBSCBS"]))
            uf = sub(g, "gIBSUF")
            sub(uf, "pIBSUF", fmt(it["INFALQIBSUF"]))
            sub(uf, "vIBSUF", fmt(it["INFVLRIBSUF"]))
            mun = sub(g, "gIBSMun")
            sub(mun, "pIBSMun", "0.00")
            sub(mun, "vIBSMun", "0.00")
            sub(g, "vIBS", fmt(it["INFVLRIBSUF"]))
            cbs = sub(g, "gCBS")
            sub(cbs, "pCBS", fmt(it["INFALQCBS"]))
            sub(cbs, "vCBS", fmt(it["INFVLRCBS"]))

    # totais
    total = sub(inf, "total")
    it_tot = sub(total, "ICMSTot")
    v_outro = dec(n["NFSVLROUTRAS"]) + dec(n["NFSVLRACR"])
    for tag, val in [
        ("vBC", n["NFSVLRBASEICMS"]), ("vICMS", n["NFSVLRICMS"]), ("vICMSDeson", 0),
        ("vFCP", tot["vFCP"]), ("vBCST", n["NFSBASSUBS"]), ("vST", n["NFSVLRSUBS"]),
        ("vFCPST", n["NFSICMFCPST"]), ("vFCPSTRet", 0), ("vProd", tot["vProd"]),
        ("vFrete", n["NFSVLRFRT"]), ("vSeg", n["NFSVLRSEG"]), ("vDesc", n["NFSDCN"]),
        ("vII", 0), ("vIPI", n["NFSVLRIPI"]), ("vIPIDevol", 0),
        ("vPIS", tot["vPIS"]), ("vCOFINS", tot["vCOFINS"]), ("vOutro", v_outro),
        ("vNF", n["NFSVLR"]),
    ]:
        sub(it_tot, tag, fmt(val))
    if ibpt is not None and not ibpt_sem:
        sub(it_tot, "vTotTrib", fmt(tot["vTotTrib"]))
    soma = (tot["vProd"] - dec(n["NFSDCN"]) + dec(n["NFSVLRSUBS"]) + dec(n["NFSVLRFRT"])
            + dec(n["NFSVLRSEG"]) + v_outro + dec(n["NFSVLRIPI"]) + dec(n["NFSICMFCPST"]))
    if soma.quantize(Decimal("0.01")) != dec(n["NFSVLR"]).quantize(Decimal("0.01")):
        avisos.append(f"Valor total da nota ({fmt(n['NFSVLR'])}) difere da soma das parcelas ({fmt(soma)}).")
    if n.get("NFSBCIBSCBS") is not None:
        ibt = sub(total, "IBSCBSTot")
        sub(ibt, "vBCIBSCBS", fmt(n["NFSBCIBSCBS"]))
        gi = sub(ibt, "gIBS")
        guf = sub(gi, "gIBSUF")
        sub(guf, "vIBSUF", fmt(n["NFSVLRIBSUF"]))
        sub(gi, "vIBS", fmt(n["NFSVLRIBS"]))
        gc = sub(ibt, "gCBS")
        sub(gc, "vCBS", fmt(n["NFSVLRCBS"]))

    # transporte
    tr = sub(inf, "transp")
    frete = (n["NFSCIFFOB"] or "").strip().upper()
    sub(tr, "modFrete", {"C": "0", "F": "1", "T": "2"}.get(frete, frete if frete.isdigit() else "9"))
    t = dados["transp"]
    if t:
        doc_t = so_digitos(t.get("FORCGC"))
        g = sub(tr, "transporta")
        sub(g, "CPF" if len(doc_t) == 11 else "CNPJ", doc_t)
        sub(g, "xNome", t.get("FORDES"))
        sub(g, "IE", so_digitos(t.get("FORCGF")))
        sub(g, "xEnder", " ".join(x for x in (t.get("FOREND"), t.get("FORNUM")) if x))
        sub(g, "xMun", t.get("FORCID"))
        sub(g, "UF", t.get("FOREST"))
    if n["NFSPLC"]:
        m.grupo(tr, "veicTransp", [("placa", n["NFSPLC"]), ("UF", n["NFSPLCEST"])])
    if any(dec(n[c]) > 0 for c in ("NFSQTD", "NFSPESBRT", "NFSPESLIQ")) or n["NFSESP"]:
        m.grupo(tr, "vol", [
            ("qVol", int(dec(n["NFSQTD"])) or None), ("esp", n["NFSESP"]), ("marca", n["NFSMARCA"]),
            ("pesoL", fmt(n["NFSPESLIQ"], 3)), ("pesoB", fmt(n["NFSPESBRT"], 3)),
        ])

    # cobrança: nota a prazo (P) ou à vista (V) tem fatura; sem pagamento (N)
    # e devolução (finalidade 4) não têm. O SysPDV não lista duplicatas no XML
    # (em 177 de 178 notas conferidas), só a fatura.
    tem_fatura = (n.get("NFSTIPPAGTO") or "").strip() in ("P", "V") and (n["NFSFINNFE"] or "1") != "4"
    if tem_fatura:
        cobr = sub(inf, "cobr")
        m.grupo(cobr, "fat", [("nFat", f"{int(n['NFSNUM']):06d}"), ("vOrig", fmt(n["NFSVLR"])),
                              ("vDesc", "0.00"), ("vLiq", fmt(n["NFSVLR"]))])

    # informações complementares; o modelo "Val Aprox Tributos ... R$ 0,00" que
    # o SysPDV grava na observação recebe os valores, como na transmissão
    obs = [n[f"NFSOBS{k}"] for k in range(1, 7)] + [n["NFSOBSERVACAO"]]
    texto = " ".join(o.strip() for o in obs if o and o.strip())
    if ibpt is not None and not ibpt_sem and dec(n["NFSVLR"]) > 0:
        vnf = dec(n["NFSVLR"])
        novo = (f"Val Aprox Tributos Federais R$ {moeda_br(tot['F'])} ({moeda_br(tot['F'] * 100 / vnf)}%) "
                f"Val Aprox Tributos Estaduais R$ {moeda_br(tot['E'])} ({moeda_br(tot['E'] * 100 / vnf)}%) Fonte: IBPT")
        texto = RE_TEXTO_IBPT.sub(novo, texto)
    if ibpt_sem:
        avisos.append("Sem % do IBPT para o(s) NCM " + ", ".join(sorted(ibpt_sem))
                      + ": tributos aproximados não calculados.")
    # o que o SysPDV acrescenta na transmissão, antes da observação
    prefixos = []
    if devolucao:
        prefixos.append(f"Valor do IPI: R$ {dec(n['NFSVLRIPI']):.2f}")
        prefixos += [f"Nota Ref.: {c}" for c in dados.get("chaves_ref", []) if c]
    if tot["vFCP"] > 0:
        prefixos.append(f"Valor Total FCP: R$ {tot['vFCP']:.2f}")
    texto = limpar_texto(" ".join(prefixos + [texto]))
    if aviso:
        if ibpt_estimado:  # o PDF também avisa (o modo automático não mostra avisos na tela)
            aviso += " (TRIBUTOS APROXIMADOS ESTIMADOS PARA NCM " + ", ".join(sorted(ibpt_estimado)) + ")"
        texto = f"{aviso} {texto}".strip()
    if texto:
        sub(sub(inf, "infAdic"), "infCpl", texto)

    xml = ET.tostring(raiz, encoding="unicode")
    return '<?xml version="1.0" encoding="UTF-8"?>' + xml, chave, avisos
