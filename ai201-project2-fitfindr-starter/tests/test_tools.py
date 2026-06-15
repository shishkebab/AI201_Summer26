import tools
from tools import (
    create_fit_card,
    estimate_price_fairness,
    get_live_trend_context,
    retry_search_with_fallback,
    search_listings,
    style_profile_memory,
    suggest_outfit,
)
from utils.data_loader import get_empty_wardrobe, get_example_wardrobe


class FakeMessage:
    def __init__(self, content):
        self.content = content


class FakeChoice:
    def __init__(self, content):
        self.message = FakeMessage(content)


class FakeResponse:
    def __init__(self, content):
        self.choices = [FakeChoice(content)]


class FakeCompletions:
    def __init__(self, content):
        self.content = content
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return FakeResponse(self.content)


class FakeChat:
    def __init__(self, content):
        self.completions = FakeCompletions(content)


class FakeGroqClient:
    def __init__(self, content):
        self.chat = FakeChat(content)


def test_search_returns_results():
    results = search_listings("vintage graphic tee", size=None, max_price=50)

    assert isinstance(results, list)
    assert len(results) > 0
    assert results[0]["id"] == "lst_006"


def test_search_empty_results():
    results = search_listings("designer ballgown", size="XXS", max_price=5)

    assert results == []


def test_search_price_filter():
    results = search_listings("jacket", size=None, max_price=10)

    assert all(item["price"] <= 10 for item in results)


def test_retry_search_recovers_by_removing_size(monkeypatch):
    recovered_item = {"id": "lst_retry_size", "title": "Recovered Tee"}
    calls = []

    def fake_search(description, size=None, max_price=None):
        calls.append(
            {"description": description, "size": size, "max_price": max_price}
        )
        if size is None and max_price == 30:
            return [recovered_item]
        return []

    monkeypatch.setattr(tools, "search_listings", fake_search)

    result = retry_search_with_fallback("vintage graphic tee", size="XS", max_price=30)

    assert result["recovered"] is True
    assert result["results"] == [recovered_item]
    assert result["adjustments"] == ["removed size filter"]
    assert result["attempted_queries"][0]["size"] is None
    assert calls == [{"description": "vintage graphic tee", "size": None, "max_price": 30.0}]


def test_retry_search_recovers_by_raising_max_price(monkeypatch):
    recovered_item = {"id": "lst_retry_price", "title": "Recovered Jacket"}

    def fake_search(description, size=None, max_price=None):
        if description == "jacket" and size is None and max_price == 12.5:
            return [recovered_item]
        return []

    monkeypatch.setattr(tools, "search_listings", fake_search)

    result = retry_search_with_fallback("jacket", size=None, max_price=10)

    assert result["recovered"] is True
    assert result["results"] == [recovered_item]
    assert result["adjustments"] == ["raised max price by 25%"]
    assert result["attempted_queries"][0]["max_price"] == 12.5


def test_retry_search_returns_empty_when_all_attempts_fail(monkeypatch):
    monkeypatch.setattr(tools, "search_listings", lambda **kwargs: [])

    result = retry_search_with_fallback(
        "designer ballgown", size="XXS", max_price=5, max_attempts=3
    )

    assert result["recovered"] is False
    assert result["results"] == []
    assert result["adjustments"] == []
    assert len(result["attempted_queries"]) == 3
    assert "still found no matches" in result["message"]


def test_retry_search_records_attempted_queries(monkeypatch):
    monkeypatch.setattr(tools, "search_listings", lambda **kwargs: [])

    result = retry_search_with_fallback(
        "vintage graphic tee", size="XS", max_price=30, max_attempts=4
    )

    assert [attempt["adjustments"] for attempt in result["attempted_queries"]] == [
        ["removed size filter"],
        ["raised max price by 25%"],
        ["removed size filter and raised max price by 25%"],
        ["simplified description"],
    ]
    assert result["attempted_queries"][-1]["description"] == "vintage graphic"


