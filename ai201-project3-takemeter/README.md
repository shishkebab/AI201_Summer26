# TakeMeter - README.md

---

## Community
Description of the community ("Jazz" subreddit), your labels, and why these distinctions matter to people in that community.

### Description of the cummunity
The Jazz subreddit (https://www.reddit.com/r/Jazz/) is a community where people share personal reactions to artists and albums, ask for help finding recordings or recommendations, recommend specific music, and post factual information about jazz history, releases, and events. 

### Labels and why the distinctions matter
My labels are Appreciation, Question, Recommendation, and Information, which separate emotional first-person posts from posts that ask the community, suggest something to hear, or provide concrete details. These distinctions matter because jazz fans use the subreddit in different ways: to discover music, learn context, solve listening or collecting questions, and connect over what the music means to them.

---

## Taxonomy (Label definitions)

### `information`
A post provides information or review about an event, jazz product, history. The information is backed up by specific statistics, quotes, date of the event, or other supporting evidence. 

**Key signal:** Provides information or review about jazz album, historical or current events. The information is backed up by specific statistics, quotes, date of the event, or other supporting evidence.

**Examples:** Jazz album information and reviews, history of jazz, interview with jazz musician, upcoming or past jazz concerts or festivals.

Example posts:
- "John Coltrane's Blue Train was recorded for Blue Note on September 15, 1957, with Lee Morgan, Curtis Fuller, Kenny Drew, Paul Chambers, and Philly Joe Jones."
- "Smalls Jazz Club in NYC has an extensive free online archive of thousands of live jazz shows that have performed there. It's worth checking out."

---

### `question`
A post asking for specific information or opinions.

**Key signal:** The post is asking for specific information or opinions from the audience.

**Examples:** Asking for opinions on a jazz album, asking for recommendations, asking for feedback on a jazz performance.

Example posts:
- "Does anyone know if an official recording for Estival Jazz Lugano 1998 exists, and where I might buy one?"
- "I'm trying to get into organ trio records. I know Jimmy Smith and a little Larry Young, but where should I go next if I want groove without it getting too lounge-y?"

---

### `appreciation`
A description on how the writer felt about a jazz song, album, or artist. It is writteen in the first-person point of view and how the writer feels about the content.

**Key signal:** Writer's own descriptive feeling or opinion towards a musician, album, or genre. Do now confuse this with the post that includes a review or information written by 3rd person. This label specifically refers to the writer's own feelings.

**Examples:** How writere feels about a jazz album, song, artist, or concert.

Example posts:
- "I finally got Wayne Shorter's Speak No Evil last night after bouncing off it for years. The title track used to feel too shadowy to me, but now those horns sound like a whole city at 1am."
- "A Love Supreme has become less of an album and more of a place I visit. I don't play it constantly, but when I do, it resets something in me."

---

### `recommendation`
A post recommending a specific jazz song, album, or artist.

**Key signal:** The post is recommending a specific jazz song, album, or artist to the audience.

**Examples:** Album recommendation, song recommendation, artist recommendation.

Example posts:
- "Strong recommendation: Joe Henderson's Page One. Blue Bossa is the famous tune, but the whole album is concise, melodic, and a perfect doorway into Henderson's sound."
- "If fusion has never clicked for you, try Herbie Hancock's Thrust before giving up. It grooves hard, the synth textures are funky instead of cheesy, and Mike Clark is ridiculous."

---

## How to Handle Ambiguous Cases

Some descriptions genuinely fit more than one label. That's intentional — it mirrors the real challenge of building labeled training data. Here's how to resolve common edge cases:

**Appreciation that recommends:** If a post is a description of how the writer felt about a jazz song, album, or artist, and the writer recommends the specific song, album, or artist, label it `recommendation`.

**Appreciation that gives information:** If a post is a description of how writer feels about an event, jazz product, or history, and the writer provides information about what they are talking about, `appreciation`. For example, a post that says "I really like this jazz album. Here is the album review", or "I like this artist, here is their biography", is an `appreciation` not an `information`.

**Information that recommends:** If a post is a description of an event, jazz product, or history, and the writer recommends the specific event, jazz product, or history, label it `recommendation`.

**Information that asks:** If a post is a description of an event, jazz product, or history, and the writer asks for audiences' opinions on the content he described, label it `Information`.

**Recommendation that asks:** If a post is a description of an event, jazz product, or history, and the writer asks for audiences' opinions on the content he described, label it `recommendation`.
---

## Valid Labels (for reference)

```
information
question
recommendation
appreciation
```

These are the only four valid labels. Use exactly these strings in `my_labels.json`.

---

## Hard Edge Cases

Some posts will be genuinely ambiguous because Reddit users often mix personal reaction, information, and recommendations in the same post. A post like "I love Idle Moments; it was recorded in 1963 with Joe Henderson and Bobby Hutcherson, and everyone should hear it" could fit `Appreciation`, `Information`, or `Recommendation`.

When I encounter an ambiguous post during annotation, I will label it by the main purpose of the post rather than by every feature it contains. If the main purpose is to tell people to listen, I will choose `Recommendation`; if the main purpose is personal feeling, I will choose `Appreciation`; if the main purpose is factual context, I will choose `Information`; and if the post is primarily asking the audience for a response, I will choose `Question`.

---

## Data Collection Plan

I will collect examples from the Jazz subreddit, especially posts about albums, artists, concerts, reissues, record collecting, listening advice, jazz history, and community discussion. I will collect 50 examples per label, for a total of 200 labeled examples across `Appreciation`, `Question`, `Recommendation`, and `Information`.

If one label is underrepresented after 200 examples, I will use targeted collection strategies instead of letting the dataset stay imbalanced. For example, I can search the subreddit for phrases like "recommend," "does anyone know," "recorded in," "RIP," "I love," or specific album and artist names, then collect more posts for the missing label until each label has roughly the same number of examples.

---

## Evaluation Metrics

I will use overall accuracy, but accuracy alone is not enough because a model can look good while mainly predicting the most common label. I will also use per-label precision and recall so I can see whether the classifier is reliable for each type of post, especially labels that are easy to confuse such as `Appreciation` and `Recommendation`.

I will use macro F1 score as the main summary metric because it gives each label equal weight and balances precision with recall. I will also inspect the confusion matrix because the most important errors for this task are label mix-ups, such as factual posts being mistaken for recommendations or personal reactions being mistaken for questions just because they include a final question.

---

## Definition of Success

This classifier would be genuinely useful if it achieved at least 80% accuracy, a macro F1 score of at least 0.75, and no label had very weak recall. Those results would make it useful for organizing posts into broad community functions, such as discovery, discussion, factual context, and appreciation.

For deployment in a real community tool, I would accept the model as good enough if it reached about 85% accuracy, a macro F1 score of 0.80 or higher, and at least 0.75 precision and recall for each label. I would still include manual review for low-confidence predictions because ambiguous jazz posts are common and the tool should support moderators or researchers rather than silently overrule human judgment.

---

## AI Tool Plan

### Label Stress-Testing

Before annotating the full dataset, I will give an AI tool my label definitions and hard edge case rules, then ask it to generate 5-10 realistic Jazz subreddit posts that sit near the boundary between two labels, such as `Appreciation` vs. `Recommendation`, `Information` vs. `Recommendation`, and `Question` vs. `Information`. I will manually classify those stress-test posts using my current rules; if several examples cannot be classified cleanly, I will tighten the definitions before labeling 200 examples.

### Annotation Assistance

I may use an LLM, such as ChatGPT or Codex, to pre-label batches of collected posts, but I will treat those labels as suggestions rather than final answers. To track this, I will keep a field or note for each example showing whether it was AI-pre-labeled and whether I accepted or changed the suggested label during human review.

### Failure Analysis

After evaluation, I will give an AI tool a list of wrong predictions, including the post text, true label, and predicted label, and ask it to identify patterns in the mistakes. I will look for repeated confusions such as recommendations being mislabeled as appreciation, factual posts with links being mislabeled as information even when they are asking a question, or short posts being classified only by keywords. I will verify any pattern myself by rereading the original examples and checking whether the error reflects a real model weakness, a weak label definition, or a mistake in my own annotation.

---

## Data Collection and Labeling

I collected examples from the Jazz subreddit, focusing on posts about jazz albums, artists, concerts, reissues, record collecting, listening advice, jazz history, and community discussion. The raw examples were organized in `data/raw_posts.txt`, then converted into `data/labeled_data.csv` with three columns: `text`, `label`, and `notes`.

I labeled each post according to the main purpose of the post, not every feature it contained. For example, if a post included both praise and factual details, I chose the label that best described the writer's main intent: personal reaction became `appreciation`, direct advice to listen became `recommendation`, audience requests became `question`, and factual context became `information`.

The final dataset has 200 total examples with a balanced label distribution:

- `appreciation`: 50 examples
- `question`: 50 examples
- `recommendation`: 50 examples
- `information`: 50 examples

Three difficult-to-label examples:

1. "Remembering a Jazz Legend today. He is one of my favourite artists, with bass clarinet and flute solos like human voices... Anyway, what are your favourites? Let's enjoy him today and always :)"
   - Decision: `appreciation`
   - Reason: The post ends with a question, but the main purpose is a personal tribute and emotional reaction to the artist.

2. "I always recommend Herbie Hancock's Speak Like a Child to people who want something lyrical but not sleepy. The horn colors are unusual and the compositions feel quietly luminous."
   - Decision: `recommendation`
   - Reason: The post includes personal praise, but the main action is telling others to listen to a specific album.

3. "Smalls Jazz Club in NYC has an extensive free online archive of thousands of live jazz shows that have performed there. It's worth checking out. https://www.smallslive.com/search/archive/"
   - Decision: `information`
   - Reason: The phrase "worth checking out" sounds like a recommendation, but the post mainly provides factual information about a jazz archive and includes a source link.

---

## Fine-tuning Approach

**Base Model:** `distilbert-base-uncased`
**Training Setup:** The Colab notebook loads the base model with a sequence-classification head for the four labels: `information`, `question`, `recommendation`, and `appreciation`. The dataset is read from the labeled CSV, converted from string labels to numeric IDs, and split into train, validation, and test sets using a stratified 70% / 15% / 15% split so each label stays balanced across the splits.

The text is tokenized with the DistilBERT tokenizer using truncation and a maximum length of 256 tokens, then trained with Hugging Face `Trainer`. The training setup uses `num_train_epochs=6`, `per_device_train_batch_size=8`, `per_device_eval_batch_size=32`, `learning_rate=2e-5`, `weight_decay=0.01`, and `warmup_steps=8`, with evaluation and checkpoint saving at the end of each epoch.

**Hyperparameter decisions:** One important hyperparameter decision was reducing the train batch size to 8 and using 6 epochs. Because this dataset has only 200 examples, a smaller batch size gives the model more update steps per epoch than a batch size of 16, and 6 epochs gives it more chances to learn subtle differences between labels such as `appreciation` and `recommendation`. I also used `warmup_steps=8` because the total number of training steps is small, so the large default warmup value (50) would spend too much of training below the intended learning rate.

---

## Baseline Description

### Prompt Used

SYSTEM_PROMPT = """
You are classifying posts from the Jazz subreddit.
Assign each post to exactly one of the following categories.

appreciation: An Appreciation post is a first-person reaction that focuses on how the writer feels about a jazz artist, album, song, performance, or style.
Example: "A Love Supreme has become less of an album and more of a place I visit. I don't play it constantly, but when I do, it resets something in me."

question: A Question post asks the community for information, opinions, identification help, buying advice, listening advice, or recommendations.
Example: "I'm trying to get into organ trio records. I know Jimmy Smith and a little Larry Young, but where should I go next if I want groove without it getting too lounge-y?"

recommendation: A Recommendation post tells other users to listen to, watch, buy, or check out a specific jazz artist, album, song, performance, or resource.
Example: "Strong recommendation: Joe Henderson's Page One. Blue Bossa is the famous tune, but the whole album is concise, melodic, and a perfect doorway into Henderson's sound."

information: An Information post provides factual or review-like context about jazz history, recordings, musicians, concerts, clubs, releases, or archives, usually with concrete details such as dates, personnel, sources, or links.
Example: "John Coltrane's Blue Train was recorded for Blue Note on September 15, 1957, with Lee Morgan, Curtis Fuller, Kenny Drew, Paul Chambers, and Philly Joe Jones."

Respond with ONLY the label name.
Do not explain your reasoning.
Do not include punctuation, markdown, or extra text.

Valid labels:
appreciation
question
recommendation
information
"""

### How results were collected

The baseline was run in the Colab notebook after the same stratified train / validation / test split used for fine-tuning. For each post in the test set, the notebook sent the system prompt plus a user message containing `Classify this post:` followed by the post text.

The Groq request used `temperature=0` and `max_tokens=20` to make responses deterministic and short. The returned text was lowercased and matched against the known labels in `LABEL_MAP`; responses that did not match a valid label were counted as unparseable and excluded from the baseline accuracy calculation.

The notebook collected all baseline predictions in `baseline_preds`, converted parseable string labels back into label IDs, and computed baseline accuracy with `accuracy_score`. It also printed a per-class `classification_report` so the baseline could be compared with the fine-tuned DistilBERT model beyond just overall accuracy.

---

## Evaluation Report

### Overall Metrics

The final test set contained 30 posts. In the saved evaluation results, both the zero-shot Groq baseline and the fine-tuned DistilBERT model reached perfect accuracy on this split.

| Model | Accuracy | Test examples | Notes |
|---|---:|---:|---|
| Zero-shot baseline (`llama-3.3-70b-versatile`) | 1.000 | 30 | Evaluated on 30/30 parseable responses |
| Fine-tuned model (`distilbert-base-uncased`) | 1.000 | 30 | Saved in `evaluation_results.json` |

### Per-Class Metrics

Baseline per-class metrics:

| Label | Precision | Recall | F1-score | Support |
|---|---:|---:|---:|---:|
| `information` | 1.00 | 1.00 | 1.00 | 8 |
| `question` | 1.00 | 1.00 | 1.00 | 7 |
| `recommendation` | 1.00 | 1.00 | 1.00 | 8 |
| `appreciation` | 1.00 | 1.00 | 1.00 | 7 |
| **Macro average** | **1.00** | **1.00** | **1.00** | **30** |
| **Weighted average** | **1.00** | **1.00** | **1.00** | **30** |

Final Fine-tuned model per-class metrics:

| Label | Precision | Recall | F1-score | Support |
|---|---:|---:|---:|---:|
| `information` | 1.00 | 1.00 | 1.00 | 8 |
| `question` | 1.00 | 1.00 | 1.00 | 7 |
| `recommendation` | 1.00 | 1.00 | 1.00 | 8 |
| `appreciation` | 1.00 | 1.00 | 1.00 | 7 |
| **Macro average** | **1.00** | **1.00** | **1.00** | **30** |
| **Weighted average** | **1.00** | **1.00** | **1.00** | **30** |

### Confusion Matrix

The final baseline confusion matrix was perfect on the 30-post test set:

| True label \ Predicted label | `information` | `question` | `recommendation` | `appreciation` |
|---|---:|---:|---:|---:|
| `information` | 8 | 0 | 0 | 0 |
| `question` | 0 | 7 | 0 | 0 |
| `recommendation` | 0 | 0 | 8 | 0 |
| `appreciation` | 0 | 0 | 0 | 7 |

Because the saved fine-tuned model accuracy was also 1.000 on the same 30-example test set, its final confusion matrix had no off-diagonal errors as well (`confusion_matrix_final.png`).

The initial confusion matrix with the default hyperparameters is shown below (`confusion_matrix_default_param.png`):

| True label \ Predicted label | `information` | `question` | `recommendation` | `appreciation` |
|---|---:|---:|---:|---:|
| `information` | 8 | 0 | 0 | 0 |
| `question` | 0 | 0 | 0 | 7 |
| `recommendation` | 1 | 0 | 0 | 7 |
| `appreciation` | 1 | 0 | 0 | 6 |

### Wrong Predictions and Analysis

Although the final saved run was perfect, an earlier low-confidence run produced 13 wrong predictions out of 30. I used those errors for failure analysis because they show which label boundaries are most fragile.

| Text excerpt | True label | Predicted label | Confidence | Analysis |
|---|---|---|---:|---|
| "Please hear Elvin Jones - Puttin' It Together if you mostly know him from Coltrane..." | `recommendation` | `appreciation` | 0.26 | The model focused on praise such as "Elvin sounds massive" instead of the command "Please hear," which is the recommendation cue. |
| "Are Japanese pressings worth the extra money for jazz vinyl, or is that mostly collector hype?..." | `question` | `appreciation` | 0.26 | The post includes personal uncertainty and taste language, but the main structure is a direct question asking the community for advice. |
| "An absolutely formative experience for me... Sun Ra's appearance is my favorite..." | `appreciation` | `information` | 0.26 | The post contains factual background about a jazz show, but the main purpose is a first-person emotional reaction. |

The main pattern is that `recommendation` is easy to confuse with `appreciation` when a recommendation includes enthusiastic descriptive language. Questions can also be mistaken for appreciation when they include personal opinions before or after the question.

### Sample Classifications

| Text excerpt | True label | Predicted label | Confidence | Correct? |
|---|---|---|---:|---|
| "Sun Ra moved from Birmingham to Chicago and later built the Arkestra..." | `information` | `question` | 0.26 | No |
| "I always recommend Herbie Hancock's Speak Like a Child..." | `recommendation` | `appreciation` | 0.26 | No |
| "Which Miles Davis electric album should I give another chance first?..." | `question` | `appreciation` | 0.26 | No |
| "John Coltrane's Blue Train was recorded for Blue Note on September 15, 1957..." | `information` | `information` | Not logged | Yes |

The correct `Blue Train` example is straightforward because it gives concrete recording information: date, label, personnel, and historical context. Those details match the `information` definition much more strongly than the other labels, since the post is not asking for help, giving a recommendation, or centering the writer's personal feelings.

---

## Reflection

### What the model learned vs. what you intended

I intended the model to learn the purpose of each Jazz subreddit post: whether the writer was sharing a personal reaction, asking the community for help, recommending something to listen to, or providing factual jazz information. In the final run, both the baseline and fine-tuned model matched those intended distinctions on the 30-example test set, which suggests the label definitions and examples were clear enough for the held-out data.

The earlier low-confidence run showed that the model did not automatically learn the deeper intent behind mixed-purpose posts. It often treated enthusiastic recommendation language as `appreciation`, and it sometimes treated questions with personal taste statements as `appreciation` too. That means the model initially learned surface cues like praise words, first-person language, and question-like phrasing more strongly than the annotation rule of "main purpose of the post."

After tuning the training setup, the model appeared to better separate the four categories, especially `recommendation` from `appreciation`. However, I would not assume the classifier has fully solved the task just because this test split reached 1.000 accuracy. The dataset is small and balanced, so a real deployment would need more naturally collected Reddit posts, especially edge cases where users combine personal reactions, factual context, and recommendations in one post.

---

## Spec Reflection

### One way the spec helped you

The spec helped by forcing the project to separate planning, labeling, baseline evaluation, fine-tuning, and reflection into distinct steps. That structure made it easier to check that the dataset had balanced labels, that the baseline and fine-tuned model used the same test split, and that the README reported more than just accuracy.

### One way implementation diverged from it and why

The implementation diverged from the simplest version of the spec because I adjusted the fine-tuning hyperparameters after seeing weak early predictions. Instead of keeping the default training setup, I used a smaller train batch size, more epochs, and a smaller warmup value because the dataset only had 200 examples and the first run showed low-confidence confusion between `recommendation`, `appreciation`, and `question`.

---

## AI usage section 

I used AI assistance to expand and organize the dataset. I directed the AI to read `raw_posts.txt` and `taxonomy.md`, then generate additional Jazz subreddit-style posts until each label had 50 examples. I reviewed the generated posts for whether they matched the intended labels, normalized the misspelled `<Qeustion>` header to `<Question>`, and converted the result into `labeled_data.csv` with `text`, `label`, and `notes` columns.

I also used AI assistance to stress-test the labeling scheme and write documentation. I asked the AI to identify patterns in wrong predictions from the earlier run, and I revised the README to distinguish between the final perfect evaluation and the earlier low-confidence failure analysis rather than presenting those errors as final results. I also asked for help drafting the zero-shot classification prompt, then kept the output constrained to only the valid label names because the notebook parser depended on exact label strings.

For annotation assistance, the AI helped generate and pre-organize synthetic examples, but the final label decisions followed my taxonomy rule of labeling by the main purpose of the post. Ambiguous examples were marked with notes in `labeled_data.csv`, especially posts that mixed personal appreciation, recommendations, questions, and factual information.
