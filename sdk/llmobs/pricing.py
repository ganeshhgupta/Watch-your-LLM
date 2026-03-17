# Pricing in USD per 1 million tokens
PRICING: dict[str, dict[str, float]] = {
    "gpt-4o": {"input": 5.0, "output": 15.0},
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
    "claude-3-5-sonnet": {"input": 3.0, "output": 15.0},
    "claude-3-5-sonnet-20241022": {"input": 3.0, "output": 15.0},
    "claude-3-5-sonnet-20240620": {"input": 3.0, "output": 15.0},
    "gemini-1.5-pro": {"input": 1.25, "output": 5.0},
    "gemini-1.5-flash": {"input": 0.075, "output": 0.30},
    "gemini-1.5-flash-8b": {"input": 0.0375, "output": 0.15},
    "gemini-2.0-flash": {"input": 0.10, "output": 0.40},
    "gemini-2.0-flash-exp": {"input": 0.10, "output": 0.40},
    "gemini-flash-latest": {"input": 0.10, "output": 0.40},
    "gemini-2.5-flash": {"input": 0.15, "output": 0.60},
    "gemini-2.5-pro": {"input": 1.25, "output": 10.0},
}


def calculate_cost(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    pricing = PRICING.get(model)
    if not pricing:
        # Fuzzy match: find a key that is a substring of model or vice versa
        model_lower = model.lower()
        for key, val in PRICING.items():
            if key in model_lower or model_lower in key:
                pricing = val
                break
    if not pricing:
        return 0.0
    return (
        prompt_tokens * pricing["input"] + completion_tokens * pricing["output"]
    ) / 1_000_000
