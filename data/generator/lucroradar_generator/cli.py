"""CLI: `lucroradar-generate --seed 42 --reference-date 2026-06-30`."""

from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path

from .config import GeneratorConfig
from .writer import write_dataset

ROOT = Path(__file__).resolve().parents[3]


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description="Gera dados sintéticos do LucroRadar AI")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--reference-date", type=date.fromisoformat, default=date(2026, 6, 30))
    ap.add_argument("--months", type=int, default=18)
    ap.add_argument("--scale", type=float, default=1.0)
    ap.add_argument("--out", type=Path, default=ROOT / "data" / "landing")
    ap.add_argument("--manifest-dir", type=Path, default=ROOT / "data" / "manifest")
    args = ap.parse_args(argv)
    cfg = GeneratorConfig(seed=args.seed, reference_date=args.reference_date,
                          months=args.months, scale=args.scale)
    manifest = write_dataset(cfg, args.out, args.manifest_dir)
    print(f"Janela: {cfg.window_start} a {cfg.reference_date} (seed={cfg.seed})")
    for batch, tables in manifest["batches"].items():
        total = sum(tables.values())
        print(f"  {batch}: {total} linhas em {len(tables)} arquivos")
    print(f"Manifesto: {args.manifest_dir / 'ground_truth.json'}")


if __name__ == "__main__":
    main()
