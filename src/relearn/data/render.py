import math
import re
from typing import Any

PATTERN = re.compile(r"\{([^{}]+)\}")

FUNCS: dict[str, Any] = {
    "sqrt": math.sqrt,
    "cosd": lambda deg: math.cos(math.radians(deg)),
    "sind": lambda deg: math.sin(math.radians(deg)),
    "tand": lambda deg: math.tan(math.radians(deg)),
    "abs": abs,
    "round": round,
}


def _plain(value: Any) -> str:
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def render(text: str, params: dict[str, float | int]) -> str:
    def substitute(match: re.Match) -> str:
        expr, _, fmt = match.group(1).partition(":")
        value = eval(expr, {"__builtins__": {}}, {**FUNCS, **params})
        return format(value, fmt) if fmt else _plain(value)

    return PATTERN.sub(substitute, text)
