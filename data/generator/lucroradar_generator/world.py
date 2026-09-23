"""Simulação determinística do "mundo verdadeiro" da empresa fictícia.

O mundo é gerado limpo; os problemas de qualidade são injetados depois
(`issues.py`) sobre as linhas exportadas. Os cenários de negócio (desconto,
custo, atraso, ociosidade, manutenção, gargalo) são embutidos aqui e
descritos no manifesto de verdade conhecida.
"""

from __future__ import annotations

import calendar
import math
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from random import Random

from .catalog import (
    LEGAL_SUFFIXES,
    PRODUCTS,
    REGIONS,
    SEGMENTS,
    SUPPLIERS,
    SYLLABLES,
    Product,
)
from .config import GeneratorConfig, month_end

# ---------------------------------------------------------------------------
# Cenários (verdade conhecida). Datas relativas à data de referência padrão;
# para outras datas são deslocadas proporcionalmente em `scenario_dates`.
# ---------------------------------------------------------------------------
DISCOUNT_SALESPEOPLE = ("V06", "V07")
COST_INCREASE_LINE = "Geradores"
COST_INCREASE_FACTOR = 1.14
LATE_PAYER_SEGMENT = "Eventos"
LATE_PAYER_COUNT = 6
IDLE_SKU = "PLT-T12"
IDLE_EXTRA_UNITS = 20
MAINT_SKUS = ("PLT-A16", "PLT-A20")
CREDIT_THRESHOLD = 30_000.0
PRICE_ADJUSTMENT = 1.04  # reajuste de tabela em janeiro (exceto Geradores)
BASE_SALES_ORDERS_PER_DAY = 6.5


def scenario_dates(cfg: GeneratorConfig) -> dict[str, date]:
    """Datas dos cenários ancoradas no fim da janela (meses antes da referência)."""
    ref = cfg.reference_date.replace(day=1)

    def m(offset: int, day: int = 1) -> date:
        y, mm = divmod(ref.month - 1 - offset, 12)
        return date(ref.year + y, mm + 1, day)

    return {
        "discount_from": m(5),  # jan/2026 para referência jun/2026
        "cost_from": m(4),  # fev/2026
        "price_adjustment": m(5),
        "late_from": m(6),  # dez/2025
        "idle_acquisition": m(7, 10),  # 10/nov/2025
        "maint_from": m(3, 20),  # 20/mar/2026
        "maint_to": m(1, 15),  # 15/mai/2026
        "credit_from": m(3),  # mar/2026
    }


@dataclass
class World:
    customers: list[dict] = field(default_factory=list)
    products: list[dict] = field(default_factory=list)
    units: list[dict] = field(default_factory=list)
    orders: list[dict] = field(default_factory=list)
    order_items: list[dict] = field(default_factory=list)
    order_events: list[dict] = field(default_factory=list)
    rental_contracts: list[dict] = field(default_factory=list)
    rental_contract_items: list[dict] = field(default_factory=list)
    maintenance_orders: list[dict] = field(default_factory=list)
    direct_costs: list[dict] = field(default_factory=list)
    receivables: list[dict] = field(default_factory=list)
    receipts: list[dict] = field(default_factory=list)
    payables: list[dict] = field(default_factory=list)
    disbursements: list[dict] = field(default_factory=list)
    facts: dict = field(default_factory=dict)  # verdade conhecida


def _poisson(rng: Random, lam: float) -> int:
    if lam <= 0:
        return 0
    l_, k, p = math.exp(-lam), 0, 1.0
    while True:
        p *= rng.random()
        if p <= l_:
            return k
        k += 1


def _money(x: float) -> float:
    return round(x + 1e-9, 2)


def _dt(d: date, hours: float) -> datetime:
    return datetime.combine(d, time(0, 0)) + timedelta(hours=hours)


def _invented_word(rng: Random) -> str:
    n = rng.choice([2, 2, 3])
    return "".join(rng.choice(SYLLABLES) for _ in range(n)).capitalize()


def _weighted_choice(rng: Random, items: list, weights: list[float]):
    return rng.choices(items, weights=weights, k=1)[0]


