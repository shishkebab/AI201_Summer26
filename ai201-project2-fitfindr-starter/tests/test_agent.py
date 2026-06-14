import agent


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
    monkeypatch.setattr(agent, "suggest_outfit", lambda new_item, wardrobe: "Wear it with jeans.")
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
        "outfit": False,
        "fit_card": False,
    }

    def fake_estimate_price_fairness(item):
        calls["price"] = True
        return {}

    def fake_suggest_outfit(new_item, wardrobe):
        calls["outfit"] = True
        return "Should not run."

    def fake_create_fit_card(outfit, new_item):
        calls["fit_card"] = True
        return "Should not run."

    monkeypatch.setattr(agent, "search_listings", lambda **kwargs: [])
    monkeypatch.setattr(agent, "_generate_no_results_message", lambda parsed: "No matches. Try broadening the search.")
    monkeypatch.setattr(agent, "estimate_price_fairness", fake_estimate_price_fairness)
    monkeypatch.setattr(agent, "suggest_outfit", fake_suggest_outfit)
    monkeypatch.setattr(agent, "create_fit_card", fake_create_fit_card)

    session = agent.run_agent("designer ballgown size XXS under $5", {"items": []})

    assert session["error"] == "No matches. Try broadening the search."
    assert session["price_fairness"] is None
    assert session["outfit_suggestion"] is None
    assert session["fit_card"] is None
    assert calls == {"price": False, "outfit": False, "fit_card": False}


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
    monkeypatch.setattr(agent, "suggest_outfit", lambda new_item, wardrobe: "Outfit still works.")
    monkeypatch.setattr(agent, "create_fit_card", lambda outfit, new_item: "Fit card still works.")

    session = agent.run_agent("vintage graphic tee under $30", {"items": []})

    assert session["error"] is None
    assert session["price_fairness"]["verdict"] == "not enough data"
    assert session["outfit_suggestion"] == "Outfit still works."
    assert session["fit_card"] == "Fit card still works."