def test_retry_search_catches_failed_attempt_and_continues(monkeypatch):
    recovered_item = {"id": "lst_retry_after_error", "title": "Recovered Item"}
    calls = []

    def fake_search(description, size=None, max_price=None):
        calls.append((description, size, max_price))
        if len(calls) == 1:
            raise RuntimeError("temporary search failure")
        if size == "XS" and max_price == 37.5:
            return [recovered_item]
        return []

    monkeypatch.setattr(tools, "search_listings", fake_search)

    result = retry_search_with_fallback(
        "vintage graphic tee", size="XS", max_price=30, max_attempts=3
    )

    assert result["recovered"] is True
    assert result["results"] == [recovered_item]
    assert result["attempted_queries"][0]["error"] == "temporary search failure"
    assert result["adjustments"] == ["raised max price by 25%"]


def test_suggest_outfit_with_wardrobe_uses_llm(monkeypatch):
    fake_client = FakeGroqClient(
        "Pair the graphic tee with baggy straight-leg jeans and chunky white sneakers."
    )
    monkeypatch.setattr(tools, "_get_groq_client", lambda: fake_client)
    new_item = search_listings("vintage graphic tee", size=None, max_price=50)[0]

    result = suggest_outfit(new_item, get_example_wardrobe())

    assert "baggy straight-leg jeans" in result
    call = fake_client.chat.completions.calls[0]
    assert call["model"] == "llama-3.3-70b-versatile"
    assert "User wardrobe:" in call["messages"][1]["content"]


def test_suggest_outfit_includes_style_profile(monkeypatch):
    fake_client = FakeGroqClient("Use the remembered streetwear preference.")
    monkeypatch.setattr(tools, "_get_groq_client", lambda: fake_client)
    new_item = search_listings("vintage graphic tee", size=None, max_price=50)[0]
    style_profile = {
        "preferred_style_tags": ["streetwear"],
        "preferred_colors": ["black"],
        "preferred_silhouettes": ["baggy"],
        "preferred_categories": ["tops"],
        "disliked_terms": ["preppy"],
    }

    result = suggest_outfit(new_item, get_example_wardrobe(), style_profile=style_profile)

    assert "streetwear" in result
    call = fake_client.chat.completions.calls[0]
    assert "Remembered style profile:" in call["messages"][1]["content"]
    assert "streetwear" in call["messages"][1]["content"]


def test_suggest_outfit_includes_trend_context(monkeypatch):
    fake_client = FakeGroqClient("Use baggy denim because it is trending.")
    monkeypatch.setattr(tools, "_get_groq_client", lambda: fake_client)
    new_item = search_listings("vintage graphic tee", size=None, max_price=50)[0]
    trend_context = {
        "confidence": "medium",
        "trending_tags": ["streetwear", "oversized"],
        "popular_styles": ["oversized streetwear"],
        "styling_cues": ["style with baggy denim"],
        "source_note": "Trend check: medium confidence.",
    }

    result = suggest_outfit(new_item, get_example_wardrobe(), trend_context=trend_context)

    assert "baggy denim" in result
    call = fake_client.chat.completions.calls[0]
    assert "Live trend context:" in call["messages"][1]["content"]
    assert "style with baggy denim" in call["messages"][1]["content"]


def test_suggest_outfit_empty_wardrobe_returns_general_advice(monkeypatch):
    fake_client = FakeGroqClient(
        "Style it with baggy jeans, chunky sneakers, and a denim jacket."
    )
    monkeypatch.setattr(tools, "_get_groq_client", lambda: fake_client)
    new_item = search_listings("vintage graphic tee", size=None, max_price=50)[0]

    result = suggest_outfit(new_item, get_empty_wardrobe())

    assert isinstance(result, str)
    assert result
    assert "baggy jeans" in result
    call = fake_client.chat.completions.calls[0]
    assert "wardrobe is empty" in call["messages"][1]["content"]


def test_suggest_outfit_empty_wardrobe_handles_llm_failure(monkeypatch):
    def raise_groq_error():
        raise ValueError("missing API key")

    monkeypatch.setattr(tools, "_get_groq_client", raise_groq_error)
    new_item = search_listings("vintage graphic tee", size=None, max_price=50)[0]

    result = suggest_outfit(new_item, get_empty_wardrobe())

    assert isinstance(result, str)
    assert result
    assert "generally" in result


