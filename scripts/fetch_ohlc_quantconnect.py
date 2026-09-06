"""Fetch OHLC data from QuantConnect for F6 offline run (T034 - STUB).

**STUB** - Fetches real data for US6 offline experiment.
Implementation only after Marcos confirms QuantConnect.

Spec F6 §10.1 - US6

For now, this is a stub that documents the expected data schema.
The 10 canonical files should be downloaded manually or via approved provider.

Canonical files §9.2:
- eur_usd.parquet
- gbp_jpy.parquet
- usd_cad.parquet
- aud_nzd.parquet
- us500.parquet
- ger30.parquet
- jp225.parquet
- xau_usd.parquet
- usoil.parquet
- nas100.parquet

Format: M30 bars with columns [timestamp, open, high, low, close, bid, ask]
"""

from __future__ import annotations


class QuantConnectFetcher:
    """Fetcher for QuantConnect historical data.
    
    STUB - Implementation pending provider confirmation from Marcos.
    """
    
    def __init__(self):
        raise NotImplementedError(
            "QuantConnect fetcher is a stub. "
            "Marcos needs to confirm provider before implementation. "
            "For now, download the 10 .parquet files manually to data/ohlc/"
        )
    
    def fetch_instrument(self, symbol: str, start_date: str, end_date: str) -> str:
        """Fetch data for a single instrument."""
        raise NotImplementedError
    
    def fetch_universe(self, symbols: list, start_date: str, end_date: str) -> None:
        """Fetch data for all instruments."""
        raise NotImplementedError


def main():
    """CLI entry point."""
    print("STUB: QuantConnect fetcher not implemented yet.")
    print("Download the 10 canonical .parquet files manually to data/ohlc/")
    print("""
Canonical files missing for US6 offline run:
  - eur_usd.parquet
  - gbp_jpy.parquet
  - usd_cad.parquet
  - aud_nzd.parquet
  - us500.parquet
  - ger30.parquet
  - jp225.parquet
  - xau_usd.parquet
  - usoil.parquet
  - nas100.parquet
""")


if __name__ == "__main__":
    main()