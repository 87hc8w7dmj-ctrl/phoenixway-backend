"""User-preference catalogues shared by /api/meta and /api/settings.

Rates are static reference rates (USD base) — a real deployment would refresh
them daily from an FX provider; caching them here keeps every price render
deterministic.
"""

RATES: dict[str, float] = {
    "USD": 1.0,
    "EUR": 0.92,
    "GBP": 0.79,
    "SEK": 10.60,
    "NOK": 10.90,
    "DKK": 6.85,
    "CHF": 0.88,
    "CAD": 1.36,
    "AUD": 1.52,
    "JPY": 152.0,
    "CNY": 7.25,
    "TRY": 34.20,
    "AED": 3.67,
    "INR": 83.40,
    "PLN": 4.00,
    "SGD": 1.35,
    "BRL": 5.40,
}

CURRENCIES = list(RATES.keys())

# code -> endonym shown in the language picker
LANGUAGES: dict[str, str] = {
    "en": "English",
    "sv": "Svenska",
    "ru": "Русский",
    "de": "Deutsch",
    "fr": "Français",
    "es": "Español",
    "it": "Italiano",
    "no": "Norsk",
    "da": "Dansk",
    "fi": "Suomi",
    "pl": "Polski",
    "nl": "Nederlands",
    "pt": "Português",
    "tr": "Türkçe",
    "ar": "العربية",
    "zh": "中文",
    "ja": "日本語",
}

REGIONS: dict[str, str] = {
    "US": "United States",
    "GB": "United Kingdom",
    "SE": "Sweden",
    "NO": "Norway",
    "DK": "Denmark",
    "FI": "Finland",
    "DE": "Germany",
    "FR": "France",
    "ES": "Spain",
    "IT": "Italy",
    "NL": "Netherlands",
    "PL": "Poland",
    "PT": "Portugal",
    "CH": "Switzerland",
    "TR": "Turkey",
    "AE": "United Arab Emirates",
    "IN": "India",
    "CN": "China",
    "JP": "Japan",
    "CA": "Canada",
    "AU": "Australia",
    "BR": "Brazil",
    "SG": "Singapore",
    "RU": "Russia",
}
