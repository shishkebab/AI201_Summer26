import agent
import tools


def default_profile(user_id="demo_user"):
    return {
        "user_id": user_id,
        "preferred_style_tags": [],
        "preferred_colors": [],
        "preferred_silhouettes": [],
        "preferred_categories": [],
        "budget_notes": None,
        "wardrobe_notes": None,
        "disliked_terms": [],
        "last_updated": None,
    }


def test_run_agent_stores_price_fairness(monkeypatch):
    selected_item = {
        "id": "lst_test",
        "title": "Test Graphic Tee",
        "category": "tops",
        "price": 24,
        "size": "L",
        "condition": "good",
        "style_tags": ["graphic tee", "vintage"],
        "colors": ["black"],
        "brand": None,
        "platform": "depop",
        "description": "A test tee.",
    }

    def fake_estimate_price_fairness(item):
        assert item is selected_item
        return {
            "item_id": item["id"],
            "item_price": item["price"],
            "comparison_count": 3,
            "average_comparable_price": 25,
            "price_range": {"min": 18, "max": 30},
            "verdict": "fair price",
            "reasoning": "Comparable prices are close.",
        }

    monkeypatch.setattr(agent, "search_listings", lambda **kwargs: [selected_item])
    monkeypatch.setattr(agent, "estimate_price_fairness", fake_estimate_price_fairness)
    monkeypatch.setattr(agent, "style_profile_memory", lambda user_id, action, profile_update=None: default_profile(user_id))
    monkeypatch.setattr(agent, "get_live_trend_context", lambda **kwargs: {"confidence": "medium", "styling_cues": ["style with baggy denim"]})
    monkeypatch.setattr(agent, "suggest_outfit", lambda new_item, wardrobe, style_profile=None, trend_context=None: "Wear it with jeans.")
    monkeypatch.setattr(agent, "create_fit_card", lambda outfit, new_item: "Fit card caption.")

    session = agent.run_agent("vintage graphic tee under $30", {"items": []})

    assert session["error"] is None
    assert session["selected_item"] is selected_item
    assert session["price_fairness"]["verdict"] == "fair price"
    assert session["outfit_suggestion"] == "Wear it with jeans."
    assert session["fit_card"] == "Fit card caption."


def test_run_agent_no_results_skips_downstream_tools(monkeypatch):
    calls = {
        "price": False,
        "trend": False,
        "outfit": False,
        "fit_card": False,
    }

    def fake_estimate_price_fairness(item):
        calls["price"] = True
        return {}

    def fake_suggest_outfit(new_item, wardrobe):
        calls["outfit"] = True
        return "Should not run."

    def fake_get_live_trend_context(**kwargs):
        calls["trend"] = True
        return {}

    def fake_create_fit_card(outfit, new_item):
        calls["fit_card"] = True
        return "Should not run."

    memory_actions = []

    def fake_style_profile_memory(user_id, action, profile_update=None):
        memory_actions.append(action)
        return default_profile(user_id)

    monkeypatch.setattr(agent, "search_listings", lambda **kwargs: [])
    monkeypatch.setattr(agent, "_generate_no_results_message", lambda parsed: "No matches. Try broadening the search.")
    monkeypatch.setattr(agent, "style_profile_memory", fake_style_profile_memory)
    monkeypatch.setattr(agent, "estimate_price_fairness", fake_estimate_price_fairness)
    monkeypatch.setattr(agent, "get_live_trend_context", fake_get_live_trend_context)
    monkeypatch.setattr(agent, "suggest_outfit", fake_suggest_outfit)
    monkeypatch.setattr(agent, "create_fit_card", fake_create_fit_card)

    session = agent.run_agent("designer ballgown size XXS under $5", {"items": []})

    assert session["error"] == "No matches. Try broadening the search."
    assert session["price_fairness"] is None
    assert session["trend_context"] is None
    assert session["outfit_suggestion"] is None
    assert session["fit_card"] is None
    assert memory_actions == ["load"]
    assert calls == {"price": False, "trend": False, "outfit": False, "fit_card": False}


def test_run_agent_price_fairness_not_enough_data_continues(monkeypatch):
    selected_item = {
        "id": "lst_test",
        "title": "Test Graphic Tee",
        "category": "tops",
        "price": 24,
        "size": "L",
        "condition": "good",
        "style_tags": ["graphic tee", "vintage"],
        "colors": ["black"],
        "brand": None,
        "platform": "depop",
        "description": "A test tee.",
    }

    monkeypatch.setattr(agent, "search_listings", lambda **kwargs: [selected_item])
    monkeypatch.setattr(agent, "style_profile_memory", lambda user_id, action, profile_update=None: default_profile(user_id))
    monkeypatch.setattr(agent, "get_live_trend_context", lambda **kwargs: {"confidence": "low", "styling_cues": []})
    monkeypatch.setattr(
        agent,
        "estimate_price_fairness",
        lambda item: {
            "item_id": item["id"],
            "item_price": item["price"],
            "comparison_count": 0,
            "average_comparable_price": None,
            "price_range": {"min": None, "max": None},
            "verdict": "not enough data",
            "reasoning": "Not enough comparable listings.",
        },
    )
    monkeypatch.setattr(agent, "suggest_outfit", lambda new_item, wardrobe, style_profile=None, trend_context=None: "Outfit still works.")
    monkeypatch.setattr(agent, "create_fit_card", lambda outfit, new_item: "Fit card still works.")

    session = agent.run_agent("vintage graphic tee under $30", {"items": []})

    assert session["error"] is None
    assert session["price_fairness"]["verdict"] == "not enough data"
    assert session["outfit_suggestion"] == "Outfit still works."
    assert session["fit_card"] == "Fit card still works."


