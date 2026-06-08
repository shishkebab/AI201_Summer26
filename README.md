# The Unofficial Guide — Project 1

> **How to use this template:**
> Complete each section *after* you've built and tested the corresponding part of your system.
> Do not write placeholder text — if a section isn't done yet, leave it blank and come back.
> Every section below is required for submission. One-liners will not receive full credit.

---

## Domain

<!-- What topic or category of knowledge does your system cover?
     Why is this knowledge valuable, and why is it hard to find through official channels?
     Example: "Student reviews of CS professors at [university] — useful because official
     course descriptions don't reflect teaching style, exam difficulty, or workload." -->

Domain: I chose the student reviews of CS professors at University of Arizona as my domain.
Throught the interaction with the chat, students can easily compare teaching styles and exam difficulty 
of different professors withouth having to read the entire reviews of each professor.

---

## Document Sources

<!-- List every source you collected documents from.
     Be specific: include URLs, subreddit names, forum thread titles, or file names.
     Aim for variety — sources that together cover different subtopics or perspectives. -->

| # | Source | Type | URL or file path |
|---|--------|------|-----------------|
| 1 | Rate My Professor Website | text|https://www.ratemyprofessors.com/professor/2633139 |
| 2 | Rate My Professor Website| text|https://www.ratemyprofessors.com/professor/2713150 |
| 3 | Rate My Professor Website| text|https://www.ratemyprofessors.com/professor/787531 |
| 4 | Rate My Professor Website| text|https://www.ratemyprofessors.com/professor/2430005 |
| 5 | Rate My Professor Website| text|https://www.ratemyprofessors.com/professor/2298882 |
| 6 | Rate My Professor Website| text|https://www.ratemyprofessors.com/professor/510557 |
| 7 | Rate My Professor Website| text|https://www.ratemyprofessors.com/professor/2004717 |
| 8 | Rate My Professor Website| text|https://www.ratemyprofessors.com/professor/1815234 |
| 9 | Rate My Professor Website| text|https://www.ratemyprofessors.com/professor/2058047 |
| 10 |Rate My Professor Website| text|https://www.ratemyprofessors.com/professor/376230 |

---

## Chunking Strategy

<!-- Describe your chunking approach with enough specificity that someone else could reproduce it.
     Include:
     - Chunk size (characters or tokens) and why that size fits your documents
     - Overlap size and why (or why not) you used overlap
     - Any preprocessing you did before chunking (e.g., stripping HTML, removing headers)
     - What your final chunk count was across all documents -->

**Chunk size:** Each student review is separated and composed of approximately 500 characters. Therefore, the chunk size is 500 characters to contain full review of each student.

**Overlap:** About 75 characters close to the chunk boundary.

**Why these choices fit your documents:** Rate My Professor reviews are short summaries of the professor's teaching style and exam difficulty from student's perspective. One chunk should not mix multiple student reviews. A 500-word chunk is large enough to capture one student review including the review and the associated tags such as "Amazing lectures" and "Accessible outside class", etc.

**Final chunk count:** 928 (with final chunk size of 328 characters and 75 overlap characters)

---

## Embedding Model

<!-- Name the embedding model you used and explain your choice.
     Then answer: if you were deploying this system for real users and cost wasn't a constraint,
     what tradeoffs would you weigh in choosing a different model?
     Consider: context length limits, multilingual support, accuracy on domain-specific text,
     latency, and local vs. API-hosted. -->

**Model used:** all-MiniLM-L6-v2

**Production tradeoff reflection:** If cost was not an issue, a larger model definitely could be used to better understand vague student comment, informal grammar, or other languages. The tradeoff is that stronger models may be slower or require an API instead of running locally. For this project, the chosen model (all-MiniLM-L6-v2) is lightweight, fast, and accurate enough for short English review chunks. 

---

## Grounded Generation

<!-- Explain how your system enforces grounding — how does it prevent the LLM from answering
     beyond the retrieved documents?
     Describe both your system prompt (what instruction you gave the model) and any structural
     choices (e.g., how you formatted the context, whether you filtered low-relevance chunks).
     Do not just say "I told it to use the documents" — show the actual instruction or explain
     the mechanism. -->

