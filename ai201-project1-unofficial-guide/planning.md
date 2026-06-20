<<<<<<< HEAD
# RulesBot — Planning Doc

Use this file to record your design decisions as you work through the lab.
There are no wrong answers — write enough that you could explain your reasoning to another group.
=======
# Project 1 Planning: The Unofficial Guide

> Write this document before you write any pipeline code.
> Your spec and architecture diagram are what you'll use to direct AI tools (Claude, Copilot, etc.) to generate your implementation — the more specific they are, the more useful the generated code will be.
> Update the Retrieval Approach and Chunking Strategy sections if you change your approach during implementation.
> Update this file before starting any stretch features.

---

## Domain

I chose the student reviews of CS professors at University of Arizona as my domain.
Throught the interaction with the chat, students can easily compare teaching styles and exam difficulty 
of different professors withouth having to read the entire reviews of each professor.

---

## Documents

<!-- List your specific sources: URLs, subreddit names, forum threads, or file descriptions.
     Aim for at least 10 sources that together cover different subtopics or perspectives within your domain. -->

| # | Source | Description | URL or location |
|---|--------|-------------|-----------------|
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
>>>>>>> ai201-project1-unofficial-guide-starter/main

---

## Chunking Strategy

<<<<<<< HEAD
**Chunk size:**


**Overlap:**


**Why this strategy fits rule book text:**


---

## Retrieval Observations

After implementing retrieval, try these test queries and record what comes back:

| Query | Top result game | Does it make sense? |
|-------|----------------|---------------------|
| "How do you win?" | | |
| "What happens when you roll a 7?" | | |
| "Can two players share a route?" | | |

**Anything surprising?**


---

## Response Quality

After implementing generation, try 2–3 questions and assess the answers:

| Query | Answer accurate? | Properly grounded? | Cited the right game? |
|-------|-----------------|-------------------|----------------------|
| | | | |
| | | | |

**What would you change about the prompt to improve grounding?**

=======
<!-- How will you split documents into chunks?
     State your chunk size (in tokens or characters), overlap size, and explain why those
     numbers fit the structure of your documents.
     A review-heavy corpus warrants different chunking than a long FAQ. -->

**Chunk size:** Each student review is separated and composed of approximately 500 characters. Therefore, the chunk size is 500 characters to contain full review of each student.

**Overlap:** About 75 characters close to the chunk boundary.

**Reasoning:** Rate My Professor reviews are short summaries of the professor's teaching style and exam difficulty from student's perspective. One chunk should not mix multiple student reviews. A 500-word chunk is large enough to capture one student review including the review and the associated tags such as "Amazing lectures" and "Accessible outside class", etc.

---

## Retrieval Approach

<!-- Which embedding model are you using (e.g., all-MiniLM-L6-v2 via sentence-transformers)?
     How many chunks will you retrieve per query (top-k)?
     If you were deploying this for real users and cost wasn't a constraint, what tradeoffs
     would you weigh in choosing a different embedding model — context length, multilingual
     support, accuracy on domain-specific text, latency? -->

**Embedding model:** all-MiniLM-L6-v2

**Top-k:** 5 chunks to retrive and compare reviews.

**Production tradeoff reflection:** If cost was not an issue, a larger model definitely could be used to better understand vague student comment, informal grammar, or other languages. The tradeoff is that stronger models may be slower or require an API instead of running locally. For this project, the chosen model (all-MiniLM-L6-v2) is lightweight, fast, and accurate enough for short English review chunks. 

---

## Evaluation Plan

<!-- List your 5 test questions with their expected correct answers.
     Questions should be specific enough that you can judge whether the system's response
     is right or wrong. "What are good dining halls?" is too vague.
     "What do students say about wait times at [dining hall name] during lunch?" is testable. -->

| # | Question | Expected answer |
|---|----------|-----------------|
| 1 | What do students say about \<professor name\>'s teaching style and exam difficulty? | [\<professor name\>: \<overall rating\>] \<professor name\>'s classes are homework-heavy, test-heavy, and difficult, while some positive reviews say his materials help students understand the subject. |
| 2 | Is \<professor name\> a good choice for clear lectures and reasonable exams? | [\<professor name\>: \<overall rating\>] Yes, based on the reviews. Students describe him as straightforward, respectful, and focused on course material. |
| 3 | Which professor has especially negative reviews about CSC335? | [\<professor name\>: \<overall rating\>] Reviews mention difficult exams, unclear project requirements, lecture-heavy classes, and tough grading. |
| 4 | Who teaches AI or ML/NLP classes? |[\<professor name\>: \<overall rating\>] (additional [\<professor name\>: \<overall rating\>] if multiple) \<professor name(s)> teach \<course name/number>|
| 5 | Which professor seems to have the highest difficulty for <class name/number> and why? |[\<professor name\>: \<overall rating\>] <professor name> appears to have the highest difficulty rating at about <rating>. Reviews mention test-heavy courses, many slides to study, weekly quizzes, and limited guidance for exams.  |

