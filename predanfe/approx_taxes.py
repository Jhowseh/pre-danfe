import csv
import io
import re
import time
import zlib
from decimal import ROUND_CEILING, ROUND_HALF_UP, Decimal
from pathlib import Path

CENT = Decimal("0.01")
HUNDRED = Decimal(100)
STATE_RATE_CANDIDATES = [Decimal(x) for x in ("18", "20", "27", "0", "4", "7", "12", "17", "19", "22", "25", "28",
                                              "29", "30", "33", "35")]
ITEMS_PER_NCM = 40
HISTORY_INVOICES = 600


def round_cents(v):
    return v.quantize(CENT, ROUND_HALF_UP)


def item_value(base, federal, state):
    return round_cents(base * federal / HUNDRED) + round_cents(base * state / HUNDRED)


def _federal_range(items, state):
    low, high = Decimal(0), Decimal(10000)
    for base, vtt in items:
        if base <= 0:
            continue
        target = vtt - round_cents(base * state / HUNDRED)
        lo = (target - Decimal("0.005")) * HUNDRED / base * HUNDRED
        hi = (target + Decimal("0.005")) * HUNDRED / base * HUNDRED
        low, high = max(low, lo), min(high, hi)
        if low >= high:
            return None
    return low, high


def _possible_pairs(items):
    pairs = []
    for e in STATE_RATE_CANDIDATES:
        bounds = _federal_range(items, e)
        if bounds is None:
            continue
        start = int(bounds[0].to_integral_value(rounding=ROUND_CEILING))
        for cents in range(start, start + 6):
            f = Decimal(cents) / HUNDRED
            if Decimal(cents) < bounds[1] and all(item_value(b, f, e) == v for b, v in items):
                pairs.append((f, e))
    return pairs


