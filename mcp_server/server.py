from mcp.server.fastmcp import FastMCP
from shared.config import AGENT_HOST
from shared.registry import AGENT_PORT
from shared.vote_vocabulary import validate_specialist_vote

mcp = FastMCP("art-appraisal-tools", port=AGENT_PORT, host=AGENT_HOST)


@mcp.tool()
def cast_vote(
    recommendation: str,
    confidence: float,
    primary_reason: str,
    secondary_reason: str,
) -> dict:
    """
    Cast your specialist vote for the final appraisal. Call this as your LAST action.

    Args:
        recommendation: Verdict AUTHENTICATE, VERIFY_FURTHER, or REJECT (legacy BUY/HOLD
            are accepted and mapped). An unrecognized value is rejected, not coerced.
        confidence: Your confidence from 0.0 (very uncertain) to 1.0 (certain).
        primary_reason: The single most important reason for your vote.
        secondary_reason: A supporting reason for your vote.

    Returns:
        Confirmed vote record.

    Raises:
        ValueError: recommendation or confidence is invalid (DP4: fail loud, no silent coercion).
    """
    rec = validate_specialist_vote(recommendation, confidence)
    return {
        "vote": rec,
        "confidence": round(float(confidence), 2),
        "reasons": [primary_reason, secondary_reason],
        "status": "VOTE_RECORDED",
    }


@mcp.tool()
def analyze_style(artist: str, medium: str, period: str) -> dict:
    """
    Analyzes the artistic style, technique, and historical period of an artwork.

    Args:
        artist: Name of the artist (e.g. "Claude Monet").
        medium: Medium used (e.g. "oil on canvas", "watercolor", "charcoal").
        period: Approximate period or year (e.g. "Impressionist", "1890s").

    Returns:
        A dict with style analysis including movement, technique, and rarity.
    """
    style_db = {
        "monet": {
            "movement": "French Impressionism",
            "technique": "En plein air, loose brushwork, light-capture",
            "rarity": "Very High — fewer than 2,500 known works",
            "condition_factors": ["canvas quality", "varnish age", "fading"],
        },
        "van gogh": {
            "movement": "Post-Impressionism",
            "technique": "Impasto, swirling strokes, vivid complementary colors",
            "rarity": "Extremely High — ~900 known paintings",
            "condition_factors": ["lead white stability", "canvas warping"],
        },
        "picasso": {
            "movement": "Cubism / Blue & Rose periods",
            "technique": "Geometric fragmentation, multiple viewpoints",
            "rarity": "High — prolific but many are institutional",
            "condition_factors": ["pigment oxidation", "paper acidity (drawings)"],
        },
    }
    artist_key = artist.lower()
    style_info = style_db.get(artist_key, {
        "movement": "Unknown / requires expert review",
        "technique": f"Analysis needed for {medium} work",
        "rarity": "Unknown",
        "condition_factors": ["general aging", "storage history"],
    })
    return {"artist": artist, "medium": medium, "period": period, "style_analysis": style_info}


@mcp.tool()
def assess_condition_factors(medium: str) -> dict:
    """
    Returns common condition risk factors for a given medium.

    Args:
        medium: The artwork's medium (e.g. "oil on canvas", "watercolor").

    Returns:
        A dict with condition assessment guidance.
    """
    risks = {
        "oil on canvas": ["cracking", "flaking", "yellowed varnish", "canvas sag"],
        "watercolor":    ["fading", "foxing", "paper brittleness", "humidity damage"],
        "oil on panel":  ["warping", "splitting", "insect damage"],
        "charcoal":      ["smudging", "fixative yellowing"],
        "pastel":        ["dust loss", "extreme fragility"],
    }
    return {
        "medium": medium,
        "condition_risks": risks.get(medium.lower(), ["general aging", "unknown factors"]),
        "recommended_assessment": "Professional conservation report required",
    }


@mcp.tool()
def check_provenance(artwork_title: str, artist: str) -> dict:
    """
    Investigates the provenance and ownership history of an artwork.

    Args:
        artwork_title: Title of the artwork (e.g. "Water Lilies").
        artist: Name of the artist (e.g. "Claude Monet").

    Returns:
        A dict with provenance chain, authenticity status, and red flags.
    """
    provenance_db = {
        ("water lilies", "monet"): {
            "authenticity": "Authenticated",
            "certification_body": "Wildenstein Plattner Institute",
            "chain_of_ownership": [
                "1906 — Purchased by collector Georges de Bellio, Paris",
                "1918 — Inherited by Victorine de Bellio",
                "1957 — Acquired by private Swiss collector",
                "1989 — Sold at Christie's, London (Lot 42)",
                "2010 — Present owner (anonymous)",
            ],
            "red_flags": [],
            "stolen_art_check": "Clear — not on Art Loss Register",
        },
        ("starry night", "van gogh"): {
            "authenticity": "Museum Collection",
            "certification_body": "MoMA, New York",
            "chain_of_ownership": [
                "1889 — Painted at Saint-Paul-de-Mausole asylum",
                "1941 — Acquired by MoMA via Lillie P. Bliss Bequest",
            ],
            "red_flags": ["This work is in a museum — any private sale would be suspicious"],
            "stolen_art_check": "N/A — institutional collection",
        },
    }
    key = (artwork_title.lower(), artist.lower())
    return provenance_db.get(key, {
        "authenticity": "Unverified — documentation required",
        "certification_body": "None on record",
        "chain_of_ownership": ["History unknown — seller documentation needed"],
        "red_flags": ["No provenance records found", "Due diligence required"],
        "stolen_art_check": "Not checked — submit to Art Loss Register",
    })