---

## Anticipated Challenges

<!-- What could go wrong? Name at least two specific risks with reasoning.
     Consider: noisy or inconsistent documents, missing source attribution, off-topic
     retrieval, chunks that split key information across boundaries. -->

1. Reviews with similar ratings but with different reasons (for e.g., both professors have ratings of 3.5, but the reasons for the ratings could be different.) might generate similar distance scores, generating incorrect response. 

2. Retrieval may return reviews from wrong professor if the query is broad, such as "Who has hard exams?" 

---

## Architecture

<!-- Draw a diagram of your pipeline showing the five stages:
     Document Ingestion → Chunking → Embedding + Vector Store → Retrieval → Generation
     Label each stage with the tool or library you're using.
     You can use ASCII art, a Mermaid diagram, or embed a sketch as an image.
     You'll use this diagram as context when prompting AI tools to implement each stage. -->

```text
+-------------+----------------------------+
| 1. Raw_data (document) collection         |
| Tool: Python, BeautifulSoup               |
| Source: Rate My Professors                |
| Remove HTML tags, navigation, buttons     |
| Output: raw professor pages in plaintext  |
+-------------+----------------------------+
              |
              v
+-----------------------------+
| 2. Ingestion & Chunking      |
| Tool: Claude, Python         |
| Chunk size: 500 characters   |
| Overlap: 75 characters       |
+-------------+---------------+
              |
              v
+-----------------------------+
| 3. Embedding + Vector Store  |
| Embedding: all-MiniLM-L6-v2  |
| Vector DB: ChromaDB          |
| Imbed Chunks + metadata      |
+-------------+---------------+
              |
              v
+-----------------------------+
| 4. Retrieval                 |
| Tool: ChromaDB               |
| Search top-k: 5 chunks       |
| Return most relevant reviews |
+-------------+---------------+
              |
              v
+-----------------------------+
| 5. Generation                |
| Tool: llama-3.3-70b-versatile|
| Input: user question +       |
| retrieved review chunks      |
| Output: grounded answer      |
+-----------------------------+
```
---

## AI Tool Plan

<!-- For each part of the pipeline below, describe:
     - Which AI tool you plan to use (Claude, Copilot, ChatGPT, etc.)
     - What you'll give it as input (which sections of this planning.md, which requirements)
     - What you expect it to produce
     - How you'll verify the output matches your spec

     "I'll use AI to help me code" is not a plan.
     "I'll give Claude my Chunking Strategy section and ask it to implement chunk_text()
     with my specified chunk size and overlap" is a plan. -->

**Milestone 3 — Ingestion and chunking:**
I will use Claude to help write Python code for collecting and cleaning the Rate My Professor review text (`preprocess` function). I will give Claude my Domain, Documents, and Chunking Strategy sections along with the 500-character chunk size, 75-character overlap, and requirement that chunks keep the review metadata (`chunk_text` function). 
I will verify the output by checking that chunks do not mix professors, each chunk contains one review, and the final chunk list includes the professor name and associated overall rating.

**Milestone 4 — Embedding and retrieval:**
I will use Claude to help implement the embedding and vector store pipeline. I will give Claude my Retrieval Approach section and ask it to use `sentence-transformers` with `all-MiniLM-L6-v2` and ChromaDB for vector storage. I expect it to produce code that embeds each chunk, stores the chunk text and metadata in ChromaDB, and retrieves the top 8 most relevant chunks for a user query. I will verify the output by printing the retrieved chunks and checking whether the they come from the correct professor and contain relevant reviews.

**Milestone 5 — Generation and interface:**
I will use Claude to help design the prompt and response format for the chatbot. I will provide it with system prompt so it knows the system must answer only from retrieved review chunks. I will also use Claude to design and implement functions that takes the user question and retrieved chunks, then returns a grounded answer that mentions professor names and course context. I will verify the output by running my five evaluation questions and checking that the answers are accurate and grounded.
>>>>>>> ai201-project1-unofficial-guide-starter/main
