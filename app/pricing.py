"""Model pricing and per-request cost calculation."""

PRICING_PER_MILLION_TOKENS = {
    "claude-haiku-5-5": (0.10, 0.50),
    "claude-sonnet-5-5": (2.00, 10.00),
}


def cost_usd(model: str, input_tokens: int, output_tokens: int) -> float:
    """Calculate cost from input/output token counts and per-million prices."""
    if input_tokens < 0 or output_tokens < 0:
        raise ValueError("Token counts must be non-negative.")

    try:
        input_price, output_price = PRICING_PER_MILLION_TOKENS[model]
    except KeyError as exc:
        raise ValueError(f"No pricing configured for model {model!r}.") from exc

    return (
        input_tokens / 1_000_000 * input_price
        + output_tokens / 1_000_000 * output_price
    )