@mcp.tool()
def check_export_restrictions(country_of_origin: str) -> dict:
    """
    Checks if artwork from a country has export restrictions or repatriation claims.

    Args:
        country_of_origin: Country where the artwork originated (e.g. "France").

    Returns:
        A dict with legal status and any known restrictions.
    """
    restrictions = {
        "france": {
            "status": "Trésors Nationaux — may require export certificate",
            "risk": "Medium",
            "notes": "Works over 50 years old above value thresholds need Ministry approval",
        },
        "italy": {
            "status": "Strict export control under Cultural Heritage Code",
            "risk": "High",
            "notes": "Pre-1909 works almost never get export approval",
        },
        "egypt": {
            "status": "Near-total export ban on antiquities",
            "risk": "Very High",
            "notes": "UNESCO 1970 convention applies; active repatriation program",
        },
        "united states": {
            "status": "Generally unrestricted for post-1900 fine art",
            "risk": "Low",
            "notes": "NAGPRA applies to Native American cultural items",
        },
    }
    return restrictions.get(country_of_origin.lower(), {
        "status": "Unknown — consult an international art law specialist",
        "risk": "Unknown",
        "notes": "Export law varies significantly by country",
    })


@mcp.tool()
def get_auction_comparables(artist: str, medium: str, size_cm: str) -> dict:
    """
    Finds recent auction sales of comparable works by the same artist.

    Args:
        artist: Name of the artist.
        medium: Medium of the artwork (e.g. "oil on canvas").
        size_cm: Approximate size as "width x height" in cm (e.g. "60x80").

    Returns:
        A dict with recent comparable sales and price range.
    """
    auction_data = {
        "monet": {
            "recent_sales": [
                {"title": "Nymphéas",     "year_sold": 2024, "house": "Sotheby's",  "price_usd": 74_000_000},
                {"title": "Le Grand Canal","year_sold": 2023, "house": "Christie's", "price_usd": 56_000_000},
                {"title": "Meules",        "year_sold": 2019, "house": "Sotheby's",  "price_usd": 110_700_000},
            ],
            "price_range_usd": {"low": 1_000_000, "high": 120_000_000},
            "market_trend": "Strong upward — Impressionist demand remains robust",
            "liquidity": "High — global collector base",
        },
        "van gogh": {
            "recent_sales": [
                {"title": "Orchard with Blossoming Apricot Trees", "year_sold": 2022, "house": "Christie's", "price_usd": 28_000_000},
            ],
            "price_range_usd": {"low": 5_000_000, "high": 200_000_000},
            "market_trend": "Stable — institutional and private demand",
            "liquidity": "Medium-High — rarity limits supply",
        },
        "picasso": {
            "recent_sales": [
                {"title": "Femme assise près d'une fenêtre", "year_sold": 2021, "house": "Christie's", "price_usd": 103_400_000},
            ],
            "price_range_usd": {"low": 500_000, "high": 150_000_000},
            "market_trend": "Volatile — period-dependent (Blue Period commands premium)",
            "liquidity": "High — large volume of works",
        },
    }
    data = auction_data.get(artist.lower(), {
        "recent_sales": [],
        "price_range_usd": {"low": 0, "high": 0},
        "market_trend": "Insufficient data — specialist appraisal needed",
        "liquidity": "Unknown",
    })
    data["queried_for"] = {"artist": artist, "medium": medium, "size_cm": size_cm}
    return data


@mcp.tool()
def estimate_insurance_value(
    artist: str,
    estimated_auction_value_usd: int,
    condition: str,
) -> dict:
    """
    Estimates the insurance (replacement) value of an artwork.

    Args:
        artist: Name of the artist.
        estimated_auction_value_usd: Estimated auction hammer price in USD.
        condition: Condition of the artwork: "excellent", "good", "fair", or "poor".

    Returns:
        A dict with insurance value and annual premium estimate.
    """
    multipliers = {"excellent": 1.20, "good": 1.10, "fair": 0.85, "poor": 0.60}
    multiplier = multipliers.get(condition.lower(), 1.0)
    insurance_value = int(estimated_auction_value_usd * multiplier)
    return {
        "artist": artist,
        "estimated_auction_value_usd": estimated_auction_value_usd,
        "condition": condition,
        "insurance_value_usd": insurance_value,
        "annual_premium_range_usd": {
            "low":  int(insurance_value * 0.001),
            "high": int(insurance_value * 0.0025),
        },
        "notes": "Insurance value reflects full replacement cost including buyer's premium",
    }


if __name__ == "__main__":
    print(f"MCP tool server -> http://{AGENT_HOST}:{AGENT_PORT}/mcp")
    mcp.run(transport="streamable-http")
