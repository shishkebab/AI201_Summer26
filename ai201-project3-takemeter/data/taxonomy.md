# Podcast Format Taxonomy

Use these four labels when annotating `train_episodes.json`. Each label captures the structural format of the episode — not the topic, production quality, or tone.

---

## Labels

### `Information`
A post provides information or review about an event, jazz product, history. The information is backed up by specific statistics, quotes, date of the event, or other supporting evidence. 

**Key signal:** Provides information or review about jazz album, historical or current events. The information is backed up by specific statistics, quotes, date of the event, or other supporting evidence.

**Examples:** Jazz album information and reviews, history of jazz, interview with jazz musician, upcoming or past jazz concerts or festivals.

---

### `question`
A post asking for specific information or opinions.

**Key signal:** The post is asking for specific information or opinions from the audience.

**Examples:** Asking for opinions on a jazz album, asking for recommendations, asking for feedback on a jazz performance.

---

### `appreciation`
A description on how the writer felt about a jazz song, album, or artist. It is writteen in the first-person point of view and how the writer feels about the content.

**Key signal:** Writer's own descriptive feeling or opinion towards a musician, album, or genre. Do now confuse this with the post that includes a review or information written by 3rd person. This label specifically refers to the writer's own feelings.

**Examples:** How writere feels about a jazz album, song, artist, or concert.

---

### `recoommendation`
A post recommending a specific jazz song, album, or artist.

**Key signal:** The post is recommending a specific jazz song, album, or artist to the audience.

**Examples:** Album recommendation, song recommendation, artist recommendation.

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