class IBPTTable:
    def __init__(self, invoices, ibpt_file=None):
        self.rates = {}
        self.text_rates = {}
        self._item_pairs = {}
        self.file = ibpt_file or {}
        by_key = {}
        for inv in invoices:
            for ncm, imp, base, vtt in inv["items"]:
                bucket = by_key.setdefault((ncm, imp), [])
                if len(bucket) < ITEMS_PER_NCM and vtt is not None:
                    bucket.append((base, vtt))
        for key, items in by_key.items():
            used = items
            pairs = _possible_pairs(used)
            while not pairs and len(used) > 1:
                used = used[: max(1, len(used) // 2)]
                pairs = _possible_pairs(used)
            if pairs:
                self._item_pairs[key] = pairs
        self.frequency = {}
        for pairs in self._item_pairs.values():
            for p in pairs:
                self.frequency[p] = self.frequency.get(p, 0) + 1
        for key, pairs in self._item_pairs.items():
            self.rates[key] = max(pairs, key=lambda p: (self.frequency.get(p, 0), -pairs.index(p)))
        self.common_state_rate = self._most_common_state_rate()
        self._learn_text(invoices)
        for key, pairs in self._item_pairs.items():
            if self.text_rates.get(key) in pairs:
                self.rates[key] = self.text_rates[key]

    def _learn_text(self, invoices, rounds=6):
        self.text_rates = dict(self.rates)
        with_text = [inv for inv in invoices[:300] if inv["F"] is not None]
        if not with_text:
            return
        candidates = set(self.rates.values())
        for inv in with_text:
            keys = {(i[0], i[1]) for i in inv["items"]}
            if len(keys) == 1:
                pair = self._single_ncm_pair(inv)
                if pair:
                    candidates.add(pair)
                    self.text_rates[keys.pop()] = pair
        candidates = sorted(candidates)
        by_key = {}
        for inv in with_text:
            for ncm, imp, *_ in inv["items"]:
                by_key.setdefault((ncm, imp), []).append(inv)

        for _ in range(rounds):
            changed = False
            for key, key_invoices in by_key.items():
                current = self.text_rates.get(key)
                if current is None:
                    continue

                def score(pair):
                    exact, error = 0, Decimal(0)
                    for inv in key_invoices:
                        F, E, complete = self._totals(inv["items"], {key: pair}, text=True)
                        if complete:
                            exact += F == inv["F"] and E == inv["E"]
                            error += abs(F - inv["F"]) + abs(E - inv["E"])
                    return (-exact, error, -self.frequency.get(pair, 0), pair != current)
                best = min(candidates, key=score)
                if score(best)[0] == 0:
                    best = self.rates.get(key, current)
                if best != current:
                    self.text_rates[key] = best
                    changed = True
            if not changed:
                break

    @staticmethod
    def _single_ncm_pair(inv):
        found = []
        for e in STATE_RATE_CANDIDATES:
            if sum(round_cents(b * e / HUNDRED) for _, _, b, *_ in inv["items"]) != inv["E"]:
                continue
            base = sum(b for _, _, b, *_ in inv["items"])
            if not base:
                continue
            approx = (inv["F"] * HUNDRED / base).quantize(CENT)
            for f in (approx - CENT, approx, approx + CENT):
                if sum(round_cents(b * f / HUNDRED) for _, _, b, *_ in inv["items"]) == inv["F"]:
                    found.append((f, e))
                    break
        return found[0] if len(found) == 1 else None

    def _totals(self, items, override=None, text=False):
        table = self.text_rates if text else self.rates
        F = E = Decimal(0)
        complete = True
        for ncm, imp, base, *_ in items:
            pair = (override or {}).get((ncm, imp)) or table.get((ncm, imp))
            if pair is None:
                complete = False
                continue
            F += round_cents(base * pair[0] / HUNDRED)
            E += round_cents(base * pair[1] / HUNDRED)
        return F, E, complete

    def _most_common_state_rate(self):
        counts = {}
        for _, e in self.rates.values():
            counts[e] = counts.get(e, 0) + 1
        return max(counts, key=counts.get) if counts else None

    def rate(self, ncm, imported=False, text=False):
        pair = (self.text_rates if text else self.rates).get((ncm, imported))
        if pair:
            return pair[0], pair[1], "invoices"
        entry = self.file.get(ncm)
        if entry:
            national, imp, state = entry
            state_rate = self.common_state_rate if self.common_state_rate is not None else state
            return (imp if imported else national), state_rate, "file"
        return None, None, None


TEXT_RE = re.compile(r"Federais R\$ ([\d.,]+) \(([\d,]+)%\).*?Estaduais R\$ ([\d.,]+) \(([\d,]+)%\)")


def _parse_brl(s):
    return Decimal(s.replace(".", "").replace(",", "."))


def parse_invoice_xml(xml):
    items = []
    for det in re.findall(r"<det nItem.*?</det>", xml, re.S):
        ncm = re.search(r"<NCM>(.*?)</NCM>", det)
        vprod = re.search(r"<vProd>(.*?)</vProd>", det)
        vdesc = re.search(r"<vDesc>(.*?)</vDesc>", det)
        vtt = re.search(r"<vTotTrib>(.*?)</vTotTrib>", det)
        orig = re.search(r"<orig>(.*?)</orig>", det)
        if not (ncm and vprod):
            continue
        base = Decimal(vprod.group(1)) - (Decimal(vdesc.group(1)) if vdesc else 0)
        items.append((ncm.group(1), (orig.group(1) if orig else "0") in ("1", "2", "3", "8"), base,
                      Decimal(vtt.group(1)) if vtt else None))
    inf = re.search(r"<infCpl>(.*?)</infCpl>", xml, re.S)
    m = TEXT_RE.search(inf.group(1)) if inf else None
    return {"items": items, "F": _parse_brl(m.group(1)) if m else None, "E": _parse_brl(m.group(3)) if m else None}


def read_ibpt_file(version, folder=Path(r"C:\Syspdv")):
    path = Path(folder) / f"{version}.ibpt"
    if not version or not path.exists():
        return {}
    try:
        text = zlib.decompress(path.read_bytes()).decode("latin-1")
    except (OSError, zlib.error):
        return {}
    table = {}
    shared = {}
    for c in csv.reader(io.StringIO(text), delimiter=";"):
        if len(c) > 7 and c[2] == "0" and c[1].strip() == "":
            raw = (c[4], c[5], c[6])
            triple = shared.get(raw)
            if triple is None:
                try:
                    triple = shared[raw] = (Decimal(c[4]), Decimal(c[5]), Decimal(c[6]))
                except ArithmeticError:
                    continue
            table[c[0]] = triple
    return table


_cache = {"at": 0.0, "table": None}


def current_table(cur, ttl_seconds=600):
    if _cache["table"] is not None and time.time() - _cache["at"] < ttl_seconds:
        return _cache["table"]
    cur.execute(f"""SELECT FIRST {HISTORY_INVOICES} NFSXMLEMINFE FROM NOTAFISCAL
                    WHERE NFSXMLEMINFE IS NOT NULL AND NFSTIP <> 'CAN' AND NFSFINNFE <> '4'
                    ORDER BY NFSDATAUT DESC""")
    invoices = []
    for (blob,) in cur.fetchall():
        data = blob.read() if hasattr(blob, "read") else blob
        invoices.append(parse_invoice_xml(data.decode("utf-8", "replace")))
    cur.execute("SELECT FIRST 1 PRPVERARQIBPT FROM PROPRIO")
    row = cur.fetchone()
    table = IBPTTable(invoices, read_ibpt_file((row[0] or "").strip() if row else ""))
    _cache.update(at=time.time(), table=table)
    return table
