import argparse
import xml.etree.ElementTree as ET
from collections import Counter
from decimal import Decimal, InvalidOperation
from pathlib import Path

import approx_taxes
from database import read_only_connection
from nfe_xml import NS, build_xml, load_invoice

DESCRIPTION = "Confere o montador de XML contra as notas já autorizadas (somente leitura)."

N = f"{{{NS}}}"

IDE_FIELDS = ["natOp", "serie", "nNF", "tpNF", "idDest", "finNFe", "indFinal"]
TOTAL_FIELDS = ["vBC", "vICMS", "vBCST", "vST", "vProd", "vFrete", "vSeg", "vDesc",
                "vIPI", "vPIS", "vCOFINS", "vOutro", "vNF", "vTotTrib"]
PROD_FIELDS = ["cProd", "xProd", "NCM", "CFOP", "uCom", "qCom", "vUnCom", "vProd", "vDesc"]
ICMS_FIELDS = ["orig", "CST", "CSOSN", "vBC", "pICMS", "vICMS", "vBCST", "vICMSST"]


def text_of(el, path):
    if el is None:
        return None
    found = el.find(path)
    return found.text.strip() if found is not None and found.text else None


def same(a, b):
    if a == b:
        return True
    try:
        return Decimal(a or "0") == Decimal(b or "0")
    except InvalidOperation:
        return (a or "").strip().upper() == (b or "").strip().upper()


def compare(official, built):
    o, m = ET.fromstring(official), ET.fromstring(built)
    diffs = []
    inf_o, inf_m = o.find(f".//{N}infNFe"), m.find(f".//{N}infNFe")
    if inf_o.get("Id") != inf_m.get("Id"):
        diffs.append(("chave", inf_o.get("Id"), inf_m.get("Id")))
    for c in IDE_FIELDS:
        a, b = text_of(o, f".//{N}ide/{N}{c}"), text_of(m, f".//{N}ide/{N}{c}")
        if not same(a, b):
            diffs.append((f"ide/{c}", a, b))
    a, b = (text_of(o, f".//{N}ide/{N}dhEmi") or "")[:10], (text_of(m, f".//{N}ide/{N}dhEmi") or "")[:10]
    if a != b:
        diffs.append(("ide/dhEmi(data)", a, b))
    for c in ("CNPJ", "CPF", "xNome", "IE", "indIEDest", "enderDest/" + N + "cMun"):
        a, b = text_of(o, f".//{N}dest/{N}{c}"), text_of(m, f".//{N}dest/{N}{c}")
        if not same(a, b):
            diffs.append((f"dest/{c.replace(N, '')}", a, b))
    for c in TOTAL_FIELDS:
        a, b = text_of(o, f".//{N}ICMSTot/{N}{c}"), text_of(m, f".//{N}ICMSTot/{N}{c}")
        if not same(a, b):
            diffs.append((f"total/{c}", a, b))
    a, b = text_of(o, f".//{N}transp/{N}modFrete"), text_of(m, f".//{N}transp/{N}modFrete")
    if not same(a, b):
        diffs.append(("transp/modFrete", a, b))
    a, b = o.find(f".//{N}cobr/{N}fat") is not None, m.find(f".//{N}cobr/{N}fat") is not None
    if a != b:
        diffs.append(("cobr/fat existe", str(a), str(b)))
    a, b = len(o.findall(f".//{N}cobr/{N}dup")), len(m.findall(f".//{N}cobr/{N}dup"))
    if a != b:
        diffs.append(("cobr/duplicatas", str(a), str(b)))
    a, b = text_of(o, f".//{N}infAdic/{N}infCpl"), text_of(m, f".//{N}infAdic/{N}infCpl")
    if " ".join((a or "").split()) != " ".join((b or "").split()):
        diffs.append(("infCpl (texto)", a, b))

    dets_o, dets_m = o.findall(f".//{N}det"), m.findall(f".//{N}det")
    if len(dets_o) != len(dets_m):
        diffs.append(("qtd itens", str(len(dets_o)), str(len(dets_m))))
    for do, dm in zip(dets_o, dets_m):
        for c in PROD_FIELDS:
            a, b = text_of(do, f"{N}prod/{N}{c}"), text_of(dm, f"{N}prod/{N}{c}")
            if not same(a, b):
                diffs.append((f"item/prod/{c}", a, b))
        icms_o, icms_m = do.find(f"{N}imposto/{N}ICMS")[0], dm.find(f"{N}imposto/{N}ICMS")[0]
        for c in ICMS_FIELDS:
            a, b = text_of(icms_o, f"{N}{c}"), text_of(icms_m, f"{N}{c}")
            if not same(a, b):
                diffs.append((f"item/ICMS/{c}", a, b))
        for path in ("vTotTrib", "PIS/*/vPIS", "PIS/*/pPIS", "COFINS/*/vCOFINS", "COFINS/*/pCOFINS"):
            sel = f"{N}imposto/" + "/".join(f"{N}{p}" if p != "*" else "*" for p in path.split("/"))
            a, b = text_of(do, sel), text_of(dm, sel)
            if not same(a, b):
                diffs.append((f"item/{path.replace('/*', '')}", a, b))
    return diffs


