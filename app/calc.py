"""Macro Traco calculations.

The single metric that matters most is **$ / 30g protein** — how much money it
costs to obtain 30 grams of protein from a given food. All formulas below were
reverse-engineered from the live Google Sheet and verified against its rows.

Given a package:
    Price        = total price paid for the package      ($)
    Size         = total size of the package             (g, or unit count for eggs)
    ServingSize  = size of one serving                   (same unit as Size)
    Protein      = protein per serving                   (g)
    Calories     = calories per serving

Derived:
    servings_per_pack   = Size / ServingSize
    protein_per_pack    = servings_per_pack * Protein
    price_per_serving   = Price / servings_per_pack = Price * ServingSize / Size

    $ / 30g protein     = price_per_serving / Protein * 30
                        = Price * ServingSize * 30 / (Size * Protein)
    Calories / 30g      = Calories * 30 / Protein
    Serving size / 30g  = ServingSize * 30 / Protein
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class MacroStats:
    dollars_per_30g: float
    calories_per_30g: float
    serving_size_per_30g: float


def compute_stats(
    price: float,
    size: float,
    serving_size: float,
    protein: float,
    calories: float,
) -> MacroStats:
    """Compute the three derived metrics. Raises ValueError on bad inputs."""
    if size <= 0 or serving_size <= 0 or protein <= 0:
        raise ValueError("Size, Serving Size, and Protein must all be greater than 0.")

    dollars_per_30g = price * serving_size * 30.0 / (size * protein)
    calories_per_30g = calories * 30.0 / protein
    serving_size_per_30g = serving_size * 30.0 / protein

    return MacroStats(
        dollars_per_30g=round(dollars_per_30g, 4),
        calories_per_30g=round(calories_per_30g, 1),
        serving_size_per_30g=round(serving_size_per_30g, 1),
    )


def rank_against(value: float, existing_values: list[float]) -> dict:
    """Where would `value` (a $/30g) rank against existing $/30g values?

    Rank 1 = cheapest protein = best. Returns the 1-based rank the item would
    take, the total count after insertion, and how many it beats.
    """
    cleaned = sorted(v for v in existing_values if v is not None and v > 0)
    total_after = len(cleaned) + 1
    # Number of existing items strictly cheaper than ours sit ahead of us.
    better_than_us = sum(1 for v in cleaned if v < value)
    rank = better_than_us + 1
    beats = len(cleaned) - better_than_us  # existing items we are cheaper than
    return {
        "rank": rank,
        "total": total_after,
        "beats": beats,
        "percentile": round(100.0 * beats / len(cleaned), 1) if cleaned else 100.0,
    }


# --- Spreadsheet formula strings (written into new rows so the Sheet self-computes) ---
#
# Column layout (1-indexed): A Food Item, B Store, C Brand, D Category,
# E Form Factor, F Date, G Price, H Size, I Serving Size, J Protein/serving,
# K Calories, L $/30g, M Cal/30g, N Serving size/30g, O Rank.

def formulas_for_row(row: int, rank_range: str = "$L$2:$L$100000") -> dict[str, str]:
    """Return {column_letter: formula} for the calculated columns of `row`."""
    return {
        "L": f"=G{row}*I{row}*30/(H{row}*J{row})",
        "M": f"=K{row}*30/J{row}",
        "N": f"=I{row}*30/J{row}",
        "O": f"=RANK(L{row},{rank_range},1)",
    }