def test_create_fit_card_returns_caption(monkeypatch):
    fake_client = FakeGroqClient(
        "This bootleg tee gives the whole fit a worn-in streetwear feel. "
        "Found on Depop for $24, it works with baggy denim and chunky sneakers."
    )
    monkeypatch.setattr(tools, "_get_groq_client", lambda: fake_client)
    new_item = search_listings("vintage graphic tee", size=None, max_price=50)[0]
    outfit = "Style it with baggy jeans, chunky sneakers, and a black denim jacket."

    result = create_fit_card(outfit, new_item)

    assert "Depop" in result
    call = fake_client.chat.completions.calls[0]
    assert call["model"] == "llama-3.3-70b-versatile"
    assert "Caption requirements:" in call["messages"][1]["content"]


def test_create_fit_card_empty_outfit_returns_error(monkeypatch):
    def fail_if_called():
        raise AssertionError("LLM should not be called for an empty outfit")

    monkeypatch.setattr(tools, "_get_groq_client", fail_if_called)
    new_item = search_listings("vintage graphic tee", size=None, max_price=50)[0]

    result = create_fit_card("   ", new_item)

    assert isinstance(result, str)
    assert "outfit suggestion was empty" in result


def test_estimate_price_fairness_returns_expected_shape():
    new_item = search_listings("vintage graphic tee", size=None, max_price=50)[0]

    result = estimate_price_fairness(new_item)

    assert set(result) == {
        "item_id",
        "item_price",
        "comparison_count",
        "average_comparable_price",
        "price_range",
        "verdict",
        "reasoning",
    }
    assert result["item_id"] == new_item["id"]
    assert result["item_price"] == new_item["price"]
    assert result["comparison_count"] >= 2
    assert result["verdict"] in {
        "good deal",
        "fair price",
        "priced high",
        "not enough data",
    }
    assert isinstance(result["reasoning"], str)
    assert result["reasoning"]


def test_estimate_price_fairness_missing_price_returns_not_enough_data():
    item = {
        "id": "test_missing_price",
        "title": "Test Tee",
        "category": "tops",
    }

    result = estimate_price_fairness(item)

    assert result["verdict"] == "not enough data"
    assert result["item_price"] is None
    assert result["comparison_count"] == 0
    assert "price" in result["reasoning"]


def test_estimate_price_fairness_missing_category_returns_not_enough_data():
    item = {
        "id": "test_missing_category",
        "title": "Test Tee",
        "price": 20,
    }

    result = estimate_price_fairness(item)

    assert result["verdict"] == "not enough data"
    assert result["item_price"] == 20
    assert result["comparison_count"] == 0
    assert "category" in result["reasoning"]


def test_estimate_price_fairness_no_comparable_listings():
    item = {
        "id": "test_no_comps",
        "title": "Rare Hat",
        "category": "hats",
        "price": 20,
        "style_tags": ["rare"],
        "colors": ["silver"],
        "brand": "Test Brand",
        "platform": "depop",
    }

    result = estimate_price_fairness(item)

    assert result["verdict"] == "not enough data"
    assert result["comparison_count"] == 0
    assert "avoid making a price claim" in result["reasoning"]


def test_estimate_price_fairness_weak_comparisons_are_low_confidence():
    item = {
        "id": "test_weak_comps",
        "title": "Plain Belt",
        "category": "accessories",
        "price": 10,
        "style_tags": ["plain"],
        "colors": ["magenta"],
        "brand": "No Match Brand",
        "platform": "depop",
    }

    result = estimate_price_fairness(item)

    assert result["verdict"] in {"good deal", "fair price", "priced high"}
    assert result["comparison_count"] >= 2
    assert "Low confidence" in result["reasoning"]


def test_style_profile_memory_load_missing_file_returns_default(tmp_path, monkeypatch):
    monkeypatch.setattr(tools, "_STYLE_PROFILE_PATH", tmp_path / "style_profiles.json")

    profile = style_profile_memory("demo_user", "load")

    assert profile["user_id"] == "demo_user"
    assert profile["preferred_style_tags"] == []
    assert profile["last_updated"] is None


