"""Confere o montador de XML contra as notas JÁ AUTORIZADAS (somente leitura).

Para cada nota com XML oficial gravado, monta o XML a partir das tabelas e
compara campo a campo com o oficial. Mostra o que diverge e um resumo.

Os valores que o SysPDV só calcula na transmissão (PIS/COFINS, tributos
aproximados/IBPT e o texto do IBPT) são recalculados como num pré-DANFE.
Os % do IBPT de cada nota são aprendidos só com as notas transmitidas ANTES
dela, para a conferência ser honesta.

  python validar.py            -> todas as notas autorizadas
  python validar.py --ultimas 20
  python validar.py --antes pdf\\PreDANFE_4194_....xml --numero 4194
        -> depois de transmitir: compara o pré-DANFE salvo com o XML final
"""
import argparse
import xml.etree.ElementTree as ET
from collections import Counter
from decimal import Decimal, InvalidOperation
from pathlib import Path

import tributos_aprox
from banco import conexao_leitura, linhas_dict
from nfe_xml import NS, carregar_nota, montar_xml

N = f"{{{NS}}}"

CAMPOS_IDE = ["natOp", "serie", "nNF", "tpNF", "idDest", "finNFe", "indFinal"]
CAMPOS_TOTAL = ["vBC", "vICMS", "vBCST", "vST", "vProd", "vFrete", "vSeg", "vDesc",
                "vIPI", "vPIS", "vCOFINS", "vOutro", "vNF", "vTotTrib"]
CAMPOS_PROD = ["cProd", "xProd", "NCM", "CFOP", "uCom", "qCom", "vUnCom", "vProd", "vDesc"]
CAMPOS_ICMS = ["orig", "CST", "CSOSN", "vBC", "pICMS", "vICMS", "vBCST", "vICMSST"]


def txt(el, caminho):
    if el is None:
        return None
    achado = el.find(caminho)
    return achado.text.strip() if achado is not None and achado.text else None


def iguais(a, b):
    if a == b:
        return True
    try:
        return Decimal(a or "0") == Decimal(b or "0")
    except InvalidOperation:
        return (a or "").strip().upper() == (b or "").strip().upper()


def comparar(oficial, montado):
    """Lista de (campo, oficial, montado) que diferem."""
    o, m = ET.fromstring(oficial), ET.fromstring(montado)
    dif = []
    inf_o, inf_m = o.find(f".//{N}infNFe"), m.find(f".//{N}infNFe")
    if inf_o.get("Id") != inf_m.get("Id"):
        dif.append(("chave", inf_o.get("Id"), inf_m.get("Id")))
    for c in CAMPOS_IDE:
        a, b = txt(o, f".//{N}ide/{N}{c}"), txt(m, f".//{N}ide/{N}{c}")
        if not iguais(a, b):
            dif.append((f"ide/{c}", a, b))
    a, b = (txt(o, f".//{N}ide/{N}dhEmi") or "")[:10], (txt(m, f".//{N}ide/{N}dhEmi") or "")[:10]
    if a != b:
        dif.append(("ide/dhEmi(data)", a, b))
    for c in ("CNPJ", "CPF", "xNome", "IE", "indIEDest", "enderDest/" + N + "cMun"):
        a, b = txt(o, f".//{N}dest/{N}{c}"), txt(m, f".//{N}dest/{N}{c}")
        if not iguais(a, b):
            dif.append((f"dest/{c.replace(N, '')}", a, b))
    for c in CAMPOS_TOTAL:
        a, b = txt(o, f".//{N}ICMSTot/{N}{c}"), txt(m, f".//{N}ICMSTot/{N}{c}")
        if not iguais(a, b):
            dif.append((f"total/{c}", a, b))
    a, b = txt(o, f".//{N}transp/{N}modFrete"), txt(m, f".//{N}transp/{N}modFrete")
    if not iguais(a, b):
        dif.append(("transp/modFrete", a, b))
    a, b = o.find(f".//{N}cobr/{N}fat") is not None, m.find(f".//{N}cobr/{N}fat") is not None
    if a != b:
        dif.append(("cobr/fat existe", str(a), str(b)))
    a, b = len(o.findall(f".//{N}cobr/{N}dup")), len(m.findall(f".//{N}cobr/{N}dup"))
    if a != b:
        dif.append(("cobr/duplicatas", str(a), str(b)))
    a, b = txt(o, f".//{N}infAdic/{N}infCpl"), txt(m, f".//{N}infAdic/{N}infCpl")
    if " ".join((a or "").split()) != " ".join((b or "").split()):
        dif.append(("infCpl (texto)", a, b))

    dets_o, dets_m = o.findall(f".//{N}det"), m.findall(f".//{N}det")
    if len(dets_o) != len(dets_m):
        dif.append(("qtd itens", str(len(dets_o)), str(len(dets_m))))
    for i, (do, dm) in enumerate(zip(dets_o, dets_m), start=1):
        for c in CAMPOS_PROD:
            a, b = txt(do, f"{N}prod/{N}{c}"), txt(dm, f"{N}prod/{N}{c}")
            if not iguais(a, b):
                dif.append((f"item/prod/{c}", a, b))
        icms_o, icms_m = do.find(f"{N}imposto/{N}ICMS")[0], dm.find(f"{N}imposto/{N}ICMS")[0]
        for c in CAMPOS_ICMS:
            a, b = txt(icms_o, f"{N}{c}"), txt(icms_m, f"{N}{c}")
            if not iguais(a, b):
                dif.append((f"item/ICMS/{c}", a, b))
        for caminho in ("vTotTrib", "PIS/*/vPIS", "PIS/*/pPIS", "COFINS/*/vCOFINS", "COFINS/*/pCOFINS"):
            sel = f"{N}imposto/" + "/".join(f"{N}{p}" if p != "*" else "*" for p in caminho.split("/"))
            a, b = txt(do, sel), txt(dm, sel)
            if not iguais(a, b):
                dif.append((f"item/{caminho.replace('/*', '')}", a, b))
    return dif