def test_run_agent_two_interactions_reuse_style_memory(tmp_path, monkeypatch):
    memory_path = tmp_path / "style_profiles.json"
    monkeypatch.setattr(tools, "_STYLE_PROFILE_PATH", memory_path)
    selected_tee = {
        "id": "lst_tee",
        "title": "Black Graphic Tee",
        "category": "tops",
        "price": 24,
        "size": "L",
        "condition": "good",
        "style_tags": ["streetwear", "vintage", "graphic tee"],
        "colors": ["black"],
        "brand": None,
        "platform": "depop",
        "description": "A test tee.",
    }
    selected_jacket = {
        "id": "lst_jacket",
        "title": "Black Streetwear Jacket",
        "category": "outerwear",
        "price": 45,
        "size": "M",
        "condition": "good",
        "style_tags": ["streetwear", "vintage"],
        "colors": ["black"],
        "brand": None,
        "platform": "depop",
        "description": "A test jacket.",
    }
    seen_profiles = []

    def fake_search(**kwargs):
        if "jacket" in kwargs["description"].lower():
            return [selected_jacket]
        return [selected_tee]

    def fake_suggest_outfit(new_item, wardrobe, style_profile=None, trend_context=None):
        seen_profiles.append(style_profile)
        return "Use baggy jeans and chunky sneakers."

    monkeypatch.setattr(agent, "search_listings", fake_search)
    monkeypatch.setattr(agent, "estimate_price_fairness", lambda item: {"verdict": "fair price"})
    monkeypatch.setattr(agent, "get_live_trend_context", lambda **kwargs: {"confidence": "medium", "trending_tags": ["streetwear"], "popular_styles": ["oversized streetwear"], "styling_cues": ["style with baggy denim"]})
    monkeypatch.setattr(agent, "suggest_outfit", fake_suggest_outfit)
    monkeypatch.setattr(agent, "create_fit_card", lambda outfit, new_item: "Fit card caption.")

    first = agent.run_agent(
        "I like oversized streetwear, black pieces, baggy jeans, and chunky sneakers. Find me a vintage graphic tee under $30.",
        {"items": []},
        user_id="demo_user",
    )
    second = agent.run_agent("Find me a jacket under $50.", {"items": []}, user_id="demo_user")

    assert first["memory_warning"] is None
    assert second["memory_warning"] is None
    assert "streetwear" in second["style_profile"]["preferred_style_tags"]
    assert "black" in second["style_profile"]["preferred_colors"]
    assert seen_profiles[0]["preferred_style_tags"] == []
    assert "streetwear" in seen_profiles[1]["preferred_style_tags"]


def test_run_agent_memory_load_failure_sets_warning_and_continues(monkeypatch):
    selected_item = {
        "id": "lst_test",
        "title": "Test Graphic Tee",
        "category": "tops",
        "price": 24,
        "size": "L",
        "condition": "good",
        "style_tags": ["graphic tee", "vintage"],
        "colors": ["black"],
        "brand": None,
        "platform": "depop",
        "description": "A test tee.",
    }

    def fake_memory(user_id, action, profile_update=None):
        if action == "load":
            raise OSError("cannot read")
        return default_profile(user_id)

    monkeypatch.setattr(agent, "style_profile_memory", fake_memory)
    monkeypatch.setattr(agent, "search_listings", lambda **kwargs: [selected_item])
    monkeypatch.setattr(agent, "estimate_price_fairness", lambda item: {"verdict": "fair price"})
    monkeypatch.setattr(agent, "get_live_trend_context", lambda **kwargs: {"confidence": "medium", "styling_cues": ["style with baggy denim"]})
    monkeypatch.setattr(agent, "suggest_outfit", lambda new_item, wardrobe, style_profile=None, trend_context=None: "Outfit works.")
    monkeypatch.setattr(agent, "create_fit_card", lambda outfit, new_item: "Fit card works.")

    session = agent.run_agent("vintage graphic tee under $30", {"items": []})

    assert session["error"] is None
    assert session["memory_warning"]
    assert session["outfit_suggestion"] == "Outfit works."
    assert session["fit_card"] == "Fit card works."


def test_run_agent_memory_save_failure_keeps_final_response(monkeypatch):
    selected_item = {
        "id": "lst_test",
        "title": "Test Graphic Tee",
        "category": "tops",
        "price": 24,
        "size": "L",
        "condition": "good",
        "style_tags": ["graphic tee", "vintage"],
        "colors": ["black"],
        "brand": None,
        "platform": "depop",
        "description": "A test tee.",
    }

    def fake_memory(user_id, action, profile_update=None):
        if action == "update":
            raise OSError("cannot write")
        return default_profile(user_id)

    monkeypatch.setattr(agent, "style_profile_memory", fake_memory)
    monkeypatch.setattr(agent, "search_listings", lambda **kwargs: [selected_item])
    monkeypatch.setattr(agent, "estimate_price_fairness", lambda item: {"verdict": "fair price"})
    monkeypatch.setattr(agent, "get_live_trend_context", lambda **kwargs: {"confidence": "medium", "styling_cues": ["style with baggy denim"]})
    monkeypatch.setattr(agent, "suggest_outfit", lambda new_item, wardrobe, style_profile=None, trend_context=None: "Outfit works.")
    monkeypatch.setattr(agent, "create_fit_card", lambda outfit, new_item: "Fit card works.")

    session = agent.run_agent("vintage graphic tee under $30", {"items": []})

    assert session["error"] is None
    assert session["memory_warning"]
    assert session["selected_item"] == selected_item
    assert session["price_fairness"] == {"verdict": "fair price"}
    assert session["outfit_suggestion"] == "Outfit works."
    assert session["fit_card"] == "Fit card works."
