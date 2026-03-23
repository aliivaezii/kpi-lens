"""
CLI entry point for database seeding.

Delegates to data/seeds/generate_kpis.py which contains the full synthetic
data generation logic. This wrapper exists so 'python scripts/seed_database.py'
is the canonical one-liner in the README.

Run:
    python scripts/seed_database.py                 # 104 weeks, default DB
    python scripts/seed_database.py --weeks 52      # 1 year only
    python scripts/seed_database.py --db sqlite:///my.db
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

# Allow running from project root without installing
sys.path.insert(0, str(Path(__file__).parent.parent))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Seed the KPI-Lens database with synthetic data"
    )
    parser.add_argument(
        "--weeks",
        type=int,
        default=104,
        help="Number of weeks to generate (default: 104)",
    )
    parser.add_argument(
        "--db",
        type=str,
        default=None,
        help="SQLAlchemy database URL (default: from .env)",
    )
    args = parser.parse_args()

    # Import after path setup so the project package is importable
    import data.seeds.generate_kpis as gen

    # Override module-level constants before calling main() so the generator
    # picks up the CLI arguments without requiring changes to generate_kpis.py.
    gen.N_WEEKS = args.weeks
    if args.db:
        os.environ["DATABASE_URL"] = args.db

    gen.main()


if __name__ == "__main__":
    main()