def test_style_profile_memory_update_creates_and_merges_profile(tmp_path, monkeypatch):
    monkeypatch.setattr(tools, "_STYLE_PROFILE_PATH", tmp_path / "style_profiles.json")

    profile = style_profile_memory(
        "demo_user",
        "update",
        {
            "preferred_style_tags": ["streetwear", "vintage"],
            "preferred_colors": ["black"],
            "preferred_categories": ["tops"],
            "wardrobe_notes": "User likes baggy jeans.",
        },
    )
    loaded = style_profile_memory("demo_user", "load")

    assert profile["last_updated"]
    assert loaded["preferred_style_tags"] == ["streetwear", "vintage"]
    assert loaded["preferred_colors"] == ["black"]
    assert loaded["preferred_categories"] == ["tops"]
    assert loaded["wardrobe_notes"] == "User likes baggy jeans."


def test_style_profile_memory_repeated_updates_dedupe_values(tmp_path, monkeypatch):
    monkeypatch.setattr(tools, "_STYLE_PROFILE_PATH", tmp_path / "style_profiles.json")

    style_profile_memory(
        "demo_user",
        "update",
        {"preferred_style_tags": ["Streetwear", "vintage"]},
    )
    profile = style_profile_memory(
        "demo_user",
        "update",
        {"preferred_style_tags": ["streetwear", "Vintage", "grunge"]},
    )

    assert profile["preferred_style_tags"] == ["Streetwear", "vintage", "grunge"]


def test_style_profile_memory_malformed_json_returns_safe_default(tmp_path, monkeypatch):
    memory_path = tmp_path / "style_profiles.json"
    memory_path.write_text("{bad json", encoding="utf-8")
    monkeypatch.setattr(tools, "_STYLE_PROFILE_PATH", memory_path)

    profile = style_profile_memory("demo_user", "load")

    assert profile["preferred_style_tags"] == []
    assert "_warning" in profile


def test_style_profile_memory_invalid_action_returns_warning(tmp_path, monkeypatch):
    monkeypatch.setattr(tools, "_STYLE_PROFILE_PATH", tmp_path / "style_profiles.json")

    profile = style_profile_memory("demo_user", "delete")

    assert profile["user_id"] == "demo_user"
    assert "_warning" in profile
    assert "Unsupported" in profile["_warning"]


def test_get_live_trend_context_returns_medium_confidence_for_matching_posts():
    result = get_live_trend_context(
        description="vintage graphic tee",
        category="tops",
        size="L",
        platform="depop",
        lookback_days=14,
        max_posts=25,
    )

    assert result["platform"] == "depop"
    assert result["size_range"] == "L"
    assert result["sample_count"] >= 3
    assert result["confidence"] in {"medium", "high"}
    assert "streetwear" in result["trending_tags"]
    assert result["styling_cues"]


def test_get_live_trend_context_platform_failure_returns_fallback(monkeypatch):
    def raise_fetch_error(**kwargs):
        raise TimeoutError("rate limited")

    monkeypatch.setattr(tools, "_fetch_public_trend_posts", raise_fetch_error)

    result = get_live_trend_context("jacket", "outerwear", "M", "depop", 14, 25)

    assert result["confidence"] == "low"
    assert result["sample_count"] == 0
    assert result["trending_tags"] == []
    assert "failed" in result["reasoning"]


def test_get_live_trend_context_no_size_match_returns_fallback(monkeypatch):
    monkeypatch.setattr(
        tools,
        "_fetch_public_trend_posts",
        lambda **kwargs: [
            {
                "platform": "depop",
                "category": "tops",
                "size": "XXL",
                "tags": ["streetwear"],
                "styles": ["oversized streetwear"],
                "cues": ["style with baggy denim"],
            }
        ],
    )

    result = get_live_trend_context("graphic tee", "tops", "XS", "depop", 14, 25)

    assert result["confidence"] == "low"
    assert result["sample_count"] == 0
    assert "size range" in result["reasoning"]
