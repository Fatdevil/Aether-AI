"""
Geographic market regions with ETF tickers for real price data.
"""

REGIONS = {
    "usa": {
        "ticker": "SPY",
        "name": "USA",
        "flag": "🇺🇸",
        "description": "Världens största ekonomi. Tech-dominerat, dollarstyrka.",
        "index_name": "S&P 500",
        "color": "#4facfe",
        "macro_drivers": ["Fed räntebesked", "Tech-sektorn (AI)", "Arbetsmarknad", "Dollarstyrka"],
    },
    "europe": {
        "ticker": "VGK",
        "name": "Europa",
        "flag": "🇪🇺",
        "description": "Exportberoende, försvarssatsning, ECB-politik.",
        "index_name": "STOXX 600",
        "color": "#0052cc",
        "macro_drivers": ["ECB räntepolitik", "Ukraina/försvar", "Energipriser", "EUR-styrka"],
    },
    "japan": {
        "ticker": "EWJ",
        "name": "Japan",
        "flag": "🇯🇵",
        "description": "Yen-försvagning, reflation, BOJ-politik.",
        "index_name": "Nikkei 225",
        "color": "#ff4757",
        "macro_drivers": ["BOJ normalisering", "Yen (JPY)", "Företagsreformer", "Export till Kina"],
    },
    "china": {
        "ticker": "MCHI",
        "name": "Kina",
        "flag": "🇨🇳",
        "description": "Stimulanspolitik, fastighetskris, geopolitisk risk.",
        "index_name": "CSI 300",
        "color": "#ff6348",
        "macro_drivers": ["Stimulanspaket", "Fastighetskris", "USA-tullar", "Tech-regulering"],
    },
    "india": {
        "ticker": "INDA",
        "name": "Indien",
        "flag": "🇮🇳",
        "description": "Snabbväxande, demografisk boom, infrastruktur.",
        "index_name": "Nifty 50",
        "color": "#ff9f43",
        "macro_drivers": ["BNP-tillväxt (~7%)", "Demografi", "Modi-reformer", "Utländska investeringar"],
    },
    "em": {
        "ticker": "EEM",
        "name": "Emerging Markets",
        "flag": "🌍",
        "description": "Tillväxtmarknader ex-Kina. Råvaruberoende.",
        "index_name": "MSCI EM",
        "color": "#2ed573",
        "macro_drivers": ["USD-styrka (negativt)", "Råvarupriser", "Kapitalflöden", "Kinas efterfrågan"],
    },
    "latam": {
        "ticker": "ILF",
        "name": "Latinamerika",
        "flag": "🌎",
        "description": "Brasilien-dominerat. Råvaror, räntor, politik.",
        "index_name": "MSCI LatAm",
        "color": "#1dd1a1",
        "macro_drivers": ["Räntor (Brasilien)", "Råvaruexport", "Politisk stabilitet", "USD/BRL"],
    },
    "asia_pac": {
        "ticker": "VPL",
        "name": "Asien-Stillahavet",
        "flag": "🌏",
        "description": "Australien, Sydkorea, Taiwan. Halvledare & råvaror.",
        "index_name": "MSCI Asia Pacific",
        "color": "#a55eea",
        "macro_drivers": ["Halvledarefterfrågan", "Kina-beroende", "Australien råvaror", "TSMC/Samsung"],
    },
}


def get_region_tickers() -> dict:
    """Return region_id -> ticker mapping."""
    return {rid: r["ticker"] for rid, r in REGIONS.items()}