def compare_before_after(before_file, number):
    if not number:
        raise SystemExit("Informe também --number.")
    with read_only_connection() as cur:
        cur.execute("SELECT NFSXMLEMINFE FROM NOTAFISCAL WHERE NFSTIP <> 'CAN' "
                    "AND TRIM(LEADING '0' FROM TRIM(NFSNUM)) = ?", (str(int(number)),))
        row = cur.fetchone()
        blob = row[0] if row else None
        if blob is None:
            raise SystemExit(f"A nota {number} ainda não tem XML oficial (não foi transmitida).")
        official = blob.read() if hasattr(blob, "read") else blob
    official = official.decode("utf-8") if isinstance(official, bytes) else official
    diffs = compare(official, before_file.read_text(encoding="utf-8"))
    if not diffs:
        print("Nenhuma diferença nos campos comparados: o pré-DANFE bateu com o DANFE final.")
    for field, a, b in diffs:
        print(f"  {field:<22} final={a!r}  pre-DANFE={b!r}")


def main():
    ap = argparse.ArgumentParser(description=DESCRIPTION)
    ap.add_argument("--latest", type=int, help="só as N notas mais recentes")
    ap.add_argument("--detail", action="store_true", help="mostra cada divergência de cada nota")
    ap.add_argument("--before", help="XML salvo pelo predanfe.py --xml ANTES da transmissão")
    ap.add_argument("--number", help="com --before: número da nota, agora já transmitida")
    args = ap.parse_args()

    if args.before:
        compare_before_after(Path(args.before), args.number)
        return

    summary, by_invoice = Counter(), {}
    with read_only_connection() as cur:
        cur.execute("""SELECT NFSCTR, NFSNUM, NFSDATAUT, NFSFINNFE, NFSXMLEMINFE FROM NOTAFISCAL
                       WHERE NFSXMLEMINFE IS NOT NULL AND NFSTIP <> 'CAN'
                       ORDER BY NFSDATAUT DESC, NFSNUM DESC""")
        invoices = []
        for ctr, num, authorized_at, purpose, blob in cur.fetchall():
            data = blob.read() if hasattr(blob, "read") else blob
            xml = data.decode("utf-8") if isinstance(data, bytes) else data
            invoices.append({"NFSCTR": ctr, "NFSNUM": num, "authorized_at": authorized_at, "purpose": purpose,
                             "xml": xml, "ibpt": approx_taxes.parse_invoice_xml(xml)})
        cur.execute("SELECT FIRST 1 PRPVERARQIBPT FROM PROPRIO")
        ibpt_file = approx_taxes.read_ibpt_file((cur.fetchone()[0] or "").strip())
        for i, inv in enumerate(invoices[: args.latest] if args.latest else invoices):
            official = inv["xml"]
            earlier = [a["ibpt"] for a in invoices[i + 1:] if a["purpose"] != "4"]
            table = approx_taxes.IBPTTable(earlier, ibpt_file)
            try:
                built, _, _ = build_xml(load_invoice(cur, inv["NFSCTR"], table))
                diffs = compare(official, built)
            except Exception as e:
                diffs = [("ERRO", type(e).__name__, str(e))]
            by_invoice[int(inv["NFSNUM"])] = diffs
            for field, _, _ in diffs:
                summary[field] += 1

    ok = sum(1 for d in by_invoice.values() if not d)
    print(f"\n{len(by_invoice)} notas conferidas: {ok} idênticas nos campos comparados, "
          f"{len(by_invoice) - ok} com diferença.\n")
    if summary:
        print("Campos com diferença (nº de ocorrências):")
        for field, count in summary.most_common():
            example = next((num, a, b) for num, d in by_invoice.items() for c, a, b in d if c == field)
            print(f"  {field:<22} {count:>4}   ex.: nota {example[0]}  oficial={example[1]!r}  "
                  f"montado={example[2]!r}")
    if args.detail:
        for num, diffs in by_invoice.items():
            if diffs:
                print(f"\nNota {num}:")
                for field, a, b in diffs:
                    print(f"  {field:<22} oficial={a!r}  montado={b!r}")


if __name__ == "__main__":
    main()
