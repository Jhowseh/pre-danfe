import re
import unicodedata
import xml.etree.ElementTree as ET
from datetime import datetime, time
from decimal import ROUND_HALF_DOWN, ROUND_HALF_UP, Decimal

import approx_taxes
from database import rows_as_dicts

NS = "http://www.portalfiscal.inf.br/nfe"
ZERO = Decimal("0")
BLOCK = object()

SQL_INVOICE = """
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
       IIF(NFSXMLEMINFE IS NULL, 'N', 'S') AS HAS_XML
  FROM NOTAFISCAL
 WHERE NFSCTR = ?
"""

SQL_ITEMS = """
SELECT I.INFSEQ, I.PROCOD, I.INFPRODES, NULLIF(TRIM(I.INFNCM), '') AS INFNCM, P.PRONCM,
       I.CFOCOD, I.INFUND,
       COALESCE(U.UNDPAD, I.INFUND) AS UNIT, P.PROCEST,
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

SQL_ISSUER = """
SELECT FIRST 1 PRPDES, PRPFAN, PRPCGC, PRPIERG, PRPINCMUN, PRPEND, PRPNUM, PRPCMP,
       PRPBAI, PRPMUN, PRPCODIBGE, PRPUF, PRPCEP, PRPTEL, PRPCRT, PRPREGFED
  FROM PROPRIO ORDER BY PRPCOD
"""

SQL_CUSTOMER = "SELECT CLICODIGOIBGE, CLIEMAIL FROM CLIENTE WHERE CLICOD = ?"
SQL_STATE_CITIES = "SELECT CODIBGE, CODIBGECID FROM FISCO_CODIGOIBGE WHERE CODIBGEUF = ?"

STATE_CODES = {
    "RO": "11", "AC": "12", "AM": "13", "RR": "14", "PA": "15", "AP": "16", "TO": "17",
    "MA": "21", "PI": "22", "CE": "23", "RN": "24", "PB": "25", "PE": "26", "AL": "27",
    "SE": "28", "BA": "29", "MG": "31", "ES": "32", "RJ": "33", "SP": "35", "PR": "41",
    "SC": "42", "RS": "43", "MS": "50", "MT": "51", "GO": "52", "DF": "53",
}
SQL_CFOP = "SELECT CFODES FROM CFOP WHERE CFOCOD = ?"
SQL_CARRIER = """
SELECT FORDES, FORCGC, FORCGF, FOREND, FORNUM, FORCID, FOREST FROM FORNECEDOR WHERE FORCOD = ?
"""
SQL_REFERENCES = """
SELECT NFRFORCOD, NFRENTSER, NFRENTDOC, NFRENTTNF FROM NOTAFISCAL_REFERENCIA WHERE NFSCTR = ?
"""
SQL_REFERENCED_KEYS = "SELECT NFRCHVAVS FROM NOTAFISCAL_REFERENCIA WHERE NFSCTR = ? ORDER BY NFRSEQ"
SQL_INBOUND_NCM = """
SELECT FIRST 1 ITENCM FROM ITEM_ENTRADA
 WHERE FORCOD = ? AND ENTSER = ? AND ENTDOC = ? AND ENTTNF = ? AND PROCOD = ?
   AND COALESCE(TRIM(ITENCM), '') <> ''
