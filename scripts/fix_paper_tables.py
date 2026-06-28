"""Fix paper trading tables — add composite primary key with profile."""

import duckdb
from pathlib import Path

db_path = Path(__file__).resolve().parent.parent / "data_store" / "aifa_quant.duckdb"
con = duckdb.connect(str(db_path))

for table in ["paper_positions", "paper_nav", "paper_orders"]:
    con.execute(f"DROP TABLE IF EXISTS {table}")
    print(f"Dropped {table}")

con.execute("""
    CREATE TABLE paper_positions (
        profile VARCHAR NOT NULL DEFAULT 'balanced',
        symbol VARCHAR NOT NULL,
        shares BIGINT NOT NULL DEFAULT 0,
        cost_basis DOUBLE DEFAULT 0.0,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (profile, symbol)
    )
""")

con.execute("""
    CREATE TABLE paper_nav (
        profile VARCHAR NOT NULL DEFAULT 'balanced',
        trade_date DATE NOT NULL,
        cash DOUBLE NOT NULL,
        market_value DOUBLE NOT NULL,
        total_value DOUBLE NOT NULL,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (profile, trade_date)
    )
""")

con.execute("""
    CREATE TABLE paper_orders (
        profile VARCHAR NOT NULL DEFAULT 'balanced',
        order_id VARCHAR NOT NULL,
        trade_date DATE NOT NULL,
        symbol VARCHAR NOT NULL,
        side VARCHAR NOT NULL,
        quantity BIGINT NOT NULL,
        order_type VARCHAR NOT NULL,
        price DOUBLE,
        fill_price DOUBLE,
        commission DOUBLE DEFAULT 0.0,
        stamp_duty DOUBLE DEFAULT 0.0,
        status VARCHAR NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (profile, order_id)
    )
""")

print("Tables recreated with composite PK (profile, symbol)")
con.close()
