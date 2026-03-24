"""
Sector definitions and analysis.
Maps major market sectors to ETFs and provides macro-driven sector scoring.
"""

# Major sectors with ETF tickers for real price data
SECTORS = {
    "tech": {
        "ticker": "XLK",
        "name": "Teknologi",
        "emoji": "💻",
        "description": "Halvledare, mjukvara, molntjänster, AI",
        "examples": "Apple, Microsoft, NVIDIA, Meta",
        "color": "#4facfe",
        "macro_drivers": ["Räntor (negativt korrelerat)", "Innovationscykel", "AI-investeringar"],
    },
    "financials": {
        "ticker": "XLF",
        "name": "Finans & Banker",
        "emoji": "🏦",
        "description": "Storbanker, försäkring, kapitalförvaltning",
        "examples": "JPMorgan, Goldman Sachs, Berkshire",
        "color": "#00e676",
        "macro_drivers": ["Räntenivå (positivt korrelerat)", "Kreditcykel", "Yieldkurvan"],
    },
    "defense": {
        "ticker": "ITA",
        "name": "Försvar & Flyg",
        "emoji": "🛡️",
        "description": "Vapensystem, cybersäkerhet, rymdindustri",
        "examples": "Lockheed Martin, Raytheon, Northrop Grumman",
        "color": "#ff6b6b",
        "macro_drivers": ["Geopolitisk spänning", "Försvarsbudgetar", "NATO-expansion"],
    },
    "energy": {
        "ticker": "XLE",
        "name": "Energi",
        "emoji": "⚡",
        "description": "Olja, gas, förnybar energi",
        "examples": "ExxonMobil, Chevron, Schlumberger",
        "color": "#ffd700",
        "macro_drivers": ["Oljepris", "OPEC-politik", "Energiomställning"],
    },
    "healthcare": {
        "ticker": "XLV",
        "name": "Hälsovård",
        "emoji": "🏥",
        "description": "Läkemedel, biotech, medicinsk utrustning",
        "examples": "UnitedHealth, Johnson & Johnson, Eli Lilly",
        "color": "#00f2fe",
        "macro_drivers": ["Demografisk utveckling", "Läkemedelspriser-politik", "Innovation (GLP-1 etc)"],
    },
    "consumer_disc": {
        "ticker": "XLY",
        "name": "Sällanköp",
        "emoji": "🛍️",
        "description": "Detaljhandel, bilar, lyx, resor",
        "examples": "Amazon, Tesla, Nike, McDonald's",
        "color": "#ff007f",
        "macro_drivers": ["Konsumentförtroende", "Arbetsmarknad", "Inflation påverkar köpkraft"],
    },
    "consumer_staples": {
        "ticker": "XLP",
        "name": "Dagligvaror",
        "emoji": "🛒",
        "description": "Mat, dryck, hygien – defensiv sektor",
        "examples": "Procter & Gamble, Coca-Cola, Walmart",
        "color": "#a29bfe",
        "macro_drivers": ["Recession-säker (defensiv)", "Inflationsgenomslag", "Stabil utdelning"],
    },
    "industrials": {
        "ticker": "XLI",
        "name": "Industri",
        "emoji": "🏭",
        "description": "Infrastruktur, transport, maskiner",
        "examples": "Caterpillar, Honeywell, Union Pacific",
        "color": "#fd79a8",
        "macro_drivers": ["PMI/ISM", "Infrastruktursinvesteringar", "Global handel"],
    },
    "materials": {
        "ticker": "XLB",
        "name": "Material",
        "emoji": "⛏️",
        "description": "Kemikalier, gruvdrift, byggmaterial",
        "examples": "Linde, Freeport-McMoRan, Nucor",
        "color": "#e17055",
        "macro_drivers": ["Råvarupriser", "Kinas efterfrågan", "Infrastruktur"],
    },
    "real_estate": {
        "ticker": "XLRE",
        "name": "Fastigheter",
        "emoji": "🏠",
        "description": "REITs, kommersiella fastigheter, bostäder",
        "examples": "Prologis, American Tower, Simon Property",
        "color": "#81ecec",
        "macro_drivers": ["Räntor (starkt negativt)", "Kontorsefterfrågan", "E-handel (lager)"],
    },
    "utilities": {
        "ticker": "XLU",
        "name": "Kraftförsörjning",
        "emoji": "💡",
        "description": "El, vatten, gas – defensiv, utdelning",
        "examples": "NextEra, Duke Energy, Southern Co",
        "color": "#636e72",
        "macro_drivers": ["Räntor (negativt, obligationsproxy)", "Reglering", "AI-datacenter-efterfrågan"],
    },
    "communication": {
        "ticker": "XLC",
        "name": "Kommunikation",
        "emoji": "📡",
        "description": "Media, telecom, sociala medier",
        "examples": "Alphabet, Meta, Netflix, Disney",
        "color": "#9d4edd",
        "macro_drivers": ["Annonsmarknad", "Streamingkrig", "AI-integration"],
    },
}


def get_sector_tickers() -> dict[str, str]:
    """Return sector_id -> ticker mapping."""
    return {sid: s["ticker"] for sid, s in SECTORS.items()}


def get_sector_info(sector_id: str) -> dict:
    """Return full sector configuration."""
    return SECTORS.get(sector_id, {})