def rental_revenue_by_month(start: date, end_excl: date, monthly_rate: float,
                            cap_excl: date) -> dict[date, float]:
    """Receita reconhecida pró-rata dia: taxa mensal × dias ativos / dias do mês.

    Período ativo = [start, min(end_excl, cap_excl)). Mesma regra do mart dbt.
    """
    out: dict[date, float] = {}
    stop = min(end_excl, cap_excl)
    d = start
    while d < stop:
        me = month_end(d)
        seg_end = min(stop, me + timedelta(days=1))
        days = (seg_end - d).days
        dim = calendar.monthrange(d.year, d.month)[1]
        out[d.replace(day=1)] = out.get(d.replace(day=1), 0.0) + monthly_rate * days / dim
        d = seg_end
    return out


class WorldBuilder:
    def __init__(self, cfg: GeneratorConfig):
        self.cfg = cfg
        self.rng = Random(cfg.seed)
        self.w = World()
        self.start = cfg.window_start
        self.ref = cfg.reference_date
        self.ref_excl = self.ref + timedelta(days=1)
        self.sd = scenario_dates(cfg)
        self.products = {p.sku: p for p in PRODUCTS}
        self._order_seq = 0
        self._event_seq = 0
        self._cost_seq = 0
        self._recv_seq = 0
        self._receipt_seq = 0
        self._pay_seq = 0
        self._disb_seq = 0
        self._maint_seq = 0
        self.sales_cogs_by_month: dict[date, float] = defaultdict(float)
        self.freight_by_month: dict[date, float] = defaultdict(float)
        self.lost_rental_requests = 0

    # ------------------------------------------------------------------ utils
    def growth(self, d: date) -> float:
        """Crescimento de demanda ~2,3% a.m. com leve sazonalidade."""
        months = (d.year - self.start.year) * 12 + d.month - self.start.month
        season = 1 + 0.06 * math.sin((d.month - 3) / 12 * 2 * math.pi)
        return (1.023 ** months) * season

    def next_id(self, attr: str, prefix: str, width: int = 6) -> str:
        val = getattr(self, attr) + 1
        setattr(self, attr, val)
        return f"{prefix}{val:0{width}d}"

    # -------------------------------------------------------------- customers
    def build_customers(self) -> None:
        rng = self.rng
        n = int(420 * self.cfg.scale)
        seg_names = list(SEGMENTS)
        seg_w = [SEGMENTS[s][0] for s in seg_names]
        reg_names = list(REGIONS)
        reg_w = [REGIONS[r][0] for r in reg_names]
        used_names: set[str] = set()
        for i in range(1, n + 1):
            seg = _weighted_choice(rng, seg_names, seg_w)
            reg = _weighted_choice(rng, reg_names, reg_w)
            city, uf = rng.choice(REGIONS[reg][1])
            while True:
                name = f"{rng.choice(SEGMENTS[seg][1])} {_invented_word(rng)}"
                if name not in used_names:
                    used_names.add(name)
                    break
            suffix = rng.choice(LEGAL_SUFFIXES)
            # 70% já eram clientes antes da janela; o restante chega ao longo dela
            if rng.random() < 0.7:
                created = self.start - timedelta(days=rng.randint(30, 1500))
            else:
                span = (self.ref - self.start).days - 20
                created = self.start + timedelta(days=int(span * rng.random() ** 0.8))
            tax = "99" + "".join(str(rng.randint(0, 9)) for _ in range(12))
            self.w.customers.append({
                "customer_id": f"C{i:05d}",
                "legal_name": f"{name} {suffix}",
                "tax_id": tax,
                "segment": seg,
                "region": reg,
                "city": city,
                "state": uf,
                "salesperson_id": rng.choice(REGIONS[reg][2]),
                "credit_limit": _money(rng.choice([50, 100, 150, 250, 400, 800]) * 1000.0),
                "created_at": created,
                # atributos internos (não exportados)
                "_weight": min(30.0, rng.paretovariate(1.25)),
                "_pay_profile": "slow" if rng.random() < 0.10 else "normal",
            })
        # Cenário: clientes de Eventos que passam a atrasar
        eventos = sorted(
            (c for c in self.w.customers if c["segment"] == LATE_PAYER_SEGMENT
             and c["created_at"] < self.start),
            key=lambda c: -c["_weight"],
        )
        late = eventos[:LATE_PAYER_COUNT]
        for c in late:
            c["_pay_profile"] = "late_scenario"
        self.w.facts["late_payer_customer_ids"] = sorted(c["customer_id"] for c in late)
        self.cust_by_id = {c["customer_id"]: c for c in self.w.customers}

    def pick_customer(self, d: date, seg_weights: dict[str, float] | None = None) -> dict:
        active = [c for c in self.w.customers if c["created_at"] <= d]
        if seg_weights:
            weights = [c["_weight"] * seg_weights.get(c["segment"], 0.05) for c in active]
        else:
            weights = [c["_weight"] for c in active]
        return _weighted_choice(self.rng, active, weights)

    # --------------------------------------------------------------- products
    def build_products(self) -> None:
        for p in PRODUCTS:
            self.w.products.append({
                "sku": p.sku,
                "description": p.description,
                "product_line": p.product_line,
                "unit_of_measure": p.unit,
                "sale_list_price": p.sale_price,
                "rental_monthly_rate": p.rental_monthly_rate,
                "is_rentable": p.rental_monthly_rate is not None,
                "is_sellable": p.sale_price is not None,
            })

    def list_price(self, p: Product, d: date) -> float | None:
        if p.sale_price is None:
            return None
        if d >= self.sd["price_adjustment"] and p.product_line != COST_INCREASE_LINE:
            return _money(p.sale_price * PRICE_ADJUSTMENT)
        return float(p.sale_price)

    def rental_rate(self, p: Product, d: date) -> float:
        assert p.rental_monthly_rate is not None
        if d >= self.sd["price_adjustment"]:
            return _money(p.rental_monthly_rate * PRICE_ADJUSTMENT)
        return float(p.rental_monthly_rate)

    # ------------------------------------------------------------------ fleet
    def build_units(self) -> None:
        rng = self.rng
        seq = 0
        for p in PRODUCTS:
            if not p.fleet_size:
                continue
            n = max(1, round(p.fleet_size * self.cfg.scale))
            for _ in range(n):
                seq += 1
                acq = self.start - timedelta(days=rng.randint(120, 1800))
                self._add_unit(seq, p, acq, rng.uniform(0.92, 1.05))
            # crescimento orgânico de frota nas plataformas tesoura
            if p.sku in ("PLT-T08", "AND-TB"):
                for k in range(max(1, n // 6)):
                    seq += 1
                    acq = self.start + timedelta(days=150 + 20 * k)
                    self._add_unit(seq, p, acq, 1.0)
        # Cenário: expansão de frota sem demanda correspondente
        p = self.products[IDLE_SKU]
        acq = self.sd["idle_acquisition"]
        idle_ids = []
        for _ in range(round(IDLE_EXTRA_UNITS * self.cfg.scale)):
            seq += 1
            idle_ids.append(self._add_unit(seq, p, acq, 1.0))
        self.w.facts["idle_expansion_unit_ids"] = idle_ids

    def _add_unit(self, seq: int, p: Product, acq: date, cost_factor: float) -> str:
        unit_id = f"U{seq:05d}"
        self.w.units.append({
            "unit_id": unit_id,
            "sku": p.sku,
            "serial_number": f"SN-{p.sku.replace('-', '')}-{seq:05d}",
            "acquisition_date": acq,
            "acquisition_cost": _money((p.unit_acquisition_cost or 0) * cost_factor),
            "branch": self.rng.choice(["Matriz", "Filial Sul", "Filial Nordeste"]),
            "retired_at": None,
            "_state_until": acq,  # disponível a partir desta data
            "_rented_since_preventive": 0,
        })
        return unit_id

    # ----------------------------------------------------------------- rental
    def simulate_rental(self) -> None:
        rng = self.rng
        warmup_start = self.start - timedelta(days=120)
        units_by_sku: dict[str, list[dict]] = defaultdict(list)
        for u in self.w.units:
            units_by_sku[u["sku"]].append(u)
        rental_products = [p for p in PRODUCTS if p.rental_monthly_rate]
        seg_w = {"Construção": 0.55, "Eventos": 0.25, "Indústria": 0.1,
                 "Agronegócio": 0.06, "Serviços": 0.04}
        # demanda diária calibrada para a utilização-alvo inicial da frota original:
        # unidades ocupadas ≈ pedidos/dia × unidades por pedido × duração média
        eventos_share = 0.25
        avg_dur = eventos_share * 6 + (1 - eventos_share) * (5 + 60 + 14) / 3
        demand = {}
        for p in rental_products:
            fleet = max(1, round(p.fleet_size * self.cfg.scale))
            avg_qty = 6.0 if p.sku == "AND-TB" else 1.57
            demand[p.sku] = p.target_utilization * fleet / (avg_qty * avg_dur)
        d = warmup_start
        contract_seq = 0
        while d <= self.ref:
            warm = d < self.start
            for p in rental_products:
                if p.sku == IDLE_SKU:
                    g = 1.0  # demanda estável: a expansão não acompanha mercado
                else:
                    g = self.growth(max(d, self.start))
                lam = demand[p.sku] * g * (0.35 if d.weekday() == 6 else 1.0)
                for _ in range(_poisson(rng, lam)):
                    cust = self.pick_customer(max(d, self.start - timedelta(days=1)), seg_w)
                    if cust["segment"] == "Eventos":
                        duration = rng.randint(2, 10)
                    else:
                        duration = int(rng.triangular(5, 60, 14))
                    qty = rng.choice([1, 1, 1, 1, 2, 2, 3]) if p.sku != "AND-TB" else rng.randint(2, 10)
                    avail = [u for u in units_by_sku[p.sku] if u["_state_until"] <= d]
                    rng.shuffle(avail)
                    if not avail:
                        if not warm:
                            self.lost_rental_requests += 1
                        continue
                    chosen = avail[:qty]
                    end = d + timedelta(days=duration)
                    if warm and end <= self.start:
                        # contrato inteiramente antes da janela: só ocupa a frota
                        for u in chosen:
                            u["_state_until"] = end
                        continue
                    contract_seq += 1
                    self._create_contract(contract_seq, p, cust, d, end, chosen)
                    for u in chosen:
                        u["_state_until"] = end
                        u["_rented_since_preventive"] += duration
                        self._after_return(u, end)
            d += timedelta(days=1)

    def _after_return(self, u: dict, returned: date) -> None:
        """Programa manutenção após devolução (corretiva aleatória ou preventiva)."""
        rng = self.rng
        sku = u["sku"]
        mtype = None
        if sku in MAINT_SKUS and self.sd["maint_from"] <= returned <= self.sd["maint_to"]:
            mtype, days, desc = "corrective", rng.randint(55, 110), "Aguardando peça importada (sistema hidráulico)"
        elif rng.random() < 0.09:
            mtype, days, desc = "corrective", rng.randint(2, 14), "Reparo após devolução"
        elif u["_rented_since_preventive"] > 150:
            mtype, days, desc = "preventive", rng.randint(1, 3), "Revisão preventiva periódica"
        if mtype is None:
            return
        if mtype == "preventive":
            u["_rented_since_preventive"] = 0
        opened = returned
        closed = returned + timedelta(days=days)
        u["_state_until"] = closed
        if closed <= self.start or opened > self.ref:
            return
        acq = self.products[sku].unit_acquisition_cost or 50_000
        if mtype == "preventive":
            cost = acq * rng.uniform(0.004, 0.010)
        elif "peça importada" in desc:
            cost = acq * rng.uniform(0.05, 0.08)
        else:
            cost = acq * rng.uniform(0.01, 0.05)
        mid = self.next_id("_maint_seq", "M", 6)
        self.w.maintenance_orders.append({
            "maintenance_id": mid,
            "unit_id": u["unit_id"],
            "maintenance_type": mtype,
            "opened_at": opened,
            "closed_at": closed if closed <= self.ref else None,
            "description": desc,
            "cost_amount": _money(cost) if closed <= self.ref else None,
            "_true_closed": closed,
            "_true_cost": _money(cost),
        })

    def _create_contract(self, seq: int, p: Product, cust: dict, start: date, end: date,
                         units: list[dict]) -> None:
        rng = self.rng
        order_id = self.next_id("_order_seq", "P", 7)
        contract_id = f"LC{seq:06d}"
        list_rate = self.rental_rate(p, start)
        disc = min(0.18, max(0.0, rng.gauss(0.045, 0.03)))
        agreed = _money(list_rate * (1 - disc))
        monthly_total = agreed * len(units)
        # pedido e eventos (retroativos a partir da entrega)
        self._rental_order_events(order_id, cust, start, monthly_total)
        self.w.rental_contracts.append({
            "contract_id": contract_id,
            "order_id": order_id,
            "customer_id": cust["customer_id"],
            "start_date": start,
            "planned_end_date": max(start + timedelta(days=1),
                                    end - timedelta(days=rng.choice([0, 0, 0, 3, 7]))),
            "actual_end_date": end if end <= self.ref else None,
            "_true_end": end,
            "billing_cycle": "monthly",
        })
        for i, u in enumerate(units, 1):
            self.w.rental_contract_items.append({
                "contract_item_id": f"{contract_id}-{i}",
                "contract_id": contract_id,
                "unit_id": u["unit_id"],
                "sku": p.sku,
                "start_date": start,
                "end_date": end if end <= self.ref else None,
                "_true_end": end,
                "list_monthly_rate": list_rate,
                "agreed_monthly_rate": agreed,
            })
        # logística de entrega e retirada (custo direto atribuível ao contrato)
        per_trip = rng.uniform(280, 950) * (1 + 0.15 * (len(units) - 1))
        for when, ctype in ((start, "delivery_logistics"), (end, "pickup_logistics")):
            if when > self.ref or when < self.start:
                continue
            self._direct_cost("contract", contract_id, ctype, when, per_trip)

    def _rental_order_events(self, order_id: str, cust: dict, delivered: date,
                             monthly_total: float) -> None:
        rng = self.rng
        pick_h = rng.uniform(18, 50)
        credit_h = self._credit_hours(delivered - timedelta(days=4), monthly_total)
        approved_to_pick = rng.uniform(1, 8)
        created_to_credit = rng.uniform(0.5, 6)
        t_deliv = _dt(delivered, rng.uniform(7, 11))
        t_pick = t_deliv - timedelta(hours=pick_h)
        t_appr = t_pick - timedelta(hours=approved_to_pick)
        t_credit = t_appr - timedelta(hours=credit_h)
        t_created = t_credit - timedelta(hours=created_to_credit)
        self.w.orders.append({
            "order_id": order_id,
            "order_type": "rental",
            "customer_id": cust["customer_id"],
            "salesperson_id": cust["salesperson_id"],
            "order_date": t_created.date(),
            "channel": rng.choice(["Consultor", "Consultor", "Televendas", "Portal"]),
        })
        for stage, ts in (("CREATED", t_created), ("CREDIT_REVIEW", t_credit),
                          ("APPROVED", t_appr), ("PICKING", t_pick), ("DELIVERED", t_deliv)):
            self._event(order_id, stage, ts)

    def _credit_hours(self, d: date, amount: float) -> float:
        rng = self.rng
        median_h = 19.0
        if d >= self.sd["credit_from"] and amount >= CREDIT_THRESHOLD:
            median_h = 108.0  # ~4,5 dias: gargalo de análise de crédito
        return median_h * math.exp(rng.gauss(0, 0.55))

    def _event(self, order_id: str, stage: str, ts: datetime) -> None:
        if ts.date() > self.ref:
            return
        self.w.order_events.append({
            "event_id": self.next_id("_event_seq", "E", 8),
            "order_id": order_id,
            "stage_code": stage,
            "event_at": ts.replace(microsecond=0),
        })

    def _direct_cost(self, ref_type: str, ref_id: str, ctype: str, d: date, amount: float) -> None:
        self.w.direct_costs.append({
            "cost_id": self.next_id("_cost_seq", "DC", 7),
            "reference_type": ref_type,
            "reference_id": ref_id,
            "cost_type": ctype,
            "cost_date": d,
            "amount": _money(amount),
        })
        if ctype in ("freight", "delivery_logistics", "pickup_logistics"):
            self.freight_by_month[d.replace(day=1)] += amount

    # ------------------------------------------------------------------ sales
    def simulate_sales(self) -> None:
        rng = self.rng
        sellable = [p for p in PRODUCTS if p.sale_price]
        weights = [p.sale_weight for p in sellable]
        base_per_day = BASE_SALES_ORDERS_PER_DAY * self.cfg.scale
        d = self.start
        item_seq = 0
        while d <= self.ref:
            if d.weekday() == 6:
                d += timedelta(days=1)
                continue
            lam = base_per_day * self.growth(d) * (0.4 if d.weekday() == 5 else 1.0)
            for _ in range(_poisson(rng, lam)):
                cust = self.pick_customer(d)
                # Cenário: vendedores V06/V07 aceleram volume com desconto alto
                if (cust["salesperson_id"] not in DISCOUNT_SALESPEOPLE and d >= self.sd["discount_from"]
                        and rng.random() < 0.08):
                    sul = [c for c in self.w.customers
                           if c["salesperson_id"] in DISCOUNT_SALESPEOPLE and c["created_at"] <= d]
                    if sul:
                        cust = _weighted_choice(rng, sul, [c["_weight"] for c in sul])
                order_id = self.next_id("_order_seq", "P", 7)
                n_lines = rng.choice([1, 1, 1, 2, 2, 3])
                lines = []
                for _line in range(n_lines):
                    p = _weighted_choice(rng, sellable, weights)
                    price = self.list_price(p, d)
                    if price >= 50_000:
                        qty = 1 if rng.random() < 0.9 else 2
                    elif price >= 5_000:
                        qty = rng.choice([1, 1, 1, 2])
                    elif price >= 1_000:
                        qty = rng.randint(1, 3)
                    else:
                        qty = rng.randint(2, 8)
                    gross = price * qty
                    if cust["salesperson_id"] in DISCOUNT_SALESPEOPLE and d >= self.sd["discount_from"]:
                        disc = rng.uniform(0.15, 0.26)
                    else:
                        disc = min(0.14, max(0.0, rng.gauss(0.05, 0.025) + (0.01 if gross > 100_000 else 0)))
                    cost_factor = p.cost_ratio * rng.uniform(0.97, 1.03)
                    unit_cost = p.sale_price * cost_factor
                    if p.product_line == COST_INCREASE_LINE and d >= self.sd["cost_from"]:
                        unit_cost *= COST_INCREASE_FACTOR
                    item_seq += 1
                    lines.append({
                        "order_item_id": f"{order_id}-{len(lines) + 1}",
                        "order_id": order_id,
                        "sku": p.sku,
                        "product_description": p.description,
                        "quantity": qty,
                        "unit_list_price": price,
                        "discount_amount": _money(gross * disc),
                        "unit_cost": _money(unit_cost),
                        "_true_unit_cost": _money(unit_cost),
                    })
                net_total = sum(li["unit_list_price"] * li["quantity"] - li["discount_amount"] for li in lines)
                self._sale_lifecycle(order_id, cust, d, lines, net_total)
            d += timedelta(days=1)

    def _sale_lifecycle(self, order_id: str, cust: dict, d: date, lines: list[dict],
                        net_total: float) -> None:
        rng = self.rng
        t_created = _dt(d, rng.uniform(8, 18))
        t_credit = t_created + timedelta(hours=rng.uniform(0.5, 6))
        t_appr = t_credit + timedelta(hours=self._credit_hours(d, net_total))
        self.w.orders.append({
            "order_id": order_id,
            "order_type": "sale",
            "customer_id": cust["customer_id"],
            "salesperson_id": cust["salesperson_id"],
            "order_date": d,
            "channel": rng.choice(["Consultor", "Consultor", "Televendas", "Portal"]),
        })
        self.w.order_items.extend(lines)
        self._event(order_id, "CREATED", t_created)
        self._event(order_id, "CREDIT_REVIEW", t_credit)
        if rng.random() < 0.04:
            self._event(order_id, "CANCELLED", t_appr)
            return
        t_pick = t_appr + timedelta(hours=rng.uniform(2, 20))
        t_inv = t_pick + timedelta(hours=rng.uniform(20, 70))
        t_deliv = t_inv + timedelta(hours=rng.uniform(18, 96))
        for stage, ts in (("APPROVED", t_appr), ("PICKING", t_pick), ("INVOICED", t_inv),
                          ("DELIVERED", t_deliv)):
            self._event(order_id, stage, ts)
        inv_date = t_inv.date()
        if inv_date > self.ref:
            return  # pedido em aberto: sem receita reconhecida nem título
        cogs = sum(li["_true_unit_cost"] * li["quantity"] for li in lines)
        self.sales_cogs_by_month[inv_date.replace(day=1)] += cogs
        self._direct_cost("order", order_id, "freight", inv_date, net_total * rng.uniform(0.012, 0.028))
        self._direct_cost("order", order_id, "commission", inv_date, net_total * 0.03)
        n_inst = rng.choices([1, 2, 3], weights=[0.6, 0.25, 0.15])[0]
        per = _money(net_total / n_inst)
        amounts = [per] * (n_inst - 1) + [_money(net_total - per * (n_inst - 1))]
        for i, amt in enumerate(amounts, 1):
            self._receivable(cust, "sale", order_id, f"NF{order_id[1:]}/{i}", inv_date,
                             inv_date + timedelta(days=28 * i), amt)

    # ------------------------------------------------------------ receivables
    def build_opening_receivables(self) -> None:
        """Títulos emitidos antes da janela (saldo inicial), sem receita na janela."""
        rng = self.rng
        clients = [c for c in self.w.customers if c["created_at"] < self.start]
        weights = [c["_weight"] for c in clients]
        n = int(230 * self.cfg.scale)
        for i in range(n):
            cust = _weighted_choice(rng, clients, weights)
            issue = self.start - timedelta(days=rng.randint(1, 40))
            amount = _money(rng.lognormvariate(math.log(9_000), 0.9))
            self._receivable(cust, "opening_balance", f"SI{i + 1:05d}", f"SI-{i + 1:05d}",
                             issue, issue + timedelta(days=rng.choice([30, 45, 60])), amount)

    def build_rental_billing(self) -> None:
        items_by_contract: dict[str, list[dict]] = defaultdict(list)
        for it in self.w.rental_contract_items:
            items_by_contract[it["contract_id"]].append(it)
        for c in self.w.rental_contracts:
            cust = self.cust_by_id[c["customer_id"]]
            per_month: dict[date, float] = defaultdict(float)
            for it in items_by_contract[c["contract_id"]]:
                rev = rental_revenue_by_month(max(it["start_date"], self.start), it["_true_end"],
                                              it["agreed_monthly_rate"], self.ref_excl)
                for m, v in rev.items():
                    per_month[m] += v
            for m, amount in sorted(per_month.items()):
                last_active = min(month_end(m), c["_true_end"] - timedelta(days=1))
                if last_active > self.ref:
                    continue
                # fatura no fim do mês (ou na devolução); contratos ativos faturam no último dia
                issue = month_end(m) if c["_true_end"] > month_end(m) else last_active
                if issue > self.ref:
                    continue
                self._receivable(cust, "rental", c["contract_id"],
                                 f"FL{c['contract_id'][2:]}-{m:%Y%m}", issue,
                                 issue + timedelta(days=20), _money(amount))

    def _payment_delay(self, cust: dict, due: date) -> int | None:
        """Dias após o vencimento (negativo = antecipado). None = não pago."""
        rng = self.rng
        prof = cust["_pay_profile"]
        if prof == "late_scenario" and due >= self.sd["late_from"]:
            if rng.random() < 0.15:
                return None
            return rng.randint(60, 150)
        if rng.random() < 0.012:
            return None  # inadimplência
        if prof == "slow":
            return rng.randint(5, 35)
        return int(rng.triangular(-5, 20, 1))

    def _receivable(self, cust: dict, origin_type: str, origin_id: str, doc: str,
                    issue: date, due: date, amount: float) -> None:
        rid = self.next_id("_recv_seq", "R", 7)
        self.w.receivables.append({
            "receivable_id": rid,
            "customer_id": cust["customer_id"],
            "origin_type": origin_type,
            "origin_id": origin_id,
            "document_number": doc,
            "issue_date": issue,
            "due_date": due,
            "amount": amount,
        })
        delay = self._payment_delay(cust, due)
        if delay is None:
            return
        pay = due + timedelta(days=delay)
        if pay < issue:
            pay = issue
        if self.rng.random() < 0.04:
            first = _money(amount * 0.5)
            self._receipt(rid, pay, first)
            self._receipt(rid, pay + timedelta(days=self.rng.randint(10, 40)), _money(amount - first))
        else:
            self._receipt(rid, pay, amount)

    def _receipt(self, rid: str, d: date, amount: float) -> None:
        if d > self.ref:
            return
        self.w.receipts.append({
            "receipt_id": self.next_id("_receipt_seq", "RC", 7),
            "receivable_id": rid,
            "receipt_date": d,
            "amount": amount,
            "method": self.rng.choice(["boleto", "boleto", "pix", "transferência"]),
        })

    # --------------------------------------------------------------- payables
    def build_payables(self) -> None:
        rng = self.rng
        # compras de estoque para revenda acompanham o CMV
        for m, cogs in sorted(self.sales_cogs_by_month.items()):
            for k in range(3):
                issue = m + timedelta(days=4 + 9 * k)
                self._payable(rng.choice(SUPPLIERS["inventory_purchase"]), "inventory_purchase",
                              issue, issue + timedelta(days=45), cogs / 3 * rng.uniform(0.95, 1.05))
        # aquisição de frota dentro da janela
        by_date: dict[date, float] = defaultdict(float)
        for u in self.w.units:
            if u["acquisition_date"] >= self.start:
                by_date[u["acquisition_date"]] += u["acquisition_cost"]
        for d, total in sorted(by_date.items()):
            n = 3 if total > 300_000 else 1
            for k in range(1, n + 1):
                self._payable(rng.choice(SUPPLIERS["fleet_capex"]), "fleet_capex", d,
                              d + timedelta(days=30 * k), total / n)
        for mo in self.w.maintenance_orders:
            closed = mo["_true_closed"]
            if closed <= self.ref and closed >= self.start:
                self._payable(rng.choice(SUPPLIERS["maintenance"]), "maintenance", closed,
                              closed + timedelta(days=30), mo["_true_cost"])
        for m, amount in sorted(self.freight_by_month.items()):
            me = month_end(m)
            self._payable(rng.choice(SUPPLIERS["freight"]), "freight", me,
                          me + timedelta(days=25), amount)
        # saldo inicial de contas a pagar: compras e despesas dos meses anteriores à janela
        first_cogs = self.sales_cogs_by_month.get(self.start, 0.0)
        for back in (2, 1):
            m0 = (self.start - timedelta(days=28 * back)).replace(day=1)
            for k in range(3):
                issue = m0 + timedelta(days=4 + 9 * k)
                self._payable(rng.choice(SUPPLIERS["inventory_purchase"]), "inventory_purchase",
                              issue, issue + timedelta(days=45), first_cogs / 3 * rng.uniform(0.9, 1.0))
        # despesas operacionais fixas (fora da margem de contribuição)
        m = (self.start - timedelta(days=1)).replace(day=1)
        i = -1
        while m <= self.ref:
            base = 470_000 * self.cfg.scale * (1.008 ** i)
            me = month_end(m)
            for name, share, due_day in (("Folha e encargos", 0.62, 5), ("Aluguel e utilidades", 0.18, 10),
                                         ("Serviços administrativos", 0.20, 15)):
                nxt = me + timedelta(days=due_day)
                self._payable(name, "operating_expenses", me, nxt, base * share)
            m = me + timedelta(days=1)
            i += 1

    def _payable(self, supplier: str, category: str, issue: date, due: date, amount: float) -> None:
        if issue > self.ref:
            return
        pid = self.next_id("_pay_seq", "AP", 6)
        amt = _money(amount)
        self.w.payables.append({
            "payable_id": pid,
            "supplier_name": supplier,
            "category": category,
            "issue_date": issue,
            "due_date": due,
            "amount": amt,
        })
        paid = due + timedelta(days=int(self.rng.triangular(-3, 6, 0)))
        if paid <= self.ref:
            self.w.disbursements.append({
                "disbursement_id": self.next_id("_disb_seq", "DS", 7),
                "payable_id": pid,
                "paid_date": paid,
                "amount": amt,
            })

    # ------------------------------------------------------------------ build
    def build(self) -> World:
        self.build_customers()
        self.build_products()
        self.build_units()
        self.simulate_rental()
        self.simulate_sales()
        self.build_opening_receivables()
        self.build_rental_billing()
        self.build_payables()
        self.w.orders.sort(key=lambda o: o["order_id"])
        self.w.facts["lost_rental_requests"] = self.lost_rental_requests
        self.w.facts["scenario_dates"] = {k: v.isoformat() for k, v in self.sd.items()}
        return self.w


def build_world(cfg: GeneratorConfig) -> World:
    return WorldBuilder(cfg).build()
