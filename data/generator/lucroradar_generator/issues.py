"""Injeção controlada de problemas de qualidade de dados.

Cada problema injetado é registrado em `facts` (manifesto de verdade
conhecida). A aplicação NÃO lê o manifesto: ele serve só para testes.
"""

from __future__ import annotations

import unicodedata
from datetime import date, timedelta
from random import Random

from .catalog import DESCRIPTION_VARIANTS, LEGACY_PRODUCT_CODES
from .world import World


def _strip_accents(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))


def format_tax_id(digits: str) -> str:
    return f"{digits[:2]}.{digits[2:5]}.{digits[5:8]}/{digits[8:12]}-{digits[12:]}"


ABBREVIATIONS = {
    "Construtora": "Constr.",
    "Engenharia": "Eng.",
    "Indústria": "Ind.",
    "Agropecuária": "Agropec.",
    "Serviços": "Serv.",
    "Produções": "Prod.",
    "Metalúrgica": "Metal.",
}


def _typo(name: str, rng: Random) -> str:
    words = name.split(" ")
    # troca duas letras internas da palavra inventada (segunda palavra)
    w = words[1]
    if len(w) > 4:
        i = rng.randint(1, len(w) - 3)
        w = w[:i] + w[i + 1] + w[i] + w[i + 2:]
    words[1] = w
    return " ".join(words)