**System prompt grounding instruction:**
I used the following system and citation prompt to guide the model to answer the question based on the provided contexts from RAG only. At the end of each answer, I will provide the professor name(s) that the answer is based on. If the answer is not found in the context, I will omit the citation entirely.

    citation_instruction = (
        "At the end of your answer, cite the professor name(s) your answer draws from using "
        "this exact format on its own line:\n\n"
        "  [Source: <professor_name>]\n\n"
        "If your answer draws from multiple reviews from different professors, list each on a separate line:\n\n"
        "  [Source: Professor A]\n"
        "  [Source: Professor B]\n\n"
        "Use only the professor names exactly as they appear in the Source labels in the "
        "context. If the answer is not found in the context, omit the citation entirely."
    )

    system_prompt = (
        "You are an assistant who helps find professor rating. Answer the user's question using ONLY "
        "the rule text provided in the context below. "
        "Do not use any knowledge about professors and college classes that is NOT explicitly stated in that context. "
        "Do not infer, speculate, or fill in gaps from general knowledge — even if you believe you know the answer. "
        "If the context only partially answers the question, answer only what the text supports and state that the rest is not covered. "
        "If the answer is not found in the context at all, say so and nothing more.\n\n"
        + citation_instruction
    )

**How source attribution is surfaced in the response:** I instrcuted the model to cite the professor name(s) that the answer is based on at the end of each answer. The final answer has the following format for the source. This is a real citation format from an answer:
`Melanie Lotz (2633139_Lotz.txt, 2633139_lotz_20)`

---

## Evaluation Report

<!-- Run your 5 test questions from planning.md through your system and record the results.
     Be honest — a partially accurate or inaccurate result that you explain well is more
     valuable than a suspiciously perfect result. -->

| # | Question | Expected answer | System response (summarized) | Retrieval quality | Response accuracy |
|---|----------|-----------------|------------------------------|-------------------|-------------------|
| 1 | What do students say about Abu Ahmed's teaching style and exam difficulty? | Straightforward and exams are at the same difficulty as homework. | Teaching style is boring, but the exams are easy | Partially relevant | Partially accurate |
| 2 | Is Christian Collberg a good choice for clear lectures and reasonable exams? | Yes, the professor makes the lecture interesting and the exams are reasonable | makes a great effort to keep the subject engaging, exams are described as extremely fair | Relevant | Accurate |
| 3 | Which professor has especially negative reviews about CSC335? | Melanie Lotz | Did not give specific name, but correct review and grounded in the material | Relevant | Partially accurate |
| 4 | Who teaches AI or ML/NLP classes? |Mihai Surdeanu  |Mihai Surdeanu | Relevant| Accurate|
| 5 | Which professor seems to have the highest difficulty for CSC252 and why?| Jonathan Misurda, because his teaching style is not organized (teaching backwards and forwards) | Jonathan Misurda, extremely hard with no structure to the course  | Relevant | Accurate |

**Retrieval quality:** Relevant / Partially relevant / Off-target  
**Response accuracy:** Accurate / Partially accurate / Inaccurate

---

## Failure Case Analysis

<!-- Identify at least one question where retrieval or generation did not work as expected.
     Write a specific explanation of *why* it failed, tied to a part of the pipeline.

     "The answer was wrong" is not an explanation.

     "The relevant information was split across a chunk boundary, so retrieval returned
     only half the context — the model didn't have enough to answer correctly" is an explanation.

     "The embedding model treated the professor's nickname as out-of-vocabulary and returned
     results from an unrelated review" is an explanation. -->

**Question that failed:**

**What the system returned:**

**Root cause (tied to a specific pipeline stage):**

**What you would change to fix it:**

---

## Spec Reflection

<!-- Reflect on how planning.md shaped your implementation.
     Answer both questions with at least 2–3 sentences each. -->

**One way the spec helped you during implementation:**

**One way your implementation diverged from the spec, and why:**

---

## AI Usage

<!-- Describe at least 2 specific instances where you used an AI tool during this project.
     For each: what did you give the AI as input, what did it produce, and what did you
     change, override, or direct differently?

     "I used Claude to help me code" is not sufficient.
     "I gave Claude my Chunking Strategy section from planning.md and asked it to implement
     chunk_text(). It returned a function using a fixed character split. I overrode the
     chunk size from 500 to 200 because my documents are short reviews, not long guides." -->

**Instance 1**

- *What I gave the AI:*
- *What it produced:*
- *What I changed or overrode:*

**Instance 2**

- *What I gave the AI:*
- *What it produced:*
- *What I changed or overrode:*
