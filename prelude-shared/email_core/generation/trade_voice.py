"""
Default trade voice preset for email generation.

Chinese sales reps typically have no good English email history, so writing_style
analysis would either be empty or learn broken English. This curated preset
provides a professional trade voice as the fallback when no user-specific
writing style or email samples exist.
"""

TRADE_VOICE_PRESET = {
    "typicalLength": "2-3 short paragraphs, 50-80 words. Follow-ups: 25-50 words.",
    "formality": "Professional but direct, knowledgeable peer tone",
    "commonGreeting": "Hi,",
    "notableTraits": [
        "Lead with buyer-relevance, not self-promotion",
        "Include specific pricing (FOB and landed) upfront",
        "One clear, low-pressure CTA as a question",
        "No superlatives — replace with concrete data (specs, certifications, capacity)",
        "Retain factory-context markers (FOB terms, facility details) as authentic signals"
    ],
    "examples": [
        "I came across your company while researching the commercial lighting market on the West Coast.",
        "Our 600x600 LED Panel Light (40W) runs $4.85/unit FOB (landed ~$6.50/unit).",
        "Happy to send samples or a spec sheet if useful.",
        "Worth a conversation?"
    ]
}

TRADE_EMAIL_SAMPLES = [
    {
        "subject": "LED panels — competitive pricing for US importers",
        "body": "Hi,\n\nI came across your company while researching the commercial lighting market on the West Coast and thought there might be a good fit.\n\nOur 600x600 LED Panel Light (40W) runs $4.85/unit FOB (landed ~$6.50/unit) and our 6-inch Downlight (15W) is $3.20/unit FOB. UL, CE, and ISO 9001 certified.\n\nHappy to send samples or a spec sheet if useful — would that help?"
    },
    {
        "subject": "quick question on your fixture sourcing",
        "body": "Hi,\n\nWe supply LED fixtures to a few distributors in the Pacific Northwest and noticed your catalog overlaps with what we manufacture.\n\nWe're Zhongshan Haoyang — UL and ETL certified, 25-day lead time, MOQ 500 units. Our 40W panels run $4.85 FOB.\n\nWorth a conversation?"
    }
]
