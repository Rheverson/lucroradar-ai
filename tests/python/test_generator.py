import hashlib
from datetime import date

from lucroradar_generator.config import GeneratorConfig
from lucroradar_generator.writer import TABLE_COLUMNS, write_dataset
from lucroradar_ingestion.contracts import SOURCE_CONTRACTS


def _digest(folder):
    h = hashlib.sha256()
    for p in sorted(folder.rglob("*.csv")):
        h.update(p.name.encode())
        h.update(p.read_bytes())
    return h.hexdigest()


def test_generator_respects_ingestion_contract():
    assert TABLE_COLUMNS == SOURCE_CONTRACTS


def test_same_seed_same_files(tmp_path):
    cfg = GeneratorConfig(seed=7, reference_date=date(2026, 6, 30), scale=0.3)
    write_dataset(cfg, tmp_path / "a", tmp_path / "ma")
    write_dataset(cfg, tmp_path / "b", tmp_path / "mb")
    assert _digest(tmp_path / "a") == _digest(tmp_path / "b")


def test_different_seed_different_files(tmp_path):
    write_dataset(GeneratorConfig(seed=1, scale=0.3), tmp_path / "a", tmp_path / "ma")
    write_dataset(GeneratorConfig(seed=2, scale=0.3), tmp_path / "b", tmp_path / "mb")
    assert _digest(tmp_path / "a") != _digest(tmp_path / "b")


def test_reference_date_controls_window(tmp_path):
    cfg = GeneratorConfig(seed=3, reference_date=date(2025, 12, 31), scale=0.3)
    m = write_dataset(cfg, tmp_path / "x", tmp_path / "m")
    assert m["window_start"] == "2024-07-01"
    assert max(m["expected"]["sales_net_revenue_by_month"]) == "2025-12"


def test_manifest_lists_controlled_problems(tmp_path):
    m = write_dataset(GeneratorConfig(seed=42, scale=0.5), tmp_path / "x", tmp_path / "m")
    dq = m["data_quality"]
    assert len(dq["duplicate_customer_pairs"]) == 14
    for key in ("orders_missing_customer", "order_items_negative_quantity", "order_items_missing_cost",
                "receivables_missing_due_date", "receipts_orphan"):
        assert dq[key], key
    assert {"discount_escalation", "cost_increase", "late_payments", "idle_fleet",
            "maintenance_backlog", "credit_review_bottleneck"} <= set(m["scenarios"])
