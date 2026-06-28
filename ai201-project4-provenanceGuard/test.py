from signals import run_groq_llm_classifier, run_stylometric_heuristics
from scoring import combine_signals, label_for_attribution

samples = {
    "clearly_ai": """Artificial intelligence represents a transformative paradigm shift in modern society.
It is important to note that while the benefits of AI are numerous, it is equally
essential to consider the ethical implications. Furthermore, stakeholders across
various sectors must collaborate to ensure responsible deployment.""",

    "clearly_human": """ok so i finally tried that new ramen place downtown and honestly?
underwhelming. the broth was fine but they put WAY too much sodium in it and
i was thirsty for like three hours after. my friend got the spicy version and
said it was better. probably won't go back unless someone drags me there""",

    "formal_human_borderline": """The relationship between monetary policy and asset price inflation has been
extensively studied in the literature. Central banks face a fundamental tension
between their mandate for price stability and the unintended consequences of
prolonged low interest rates on equity and real estate valuations.""",

    "edited_ai_borderline": """I've been thinking a lot about remote work lately. There are genuine tradeoffs —
flexibility and no commute on one side, isolation and blurred work-life boundaries
on the other. Studies show productivity varies widely by individual and role type."""
}

for name, text in samples.items():
    groq = run_groq_llm_classifier(text)
    stylo = run_stylometric_heuristics(text)
    decision = combine_signals([groq, stylo])

    print("\n---", name)
    print("Groq score:", groq["ai_likelihood"], "| status:", groq["status"])
    print("Stylometric score:", round(stylo["ai_likelihood"], 3), "| quality:", stylo["quality"])
    print("Combined:", decision["combined_ai_likelihood"])
    print("Confidence:", decision["confidence_score"])
    print("Attribution:", decision["attribution"])
    print("Label:", label_for_attribution(decision["attribution"]))
