"""
Fetches every RateMyProfessors review for each professor listed in planning.md
and writes one plaintext .txt file per professor into documents/. The output is
shaped (one review per delimited block) so a later chunker can split it cleanly.

Source URLs are read from planning.md so it stays the single source of truth.
Data is pulled from RateMyProfessors' GraphQL API, which returns *all* reviews
with cursor pagination (the page HTML only embeds the 5 most-recent ones).
"""

import base64
import html
import pathlib
import re
import time

import requests

PLANNING_FILE = pathlib.Path("planning.md")
OUTPUT_DIR = pathlib.Path("documents")
GRAPHQL_URL = "https://www.ratemyprofessors.com/graphql"
AUTH_HEADER = "Basic dGVzdDp0ZXN0"  # public RMP token (test:test)
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)
PAGE_SIZE = 100  # ratings per GraphQL page
REQUEST_PAUSE = 1.0  # seconds between professors (be polite)

# GraphQL query: teacher aggregates + one page of ratings.
TEACHER_QUERY = """
query Teacher($id: ID!, $count: Int!, $after: String) {
  node(id: $id) {
    ... on Teacher {
      firstName
      lastName
      department
      school { name }
      avgRating
      avgDifficulty
      wouldTakeAgainPercent
      numRatings
      courseCodes { courseName courseCount }
      ratings(first: $count, after: $after) {
        pageInfo { hasNextPage endCursor }
        edges {
          node {
            class
            comment
            ratingTags
            clarityRating
            helpfulRating
            difficultyRating
          }
        }
      }
    }
  }
}
"""


def extract_professor_ids(planning_path):
    """Pull the numeric professor ids from the RateMyProfessors URLs in planning.md."""
    text = planning_path.read_text(encoding="utf-8")
    ids = re.findall(r"ratemyprofessors\.com/professor/(\d+)", text)
    seen = []
    for pid in ids:  # dedup, preserve order
        if pid not in seen:
            seen.append(pid)
    return seen


def teacher_node_id(pid):
    """Convert a numeric professor id into the base64 GraphQL node id."""
    return base64.b64encode(f"Teacher-{pid}".encode()).decode()


def run_query(session, node_id, after):
    """POST one GraphQL request and return the teacher node (raises on errors)."""
    payload = {
        "query": TEACHER_QUERY,
        "variables": {"id": node_id, "count": PAGE_SIZE, "after": after},
    }
    resp = session.post(GRAPHQL_URL, json=payload, timeout=30)
    resp.raise_for_status()
    body = resp.json()
    if body.get("errors"):
        raise RuntimeError(f"GraphQL errors: {body['errors']}")
    return body["data"]["node"]


def clean(text):
    """Unescape HTML entities and collapse whitespace into a single clean line."""
    if not text:
        return ""
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


def parse_tags(rating_tags):
    """Split the '--'-delimited ratingTags string into a clean list."""
    if not rating_tags:
        return []
    return [t.strip() for t in rating_tags.split("--") if t.strip()]


def fetch_teacher(session, pid):
    """Fetch teacher aggregates plus every review (paginated). None if not found."""
    node_id = teacher_node_id(pid)
    node = run_query(session, node_id, after=None)
    if not node:
        print(f"  [WARN] professor {pid} not found (null node)")
        return None

    reviews = []
    ratings = node["ratings"]
    while True:
        for edge in ratings["edges"]:
            r = edge["node"]
            clarity = r.get("clarityRating") or 0
            helpful = r.get("helpfulRating") or 0
            reviews.append(
                {
                    "course": r.get("class") or "N/A",
                    "quality": round((clarity + helpful) / 2, 1),
                    "difficulty": r.get("difficultyRating"),
                    "tags": parse_tags(r.get("ratingTags")),
                    "comment": clean(r.get("comment")),
                }
            )
        page = ratings["pageInfo"]
        if not page["hasNextPage"]:
            break
        node_page = run_query(session, node_id, after=page["endCursor"])
        ratings = node_page["ratings"]
        time.sleep(REQUEST_PAUSE)

    return {
        "pid": pid,
        "name": f"{node.get('firstName', '').strip()} {node.get('lastName', '').strip()}".strip(),
        "last_name": (node.get("lastName") or "").strip(),
        "department": node.get("department") or "",
        "school": (node.get("school") or {}).get("name", ""),
        "avg_rating": node.get("avgRating"),
        "avg_difficulty": node.get("avgDifficulty"),
        "would_take_again": node.get("wouldTakeAgainPercent"),
        "num_ratings": node.get("numRatings"),
        "courses": [c["courseName"] for c in (node.get("courseCodes") or [])],
        "reviews": reviews,
    }