"""


def _fetch_all(cur, sql, params=()):
    cur.execute(sql, params)
    return rows_as_dicts(cur)


def _fetch_one(cur, sql, params=()):
    rows = _fetch_all(cur, sql, params)
    return rows[0] if rows else {}


def _fetch_tuples(cur, sql, params=()):
    cur.execute(sql, params)
    return cur.fetchall()


def strip_accents(s):
    return unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().upper().strip()


def city_code(cur, city, state, fallback=None):
    if state in STATE_CODES and city:
        target = strip_accents(city)
        for code, name in _fetch_tuples(cur, SQL_STATE_CITIES, (state,)):
            if strip_accents(name) == target:
                return STATE_CODES[state] + code.strip()
    return fallback


def load_invoice(cur, nfsctr, ibpt_table=None):
    invoice = _fetch_one(cur, SQL_INVOICE, (nfsctr,))
    if not invoice:
        raise ValueError(f"Nota NFSCTR={nfsctr} não encontrada.")
    customer = _fetch_one(cur, SQL_CUSTOMER, (invoice["CLICOD"],)) if invoice["CLICOD"] else {}
    customer["CMUN"] = city_code(cur, invoice["NFSCLICID"], invoice["NFSCLIEST"], customer.get("CLICODIGOIBGE"))

    references = _fetch_tuples(cur, SQL_REFERENCES, (nfsctr,))
    items = _fetch_all(cur, SQL_ITEMS, (nfsctr,))
    for item in items:
        if not item["INFNCM"]:
            for ref in references:
                found = _fetch_tuples(cur, SQL_INBOUND_NCM, (*ref, item["PROCOD"]))
                if found:
                    item["INFNCM"] = found[0][0].strip()
                    break
        item["INFNCM"] = item["INFNCM"] or item["PRONCM"]

    return {
        "invoice": invoice,
        "items": items,
        "issuer": _fetch_one(cur, SQL_ISSUER),
        "customer": customer,
        "cfop": _fetch_one(cur, SQL_CFOP, (invoice["CFOCOD"],)),
        "carrier": _fetch_one(cur, SQL_CARRIER, (invoice["FORCOD"],)) if invoice["FORCOD"] else {},
        "referenced_keys": [r[0].strip() for r in _fetch_tuples(cur, SQL_REFERENCED_KEYS, (nfsctr,))
                            if r[0] and r[0].strip()],
        "ibpt": ibpt_table if ibpt_table is not None else approx_taxes.current_table(cur),
    }


def dec(v):
    return Decimal(str(v)) if v is not None else ZERO


PIS_COFINS_RATES = {"R": (Decimal("1.65"), Decimal("7.60")),
                    "P": (Decimal("0.65"), Decimal("3.00"))}
IBPT_TEXT_RE = re.compile(r"Val Aprox Tributos Federais R\$ [\d.,]+(?: \([\d.,]+%\))?\s*"
                          r"Val Aprox Tributos Estaduais R\$ [\d.,]+(?: \([\d.,]+%\))?\s*Fonte: IBPT")


def brl(v):
    return f"{approx_taxes.round_cents(dec(v)):.2f}".replace(".", ",")


def clean_text(s):
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode()
    return " ".join(s.replace("-", " ").split())


def fmt(v, places=2):
    q = Decimal(1).scaleb(-places)
    return str(dec(v).quantize(q, rounding=ROUND_HALF_UP))


def digits_only(s):
    return re.sub(r"\D", "", s or "")


def date_time(d, t):
    if d is None:
        return None
    day = d.date() if isinstance(d, datetime) else d
    hour = t if isinstance(t, time) else time(0, 0)
    return datetime.combine(day, hour.replace(microsecond=0)).isoformat() + "-03:00"


def key_check_digit(key43):
    total, weight = 0, 2
    for c in reversed(key43):
        total += int(c) * weight
        weight = 2 if weight == 9 else weight + 1
    remainder = total % 11
    return 0 if remainder < 2 else 11 - remainder


def access_key(cuf, issued_at, cnpj, series, number, cnf, model="55", emission_type="1"):
    base = (f"{cuf}{issued_at:%y%m}{cnpj:0>14}{model}{int(series):03d}{int(number):09d}"
            f"{emission_type}{int(cnf):08d}")
    return base + str(key_check_digit(base))


class _Builder:
    def __init__(self):
        ET.register_namespace("", NS)

    @staticmethod
    def sub(parent, tag, text=BLOCK, required=False, **attrs):
        if text is BLOCK:
            return ET.SubElement(parent, f"{{{NS}}}{tag}", attrs)
        if text in (None, "") and not required:
            return None
        el = ET.SubElement(parent, f"{{{NS}}}{tag}", attrs)
        if text not in (None, ""):
            el.text = str(text)
        return el

    def group(self, parent, tag, fields):
        if not any(v not in (None, "") for _, v in fields):
            return None
        g = ET.SubElement(parent, f"{{{NS}}}{tag}")
        for t, v in fields:
            self.sub(g, t, v)
        return g


def build_xml(data, notice=None):
    n, issuer, customer = data["invoice"], data["issuer"], data["customer"]
    b = _Builder()
    sub = b.sub
    warnings = []

    cuf = (issuer.get("PRPCODIBGE") or "25")[:2]
    issued_at = n["NFSDATEMI"] or datetime.now()
    cnf = int(n["NFSCTR"])
    cnpj = digits_only(issuer["PRPCGC"])
    key = access_key(cuf, issued_at, cnpj, n["NFSSER"], n["NFSNUM"], cnf)
    if n.get("NFSCHVNFE") and n["NFSCHVNFE"].strip() != key:
        warnings.append(f"Chave gravada no banco ({n['NFSCHVNFE'].strip()}) difere da calculada ({key}).")

    root = ET.Element(f"{{{NS}}}NFe")
    inf = sub(root, "infNFe", Id=f"NFe{key}", versao="4.00")

    invoice_cfop = (n["CFOCOD"] or "").strip()[:4]
    dest_state = n["NFSCLIEST"] or ""
    dest_doc = digits_only(n["NFSCLICPFCGC"])
    dest_ie = digits_only(n["NFSCLIRGCGF"]) if (n["NFSCLIRGCGF"] or "").upper() != "ISENTO" else ""
    ide = sub(inf, "ide")
    for tag, val in [
        ("cUF", cuf), ("cNF", f"{cnf:08d}"),
        ("natOp", (data["cfop"].get("CFODES") or "")[:60]),
        ("mod", "55"), ("serie", int(n["NFSSER"])), ("nNF", int(n["NFSNUM"])),
        ("dhEmi", date_time(n["NFSDATEMI"], n["NFSHORSAI"])),
        ("dhSaiEnt", date_time(n["NFSDATSAI"], n["NFSHORSAI"])),
        ("tpNF", "0" if invoice_cfop[:1] in ("1", "2", "3") else "1"),
        ("idDest", "3" if invoice_cfop[:1] in ("3", "7") else ("1" if dest_state == issuer["PRPUF"] else "2")),
        ("cMunFG", issuer["PRPCODIBGE"]), ("tpImp", "1"), ("tpEmis", "1"), ("cDV", key[-1]),
        ("tpAmb", n["NFSAMBNFE"] or "1"), ("finNFe", n["NFSFINNFE"] or "1"),
        ("indFinal", "1" if len(dest_doc) == 11 or not dest_ie else "0"),
        ("indPres", "1"), ("procEmi", "0"), ("verProc", "PreDanfe"),
    ]:
        sub(ide, tag, val)

    em = sub(inf, "emit")
    sub(em, "CNPJ", cnpj)
    sub(em, "xNome", issuer["PRPDES"])
    sub(em, "xFant", issuer["PRPFAN"])
    b.group(em, "enderEmit", [
        ("xLgr", issuer["PRPEND"]), ("nro", issuer["PRPNUM"]), ("xCpl", issuer["PRPCMP"]),
        ("xBairro", issuer["PRPBAI"]), ("cMun", issuer["PRPCODIBGE"]), ("xMun", issuer["PRPMUN"]),
        ("UF", issuer["PRPUF"]), ("CEP", digits_only(issuer["PRPCEP"])), ("cPais", "1058"),
        ("xPais", "BRASIL"), ("fone", digits_only(issuer["PRPTEL"])),
    ])
    sub(em, "IE", digits_only(issuer["PRPIERG"]))
    sub(em, "IM", issuer.get("PRPINCMUN"))
    sub(em, "CRT", issuer["PRPCRT"] or "3")

    de = sub(inf, "dest")
    sub(de, "CPF" if len(dest_doc) == 11 else "CNPJ", dest_doc)
    sub(de, "xNome", n["NFSCLIDES"])
    b.group(de, "enderDest", [
        ("xLgr", n["NFSCLIEND"]), ("nro", n["NFSCLINUM"] or "SN"), ("xCpl", n["NFSCLICMP"]),
        ("xBairro", n["NFSCLIBAI"]), ("cMun", customer.get("CMUN")), ("xMun", n["NFSCLICID"]),
        ("UF", dest_state), ("CEP", digits_only(n["NFSCLICEP"])), ("cPais", "1058"),
        ("xPais", "BRASIL"), ("fone", digits_only(n["NFSCLITEL"])),
    ])
    sub(de, "indIEDest", "1" if dest_ie else "9")
    sub(de, "IE", dest_ie)

    tot = {k: ZERO for k in ("vProd", "vPIS", "vCOFINS", "vFCP", "vTotTrib", "F", "E")}
    simples_nacional = (issuer["PRPCRT"] or "3") in ("1", "2")
    regime_rates = PIS_COFINS_RATES.get((issuer.get("PRPREGFED") or "").strip())
    is_return = (n["NFSFINNFE"] or "1") == "4"
    ibpt = None if is_return else data.get("ibpt")
    ibpt_estimated, ibpt_missing = set(), set()
    for i, it in enumerate(data["items"], start=1):
        det = sub(inf, "det", nItem=str(i))
        pr = sub(det, "prod")
        procod = (it["PROCOD"] or "").strip()
        v_prod = (dec(it["INFQTDEMB"]) * dec(it["INFVLREMB"])).quantize(Decimal("0.01"), ROUND_HALF_UP)
        for tag, val in [
            ("cProd", procod[-13:]), ("cEAN", "SEM GTIN"), ("xProd", it["INFPRODES"]),
            ("NCM", it["INFNCM"]), ("CEST", it["PROCEST"]), ("CFOP", (it["CFOCOD"] or "")[:4]),
            ("uCom", it["UNIT"]), ("qCom", fmt(it["INFQTDEMB"], 3)),
            ("vUnCom", fmt(it["INFVLREMB"], 8)), ("vProd", fmt(v_prod)),
            ("cEANTrib", "SEM GTIN"), ("uTrib", it["UNIT"]), ("qTrib", fmt(it["INFQTDEMB"], 3)),
            ("vUnTrib", fmt(it["INFVLREMB"], 10)),
        ]:
            sub(pr, tag, val)
        for tag, field in (("vFrete", "INFVLRFRT"), ("vSeg", "INFVLRSEG"),
                           ("vDesc", "INFVLRDCN"), ("vOutro", "INFVLROUTRAS")):
            if dec(it[field]) > 0:
                sub(pr, tag, fmt(it[field]))
        sub(pr, "indTot", "1")
        tot["vProd"] += v_prod
        net = v_prod - dec(it["INFVLRDCN"]).quantize(Decimal("0.01"), ROUND_HALF_UP)
        if net != dec(it["INFVLRTOT"]):
            warnings.append(f"Item {i}: quantidade x unitário - desconto = {net}, "
                            f"mas o total gravado é {fmt(it['INFVLRTOT'])}.")

        tax = sub(det, "imposto")
        orig, cst = it["INFTABA"] or "0", (it["INFTABB"] or "").strip()
        if ibpt is not None:
            ncm = (it["INFNCM"] or "").strip()
            imported = orig.strip() in ("1", "2", "3", "8")
            f, e, source = ibpt.rate(ncm, imported)
            if f is None:
                ibpt_missing.add(ncm)
            else:
                if source == "file":
                    ibpt_estimated.add(ncm)
                v_tt = approx_taxes.item_value(net, f, e)
                sub(tax, "vTotTrib", fmt(v_tt))
                tot["vTotTrib"] += v_tt
                ft, et, _ = ibpt.rate(ncm, imported, text=True)
                tot["F"] += approx_taxes.round_cents(net * ft / 100)
                tot["E"] += approx_taxes.round_cents(net * et / 100)
        icms = sub(tax, "ICMS")
        if simples_nacional:
            g = sub(icms, f"ICMSSN{(it['INFCSOSN'] or '102').strip()}", required=True)
            sub(g, "orig", orig)
            sub(g, "CSOSN", (it["INFCSOSN"] or "").strip())
        else:
            group_name = {"40": "40", "41": "40", "50": "40"}.get(cst, cst or "90")
            g = sub(icms, f"ICMS{group_name}", required=True)
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
            ipi = sub(tax, "IPI")
            sub(ipi, "cEnq", "999")
            gi = sub(ipi, "IPITrib")
            sub(gi, "CST", "50")
            base = dec(it["INFBASEIPI"])
            sub(gi, "vBC", fmt(base))
            sub(gi, "pIPI", fmt(dec(it["INFVLRIPI"]) * 100 / base if base else 0))
            sub(gi, "vIPI", fmt(it["INFVLRIPI"]))

        for index, (tax_name, prefix) in enumerate((("PIS", "PIS"), ("COFINS", "COFINS"))):
            tax_cst = (it[f"INFCST{prefix}"] or "").strip() or "99"
            tax_base, tax_rate, tax_value = (dec(it[f"INFBASE{prefix}"]), dec(it[f"INFALQ{prefix}"]),
                                             dec(it[f"INFVLR{prefix}"]))
            if tax_cst in ("01", "02"):
                if tax_cst == "01" and regime_rates:
                    tax_rate = regime_rates[index]
                tax_value = (tax_base * tax_rate / 100).quantize(Decimal("0.01"), ROUND_HALF_DOWN)
            el = sub(tax, tax_name)
            if tax_cst in ("01", "02"):
                g = sub(el, f"{tax_name}Aliq")
                sub(g, "CST", tax_cst)
                sub(g, "vBC", fmt(tax_base))
                sub(g, f"p{tax_name}", fmt(tax_rate, 4))
                sub(g, f"v{tax_name}", fmt(tax_value))
            elif tax_cst in ("04", "05", "06", "07", "08", "09"):
                sub(sub(el, f"{tax_name}NT"), "CST", tax_cst)
            else:
                g = sub(el, f"{tax_name}Outr")
                sub(g, "CST", tax_cst)
                sub(g, "vBC", fmt(tax_base))
                sub(g, f"p{tax_name}", fmt(tax_rate, 4))
                sub(g, f"v{tax_name}", fmt(tax_value))
            tot[f"v{tax_name}"] += tax_value

        if it.get("CSTIBSCBSCOD"):
            ib = sub(tax, "IBSCBS")
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

    total = sub(inf, "total")
    icms_tot = sub(total, "ICMSTot")
    v_other = dec(n["NFSVLROUTRAS"]) + dec(n["NFSVLRACR"])
    for tag, val in [
        ("vBC", n["NFSVLRBASEICMS"]), ("vICMS", n["NFSVLRICMS"]), ("vICMSDeson", 0),
        ("vFCP", tot["vFCP"]), ("vBCST", n["NFSBASSUBS"]), ("vST", n["NFSVLRSUBS"]),
        ("vFCPST", n["NFSICMFCPST"]), ("vFCPSTRet", 0), ("vProd", tot["vProd"]),
        ("vFrete", n["NFSVLRFRT"]), ("vSeg", n["NFSVLRSEG"]), ("vDesc", n["NFSDCN"]),
        ("vII", 0), ("vIPI", n["NFSVLRIPI"]), ("vIPIDevol", 0),
        ("vPIS", tot["vPIS"]), ("vCOFINS", tot["vCOFINS"]), ("vOutro", v_other),
        ("vNF", n["NFSVLR"]),
    ]:
        sub(icms_tot, tag, fmt(val))
    if ibpt is not None and not ibpt_missing:
        sub(icms_tot, "vTotTrib", fmt(tot["vTotTrib"]))
    parts_sum = (tot["vProd"] - dec(n["NFSDCN"]) + dec(n["NFSVLRSUBS"]) + dec(n["NFSVLRFRT"])
                 + dec(n["NFSVLRSEG"]) + v_other + dec(n["NFSVLRIPI"]) + dec(n["NFSICMFCPST"]))
    if parts_sum.quantize(Decimal("0.01")) != dec(n["NFSVLR"]).quantize(Decimal("0.01")):
        warnings.append(f"Valor total da nota ({fmt(n['NFSVLR'])}) difere da soma das parcelas ({fmt(parts_sum)}).")
    if n.get("NFSBCIBSCBS") is not None:
        ibt = sub(total, "IBSCBSTot")
        sub(ibt, "vBCIBSCBS", fmt(n["NFSBCIBSCBS"]))
        gi = sub(ibt, "gIBS")
        guf = sub(gi, "gIBSUF")
        sub(guf, "vIBSUF", fmt(n["NFSVLRIBSUF"]))
        sub(gi, "vIBS", fmt(n["NFSVLRIBS"]))
        gc = sub(ibt, "gCBS")
        sub(gc, "vCBS", fmt(n["NFSVLRCBS"]))

    tr = sub(inf, "transp")
    freight = (n["NFSCIFFOB"] or "").strip().upper()
    sub(tr, "modFrete", {"C": "0", "F": "1", "T": "2"}.get(freight, freight if freight.isdigit() else "9"))
    carrier = data["carrier"]
    if carrier:
        carrier_doc = digits_only(carrier.get("FORCGC"))
        g = sub(tr, "transporta")
        sub(g, "CPF" if len(carrier_doc) == 11 else "CNPJ", carrier_doc)
        sub(g, "xNome", carrier.get("FORDES"))
        sub(g, "IE", digits_only(carrier.get("FORCGF")))
        sub(g, "xEnder", " ".join(x for x in (carrier.get("FOREND"), carrier.get("FORNUM")) if x))
        sub(g, "xMun", carrier.get("FORCID"))
        sub(g, "UF", carrier.get("FOREST"))
    if n["NFSPLC"]:
        b.group(tr, "veicTransp", [("placa", n["NFSPLC"]), ("UF", n["NFSPLCEST"])])
    if any(dec(n[c]) > 0 for c in ("NFSQTD", "NFSPESBRT", "NFSPESLIQ")) or n["NFSESP"]:
        b.group(tr, "vol", [
            ("qVol", int(dec(n["NFSQTD"])) or None), ("esp", n["NFSESP"]), ("marca", n["NFSMARCA"]),
            ("pesoL", fmt(n["NFSPESLIQ"], 3)), ("pesoB", fmt(n["NFSPESBRT"], 3)),
        ])

    has_bill = (n.get("NFSTIPPAGTO") or "").strip() in ("P", "V") and (n["NFSFINNFE"] or "1") != "4"
    if has_bill:
        cobr = sub(inf, "cobr")
        b.group(cobr, "fat", [("nFat", f"{int(n['NFSNUM']):06d}"), ("vOrig", fmt(n["NFSVLR"])),
                              ("vDesc", "0.00"), ("vLiq", fmt(n["NFSVLR"]))])

    notes = [n[f"NFSOBS{k}"] for k in range(1, 7)] + [n["NFSOBSERVACAO"]]
    text = " ".join(o.strip() for o in notes if o and o.strip())
    if ibpt is not None and not ibpt_missing and dec(n["NFSVLR"]) > 0:
        vnf = dec(n["NFSVLR"])
        ibpt_text = (f"Val Aprox Tributos Federais R$ {brl(tot['F'])} ({brl(tot['F'] * 100 / vnf)}%) "
                     f"Val Aprox Tributos Estaduais R$ {brl(tot['E'])} ({brl(tot['E'] * 100 / vnf)}%) Fonte: IBPT")
        text = IBPT_TEXT_RE.sub(ibpt_text, text)
    if ibpt_missing:
        warnings.append("Sem % do IBPT para o(s) NCM " + ", ".join(sorted(ibpt_missing))
                        + ": tributos aproximados não calculados.")
    prefixes = []
    if is_return:
        prefixes.append(f"Valor do IPI: R$ {dec(n['NFSVLRIPI']):.2f}")
        prefixes += [f"Nota Ref.: {k}" for k in data.get("referenced_keys", []) if k]
    if tot["vFCP"] > 0:
        prefixes.append(f"Valor Total FCP: R$ {tot['vFCP']:.2f}")
    text = clean_text(" ".join(prefixes + [text]))
    if notice:
        if ibpt_estimated:
            notice += " (TRIBUTOS APROXIMADOS ESTIMADOS PARA NCM " + ", ".join(sorted(ibpt_estimated)) + ")"
        text = f"{notice} {text}".strip()
    if text:
        sub(sub(inf, "infAdic"), "infCpl", text)

    xml = ET.tostring(root, encoding="unicode")
    return '<?xml version="1.0" encoding="UTF-8"?>' + xml, key, warnings
