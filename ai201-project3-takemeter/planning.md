# TakeMeter - planning.md

---

## Community
Description of the community ("Jazz" subreddit), your labels, and why these distinctions matter to people in that community.

### Description of the cummunity
The Jazz subreddit (https://www.reddit.com/r/Jazz/) is a community where people share personal reactions to artists and albums, ask for help finding recordings or recommendations, recommend specific music, and post factual information about jazz history, releases, and events. 

### Labels and why the distinctions matter
My labels are Appreciation, Question, Recommendation, and Information, which separate emotional first-person posts from posts that ask the community, suggest something to hear, or provide concrete details. These distinctions matter because jazz fans use the subreddit in different ways: to discover music, learn context, solve listening or collecting questions, and connect over what the music means to them.

---

## Taxonomy (Label definitions)

### `Information`
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

### `recoommendation`
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
review
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