def _fmt_num(value, suffix=""):
    """Format a possibly-missing numeric value."""
    return f"{value}{suffix}" if value is not None else "N/A"


def format_txt(data):
    """Render a professor's data as minimal, reviews-only plaintext."""
    dept = data["department"]
    school = data["school"]
    if dept and school:
        dept_line = f"{dept} — {school}"
    else:
        dept_line = dept or school or "N/A"

    wta = data["would_take_again"]
    wta_str = f"{round(wta, 1)}%" if wta is not None and wta >= 0 else "N/A"

    header = [
        f"Professor: {data['name']}",
        f"Department: {dept_line}",
        "Overall quality: {q}/5 | Difficulty: {d}/5 | Would take again: {w} | Ratings: {n}".format(
            q=_fmt_num(data["avg_rating"]),
            d=_fmt_num(data["avg_difficulty"]),
            w=wta_str,
            n=_fmt_num(data["num_ratings"]),
        ),
        f"Courses: {', '.join(data['courses']) if data['courses'] else 'N/A'}",
    ]

    # separator = "=" * 30
    blocks = ["\n".join(header)]
    # blocks = []
    for rev in data["reviews"]:
        tags = ", ".join(rev["tags"]) if rev["tags"] else "(none)"
        block = (
            f"Course: {rev['course']} | "
            f"Quality: {_fmt_num(rev['quality'])}/5 | "
            f"Difficulty: {_fmt_num(rev['difficulty'])}/5\n"
            f"Tags: {tags}\n"
            f"Review: {rev['comment']}"
        )
        blocks.append(block)

    # return f"\n\n{separator}\n\n".join(blocks) + "\n"
    return "\n\n".join(blocks) + "\n"


def write_professor_file(data):
    """Write one professor's plaintext to documents/{pid}_{LastName}.txt."""
    safe_last = re.sub(r"[^A-Za-z0-9]", "", data["last_name"]) or "Unknown"
    path = OUTPUT_DIR / f"{data['pid']}_{safe_last}.txt"
    path.write_text(format_txt(data), encoding="utf-8")
    return path


def main():
    OUTPUT_DIR.mkdir(exist_ok=True)
    pids = extract_professor_ids(PLANNING_FILE)
    print(f"Found {len(pids)} professor source(s) in {PLANNING_FILE}")

    session = requests.Session()
    session.headers.update(
        {
            "Authorization": AUTH_HEADER,
            "Content-Type": "application/json",
            "User-Agent": USER_AGENT,
        }
    )

    total_reviews = 0
    written = 0
    for pid in pids:
        try:
            data = fetch_teacher(session, pid)
            if data is None:
                continue
            path = write_professor_file(data)
            n = len(data["reviews"])
            total_reviews += n
            written += 1
            print(f"  [OK] {path.name} - {n} reviews")
        except Exception as exc:  # one failure shouldn't abort the batch
            print(f"  [FAIL] professor {pid} failed: {exc}")
        time.sleep(REQUEST_PAUSE)

    print(f"\nDone: {written}/{len(pids)} files, {total_reviews} reviews total -> {OUTPUT_DIR}/")


if __name__ == "__main__":
    main()