def inject_issues(world: World, seed: int, reference_date: date) -> dict:
    rng = Random(seed * 7919 + 17)
    facts: dict = {}
    customers = world.customers

    # ---------------------------------------------------------- duplicidades
    orders_by_customer: dict[str, list[dict]] = {}
    for o in world.orders:
        orders_by_customer.setdefault(o["customer_id"], []).append(o)
    eligible = [
        c for c in customers
        if len(orders_by_customer.get(c["customer_id"], [])) >= 4
        and c["created_at"] < reference_date - timedelta(days=400)
        and c["customer_id"] not in world.facts.get("late_payer_customer_ids", [])
    ]
    rng.shuffle(eligible)
    dup_sources = sorted(eligible[:14], key=lambda c: c["customer_id"])
    next_num = len(customers) + 1
    duplicate_pairs = []
    for k, orig in enumerate(dup_sources):
        dup_id = f"C{next_num:05d}"
        next_num += 1
        kind = ["same_tax_id_formatted", "no_tax_id_abbrev", "same_tax_id_typo"][k % 3]
        name = orig["legal_name"]
        if kind == "same_tax_id_formatted":
            new_name, tax = _strip_accents(name).upper(), format_tax_id(orig["tax_id"])
        elif kind == "no_tax_id_abbrev":
            first = name.split(" ")[0]
            new_name = name.replace(first, ABBREVIATIONS.get(first, first), 1).replace("Ltda", "LTDA.")
            tax = ""
        else:
            new_name, tax = _typo(name, rng), orig["tax_id"]
        created = reference_date - timedelta(days=rng.randint(200, 380))
        dup = dict(orig)
        dup.update({"customer_id": dup_id, "legal_name": new_name, "tax_id": tax,
                    "created_at": created})
        customers.append(dup)
        moved = 0
        for o in orders_by_customer[orig["customer_id"]]:
            if o["order_date"] >= created and rng.random() < 0.4:
                o["customer_id"] = dup_id
                moved += 1
        duplicate_pairs.append({"original": orig["customer_id"], "duplicate": dup_id,
                                "kind": kind, "orders_moved": moved})
    # títulos e contratos seguem o cliente do pedido
    order_customer = {o["order_id"]: o["customer_id"] for o in world.orders}
    contract_customer = {}
    for c in world.rental_contracts:
        c["customer_id"] = order_customer[c["order_id"]]
        contract_customer[c["contract_id"]] = c["customer_id"]
    for r in world.receivables:
        if r["origin_type"] == "sale":
            r["customer_id"] = order_customer[r["origin_id"]]
        elif r["origin_type"] == "rental":
            r["customer_id"] = contract_customer[r["origin_id"]]
    facts["duplicate_customer_pairs"] = duplicate_pairs

    # falsos positivos: nomes parecidos, empresas diferentes (não devem ser unidos)
    others = [c for c in customers if c["customer_id"] not in
              {p["original"] for p in duplicate_pairs} | {p["duplicate"] for p in duplicate_pairs}]
    rng.shuffle(others)
    false_pairs = []
    for a, b in ((others[0], others[1]), (others[2], others[3])):
        word = a["legal_name"].split(" ")[1]
        prefix = b["legal_name"].split(" ")[0]
        b["legal_name"] = f"{prefix} {word} {b['legal_name'].split(' ')[-1]}"
        false_pairs.append({"a": a["customer_id"], "b": b["customer_id"]})
    facts["similar_name_distinct_customers"] = false_pairs

    # ------------------------------------------- inconsistências de cadastro
    dup_ids = {p["duplicate"] for p in duplicate_pairs}
    base = [c for c in customers if c["customer_id"] not in dup_ids]
    messy = rng.sample(base, int(len(base) * 0.06))
    for c in messy:
        c["legal_name"] = rng.choice([
            "  " + c["legal_name"],
            c["legal_name"].upper(),
            c["legal_name"].replace(" ", "  ", 1),
        ])
    for c in rng.sample(base, int(len(base) * 0.3)):
        if c["tax_id"] and "." not in c["tax_id"]:
            c["tax_id"] = format_tax_id(c["tax_id"])
    missing_segment = rng.sample(base, int(len(base) * 0.03))
    for c in missing_segment:
        c["segment"] = ""
    missing_region = rng.sample([c for c in base if c["segment"]], 5)
    for c in missing_region:
        c["region"] = ""
    facts["customers_missing_segment"] = sorted(c["customer_id"] for c in missing_segment)
    facts["customers_missing_region"] = sorted(c["customer_id"] for c in missing_region)
    facts["customers_messy_name"] = len(messy)

    # ------------------------------------------------------------- produtos
    for code, (canonical, desc) in LEGACY_PRODUCT_CODES.items():
        prod = next(p for p in world.products if p["sku"] == canonical)
        legacy = dict(prod)
        legacy.update({"sku": code, "description": desc})
        world.products.append(legacy)
    legacy_lines = 0
    variant_lines = 0
    early_limit = reference_date - timedelta(days=365)
    order_date = {o["order_id"]: o["order_date"] for o in world.orders}
    for it in world.order_items:
        for code, (canonical, _desc) in LEGACY_PRODUCT_CODES.items():
            if it["sku"] == canonical and order_date[it["order_id"]] < early_limit and rng.random() < 0.3:
                it["sku"] = code
                legacy_lines += 1
        variants = DESCRIPTION_VARIANTS.get(it["sku"])
        if variants and rng.random() < 0.25:
            it["product_description"] = rng.choice(variants)
            variant_lines += 1
    facts["order_items_legacy_sku"] = legacy_lines
    facts["order_items_description_variant"] = variant_lines

    # ---------------------------------------------------------- custo ausente
    parts_cut = reference_date - timedelta(days=90)
    sku_line = {p["sku"]: p["product_line"] for p in world.products}
    missing_cost_items = []
    for it in world.order_items:
        od = order_date[it["order_id"]]
        if sku_line.get(it["sku"]) == "Peças e acessórios" and od >= parts_cut and rng.random() < 0.3:
            it["unit_cost"] = None
            missing_cost_items.append(it["order_item_id"])
        elif rng.random() < 0.02:
            it["unit_cost"] = None
            missing_cost_items.append(it["order_item_id"])
    facts["order_items_missing_cost"] = sorted(missing_cost_items)

    # ------------------------------------------------ registros inválidos
    for o in world.orders:
        o["_orig_date"] = o["order_date"]
    sale_orders = [o for o in world.orders if o["order_type"] == "sale"]
    no_customer = rng.sample(sale_orders, max(3, int(len(sale_orders) * 0.003)))
    for o in no_customer:
        o["customer_id"] = ""
    remaining = [o for o in sale_orders if o["customer_id"]]
    br_dates = rng.sample(remaining, int(len(remaining) * 0.01))
    for o in br_dates:
        o["order_date"] = o["order_date"].strftime("%d/%m/%Y")
    bad_date = rng.sample([o for o in remaining if not isinstance(o["order_date"], str)], 4)
    for o in bad_date:
        d = o["order_date"]
        o["order_date"] = f"{d.year}-02-30"
    facts["orders_missing_customer"] = sorted(o["order_id"] for o in no_customer)
    facts["orders_invalid_date"] = sorted(o["order_id"] for o in bad_date)
    facts["orders_br_date_format"] = len(br_dates)

    invalid_order_ids = set(facts["orders_missing_customer"]) | set(facts["orders_invalid_date"])
    candidates = [it for it in world.order_items if it["order_id"] not in invalid_order_ids]
    neg = rng.sample(candidates, max(3, int(len(candidates) * 0.0015)))
    for it in neg:
        it["quantity"] = -abs(it["quantity"])
    unk = rng.sample([it for it in candidates if it not in neg], 5)
    for it in unk:
        it["sku"] = "XYZ-999"
    facts["order_items_negative_quantity"] = sorted(it["order_item_id"] for it in neg)
    facts["order_items_unknown_sku"] = sorted(it["order_item_id"] for it in unk)
    dup_rows = rng.sample(candidates, int(len(candidates) * 0.005))
    facts["order_items_exact_duplicates"] = len(dup_rows)
    world.order_items.extend(dict(it) for it in dup_rows)

    for ev in rng.sample(world.order_events, int(len(world.order_events) * 0.03)):
        ev["stage_code"] = rng.choice([ev["stage_code"].lower(), " " + ev["stage_code"],
                                       ev["stage_code"].title()])

    # --------------------------------------------------------- financeiro
    recv_no_due = rng.sample(world.receivables, max(5, int(len(world.receivables) * 0.004)))
    for r in recv_no_due:
        r["due_date"] = None
    facts["receivables_missing_due_date"] = sorted(r["receivable_id"] for r in recv_no_due)
    br_amount = rng.sample([r for r in world.receivables if r["due_date"]], int(len(world.receivables) * 0.01))
    for r in br_amount:
        r["amount"] = f"{r['amount']:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    facts["receivables_br_amount_format"] = len(br_amount)
    dup_receipts = rng.sample(world.receipts, int(len(world.receipts) * 0.003))
    world.receipts.extend(dict(r) for r in dup_receipts)
    facts["receipts_exact_duplicates"] = len(dup_receipts)
    orphan_ids = []
    for i in range(3):
        rid = f"RCX{i + 1:05d}"
        world.receipts.append({"receipt_id": rid, "receivable_id": f"R9{i:06d}",
                               "receipt_date": reference_date - timedelta(days=10 * (i + 1)),
                               "amount": 1500.0 * (i + 1), "method": "pix"})
        orphan_ids.append(rid)
    facts["receipts_orphan"] = orphan_ids
    return facts
