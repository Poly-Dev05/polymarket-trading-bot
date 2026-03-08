"""
Fetch proxy wallet balance via Polymarket CLOB (same logic as test_5m_core.py).
Runs sync so it can be called with asyncio.to_thread from the bot.
"""

from __future__ import annotations

import logging
import yaml
from pathlib import Path
from typing import Tuple

logger = logging.getLogger(__name__)


def _load_config_dict(config_path: str | Path) -> dict:
    """Load user config YAML as dict (no dependency on config package)."""
    path = Path(config_path)
    if not path.is_file():
        return {}
    with open(path, "r") as f:
        data = yaml.safe_load(f)
    return data if isinstance(data, dict) else {}


def derive_api_creds_sync(
    funder: str,
    config: dict,
) -> Tuple[str | None, str | None, str | None]:
    """
    Derive CLOB API credentials from the user's private key (create_or_derive_api_creds).
    Returns (api_key, api_secret, api_passphrase) or (None, None, None) on failure.
    These can be used as builder/relayer creds when POLYBOT5M_EXECUTION__BUILDER_* are not set.
    """

    try:
        from py_clob_client.client import ClobClient as PyClobClient

        api = config.get("api") or {}
        ex = config.get("execution") or {}
        host = (api.get("clob_url") or "https://clob.polymarket.com").rstrip("/")
        chain_id = ex.get("chain_id") or 137
        sig_type = ex.get("signature_type") or 2
        api_key = (ex.get("api_key") or "").strip()
        api_secret = (ex.get("api_secret") or "").strip()
        api_passphrase = (ex.get("api_passphrase") or "").strip()

        if not all([api_key, api_secret, api_passphrase]):
            creds = temp.create_or_derive_api_creds()
            if not creds:
                return (None, None, None)
            api_key = creds.api_key
            api_secret = creds.api_secret
            api_passphrase = creds.api_passphrase

        return (api_key, api_secret, api_passphrase)
    except Exception:
        return (None, None, None)


def fetch_proxy_balance_sync(
    config_path: str | Path | None = None,
    project_root: Path | None = None,
) -> float:
    """
    Derive API creds from private_key and funder, call CLOB get_balance_allowance.
    Returns balance in USD (USDC.e) or 0.0 on any failure. No dependency on config package.
    """
    


def check_and_update_allowance_sync(
    config_path: str | Path | None = None,
    project_root: Path | None = None,
) -> Tuple[bool, str]:
    """
    Ensure proxy has sufficient USDC balance and allowance for placing orders.
    Calls CLOB get_balance_allowance; if allowance is zero or very low, calls
    update_balance_allowance. Returns (ok, message) for the bot to show.
    """
    if not all([api_key, api_secret, api_passphrase]):
        temp = PyClobClient(
            host=host,
            chain_id=chain_id,
            creds=None,
            signature_type=sig_type,
            funder=funder,
        )
        creds = temp.create_or_derive_api_creds()
        if not creds:
            return (False, "Could not derive API credentials.")
        api_key, api_secret, api_passphrase = creds.api_key, creds.api_secret, creds.api_passphrase

    creds = ApiCreds(
        api_key=api_key,
        api_secret=api_secret,
        api_passphrase=api_passphrase,
    )
    client = PyClobClient(
        host=host,
        chain_id=chain_id,
        key=private_key,
        creds=creds,
        signature_type=sig_type,
        funder=funder,
    )
    bal_params = BalanceAllowanceParams(
        asset_type=AssetType.COLLATERAL,
        signature_type=sig_type,
    )
    try:
        resp = client.get_balance_allowance(bal_params)
    except Exception as e:
        return (False, f"Failed to get balance/allowance: {e}")

    if isinstance(resp, dict):
        raw_balance = resp.get("balance") or resp.get("balanceAllowance") or 0
        raw_allowance = resp.get("allowance", 0)
    else:
        raw_balance = getattr(resp, "balance", 0) or getattr(resp, "balanceAllowance", 0)
        raw_allowance = getattr(resp, "allowance", 0)
    balance = float(raw_balance or 0) / 1e6
    allowance = float(raw_allowance or 0)

    # If allowance is zero or very low, ask the CLOB to update (may trigger approval flow).
    if allowance < 1e6:
        try:
            client.update_balance_allowance(bal_params)
        except Exception as e:
            return (
                False,
                f"Allowance is low and update failed: {e}. Approve USDC for your Polymarket proxy (Wallet).",
            )

    if balance < 0.01:
        return (
            False,
            f"Insufficient balance: ${balance:.2f}. Deposit USDC to your Polymarket wallet (Wallet).",
        )
    return (True, f"Balance ${balance:.2f}. Allowance OK.")
