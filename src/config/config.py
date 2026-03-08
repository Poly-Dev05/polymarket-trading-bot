
class OrderConfig(BaseModel):
    """Order Price and Order Size (Telegram Settings / Arbitrage bot)."""
    price: float = 0.47
    size: float = 5.0


class RiskConfig(BaseModel):
    stop_loss_pct: float = 8.0
    stop_time: int = 30  # seconds before market close (force-sell)
    max_position_size_usdc: float = 20.0
    max_concurrent_positions: int = 2

def get_user_config_path(user_id: int | str, project_root: Path | None = None) -> Path:
    """Path to per-user config: config/users/<user_id>.yaml."""
    root = project_root or Path.cwd()
    return (root / "config" / "users" / f"{user_id}.yaml").resolve()