def comparar_antes_depois(arq_antes, numero):
    """Pré-DANFE gerado antes do envio x XML oficial gravado depois do envio."""
    if not numero:
        raise SystemExit("Informe também --numero.")
    with conexao_leitura() as cur:
        cur.execute("SELECT NFSXMLEMINFE FROM NOTAFISCAL WHERE NFSTIP <> 'CAN' "
                    "AND TRIM(LEADING '0' FROM TRIM(NFSNUM)) = ?", (str(int(numero)),))
        linha = cur.fetchone()
        blob = linha[0] if linha else None
        if blob is None:
            raise SystemExit(f"A nota {numero} ainda não tem XML oficial (não foi transmitida).")
        oficial = blob.read() if hasattr(blob, "read") else blob
    oficial = oficial.decode("utf-8") if isinstance(oficial, bytes) else oficial
    dif = comparar(oficial, arq_antes.read_text(encoding="utf-8"))
    if not dif:
        print("Nenhuma diferença nos campos comparados: o pré-DANFE bateu com o DANFE final.")
    for campo, a, b in dif:
        print(f"  {campo:<22} final={a!r}  pre-DANFE={b!r}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--ultimas", type=int, help="só as N notas mais recentes")
    ap.add_argument("--detalhe", action="store_true", help="mostra cada divergência de cada nota")
    ap.add_argument("--antes", help="XML salvo pelo predanfe.py --xml ANTES da transmissão")
    ap.add_argument("--numero", help="com --antes: número da nota, agora já transmitida")
    args = ap.parse_args()

    if args.antes:
        comparar_antes_depois(Path(args.antes), args.numero)
        return

    resumo, por_nota = Counter(), {}
    with conexao_leitura() as cur:
        cur.execute("""SELECT NFSCTR, NFSNUM, NFSDATAUT, NFSFINNFE, NFSXMLEMINFE FROM NOTAFISCAL
                       WHERE NFSXMLEMINFE IS NOT NULL AND NFSTIP <> 'CAN'
                       ORDER BY NFSDATAUT DESC, NFSNUM DESC""")
        notas = []
        for ctr, num, aut, fin, blob in cur.fetchall():
            dados = blob.read() if hasattr(blob, "read") else blob
            xml = dados.decode("utf-8") if isinstance(dados, bytes) else dados
            notas.append({"NFSCTR": ctr, "NFSNUM": num, "aut": aut, "fin": fin, "xml": xml,
                          "ibpt": tributos_aprox.ler_nota_xml(xml)})
        cur.execute("SELECT FIRST 1 PRPVERARQIBPT FROM PROPRIO")
        arquivo = tributos_aprox.ler_arquivo_ibpt((cur.fetchone()[0] or "").strip())
        for i, nota in enumerate(notas[: args.ultimas] if args.ultimas else notas):
            oficial = nota["xml"]
            # só notas transmitidas antes desta ensinam os % do IBPT
            anteriores = [a["ibpt"] for a in notas[i + 1:] if a["fin"] != "4"]
            tabela = tributos_aprox.TabelaIBPT(anteriores, arquivo)
            try:
                montado, _, _ = montar_xml(carregar_nota(cur, nota["NFSCTR"], tabela))
                dif = comparar(oficial, montado)
            except Exception as e:  # noqa: BLE001 - relatório, não pode parar no meio
                dif = [("ERRO", type(e).__name__, str(e))]
            por_nota[int(nota["NFSNUM"])] = dif
            for campo, _, _ in dif:
                resumo[campo] += 1

    ok = sum(1 for d in por_nota.values() if not d)
    print(f"\n{len(por_nota)} notas conferidas: {ok} idênticas nos campos comparados, {len(por_nota) - ok} com diferença.\n")
    if resumo:
        print("Campos com diferença (nº de ocorrências):")
        for campo, qtd in resumo.most_common():
            exemplo = next((num, a, b) for num, d in por_nota.items() for c, a, b in d if c == campo)
            print(f"  {campo:<22} {qtd:>4}   ex.: nota {exemplo[0]}  oficial={exemplo[1]!r}  montado={exemplo[2]!r}")
    if args.detalhe:
        for num, dif in por_nota.items():
            if dif:
                print(f"\nNota {num}:")
                for campo, a, b in dif:
                    print(f"  {campo:<22} oficial={a!r}  montado={b!r}")


if __name__ == "__main__":
    main()
