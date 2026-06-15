import json

import agent


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


def selected_item():
    return {
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


class FakeFunction:
    def __init__(self, name, arguments):
        self.name = name
        self.arguments = arguments


class FakeToolCall:
    def __init__(self, name, arguments="{}", call_id=None):
        self.id = call_id or f"call_{name}"
        self.function = FakeFunction(name, arguments)


class FakeMessage:
    def __init__(self, content=None, tool_calls=None):
        self.content = content
        self.tool_calls = tool_calls


class FakeChoice:
    def __init__(self, message):
        self.message = message


class FakeResponse:
    def __init__(self, message):
        self.choices = [FakeChoice(message)]


class FakeCompletions:
    def __init__(self, messages):
        self.messages = messages
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if not self.messages:
            return FakeResponse(FakeMessage(content="Done."))
        return FakeResponse(self.messages.pop(0))


class FakeChat:
    def __init__(self, messages):
        self.completions = FakeCompletions(messages)


class FakeGroqClient:
    def __init__(self, messages):
        self.chat = FakeChat(messages)


def tool_message(name, args=None, raw_args=None):
    arguments = raw_args if raw_args is not None else json.dumps(args or {})
    return FakeMessage(tool_calls=[FakeToolCall(name, arguments)])


def tool_messages(*calls):
    return FakeMessage(tool_calls=list(calls))


def install_common_tool_fakes(monkeypatch, item=None):
    item = item or selected_item()
    memory_actions = []

    def fake_style_profile_memory(user_id, action, profile_update=None):
        memory_actions.append(action)
        return default_profile(user_id)

    monkeypatch.setattr(agent, "style_profile_memory", fake_style_profile_memory)
    monkeypatch.setattr(agent, "estimate_price_fairness", lambda item: {"verdict": "fair price"})
    monkeypatch.setattr(
        agent,
        "get_live_trend_context",
        lambda **kwargs: {
            "confidence": "medium",
            "styling_cues": ["style with baggy denim"],
        },
    )
    monkeypatch.setattr(
        agent,
        "suggest_outfit",
        lambda new_item, wardrobe, style_profile=None, trend_context=None: "Wear it with jeans.",
    )
    monkeypatch.setattr(
        agent,
        "create_fit_card",
        lambda outfit, new_item: "Fit card caption.",
    )
    return item, memory_actions


def test_run_agent_llm_tool_calls_populate_session(monkeypatch):
    item, memory_actions = install_common_tool_fakes(monkeypatch)
    fake_client = FakeGroqClient(
        [
            tool_message(
                "search_listings",
                {"description": "vintage graphic tee", "size": None, "max_price": 30},
            ),
            tool_messages(
                FakeToolCall("estimate_price_fairness"),
                FakeToolCall("get_live_trend_context"),
                FakeToolCall("suggest_outfit"),
                FakeToolCall("create_fit_card"),
            ),
            FakeMessage(content="Found a tee and made a fit card."),
        ]
    )

    monkeypatch.setattr(agent, "_get_groq_client", lambda: fake_client)
    monkeypatch.setattr(agent, "search_listings", lambda **kwargs: [item])

    session = agent.run_agent("vintage graphic tee under $30", {"items": []})

    assert session["error"] is None
    assert session["selected_item"] is item
    assert session["price_fairness"] == {"verdict": "fair price"}
    assert session["trend_context"]["confidence"] == "medium"
    assert session["outfit_suggestion"] == "Wear it with jeans."
    assert session["fit_card"] == "Fit card caption."
    assert session["final_response"] == "Found a tee and made a fit card."
    assert memory_actions == ["load", "update"]
    first_llm_call = fake_client.chat.completions.calls[0]
    assert first_llm_call["model"] == agent.LLM_MODEL
    assert first_llm_call["tools"] == agent.TOOL_DEFINITIONS


def test_run_agent_retry_recovery_continues_to_fit_card(monkeypatch):
    item, _ = install_common_tool_fakes(monkeypatch)
    fake_client = FakeGroqClient(
        [
            tool_message(
                "search_listings",
                {"description": "vintage graphic tee", "size": "XS", "max_price": 30},
            ),
            tool_message(
                "retry_search_with_fallback",
                {"description": "vintage graphic tee", "size": "XS", "max_price": 30},
            ),
            tool_messages(
                FakeToolCall("estimate_price_fairness"),
                FakeToolCall("get_live_trend_context"),
                FakeToolCall("suggest_outfit"),
                FakeToolCall("create_fit_card"),
            ),
            FakeMessage(content="Recovered after loosening size."),
        ]
    )

    monkeypatch.setattr(agent, "_get_groq_client", lambda: fake_client)
    monkeypatch.setattr(agent, "search_listings", lambda **kwargs: [])
    monkeypatch.setattr(
        agent,
        "retry_search_with_fallback",
        lambda **kwargs: {
            "results": [item],
            "adjustments": ["removed size filter"],
            "attempted_queries": [],
            "recovered": True,
            "message": "I removed the size filter and found options.",
        },
    )

    session = agent.run_agent("vintage graphic tee size XS under $30", {"items": []})

    assert session["error"] is None
    assert session["selected_item"] is item
    assert session["search_retry"]["recovered"] is True
    assert session["search_adjustments"] == ["removed size filter"]
    assert session["search_retry_message"] == "I removed the size filter and found options."
    assert session["outfit_suggestion"] == "Wear it with jeans."
    assert session["fit_card"] == "Fit card caption."


def test_run_agent_retry_failure_skips_downstream_tools(monkeypatch):
    calls = {"price": False, "trend": False, "outfit": False, "fit_card": False}

    def fake_style_profile_memory(user_id, action, profile_update=None):
        return default_profile(user_id)

    def fake_price(item):
        calls["price"] = True
        return {}

    def fake_trend(**kwargs):
        calls["trend"] = True
        return {}

    def fake_outfit(new_item, wardrobe, style_profile=None, trend_context=None):
        calls["outfit"] = True
        return "Should not run."

    def fake_card(outfit, new_item):
        calls["fit_card"] = True
        return "Should not run."

    fake_client = FakeGroqClient(
        [
            tool_message("search_listings", {"description": "designer ballgown"}),
            tool_message("retry_search_with_fallback", {"description": "designer ballgown"}),
            FakeMessage(content="No matches."),
        ]
    )

    monkeypatch.setattr(agent, "_get_groq_client", lambda: fake_client)
    monkeypatch.setattr(agent, "style_profile_memory", fake_style_profile_memory)
    monkeypatch.setattr(agent, "search_listings", lambda **kwargs: [])
    monkeypatch.setattr(
        agent,
        "retry_search_with_fallback",
        lambda **kwargs: {
            "results": [],
            "adjustments": [],
            "attempted_queries": [],
            "recovered": False,
            "message": "I tried loosening the search but still found no matches.",
        },
    )
    monkeypatch.setattr(agent, "_generate_no_results_message", lambda parsed: "Try a broader search.")
    monkeypatch.setattr(agent, "estimate_price_fairness", fake_price)
    monkeypatch.setattr(agent, "get_live_trend_context", fake_trend)
    monkeypatch.setattr(agent, "suggest_outfit", fake_outfit)
    monkeypatch.setattr(agent, "create_fit_card", fake_card)

    session = agent.run_agent("designer ballgown size XXS under $5", {"items": []})

    assert "still found no matches" in session["error"]
    assert session["selected_item"] is None
    assert session["price_fairness"] is None
    assert session["trend_context"] is None
    assert session["outfit_suggestion"] is None
    assert session["fit_card"] is None
    assert calls == {"price": False, "trend": False, "outfit": False, "fit_card": False}


def test_dispatch_tool_unknown_tool_returns_json_error():
    session = agent._new_session("vintage tee", {"items": []})

    result = json.loads(agent.dispatch_tool("unknown_tool", {}, session))

    assert result["error"] == "Unknown tool: unknown_tool"


def test_run_agent_malformed_tool_arguments_become_defaults(monkeypatch):
    item, _ = install_common_tool_fakes(monkeypatch)
    fake_client = FakeGroqClient(
        [
            tool_message("search_listings", raw_args="{bad json"),
            tool_messages(
                FakeToolCall("estimate_price_fairness"),
                FakeToolCall("get_live_trend_context"),
                FakeToolCall("suggest_outfit"),
                FakeToolCall("create_fit_card"),
            ),
            FakeMessage(content="Done."),
        ]
    )
    seen_kwargs = []

    def fake_search(**kwargs):
        seen_kwargs.append(kwargs)
        return [item]

    monkeypatch.setattr(agent, "_get_groq_client", lambda: fake_client)
    monkeypatch.setattr(agent, "search_listings", fake_search)

    session = agent.run_agent("vintage graphic tee under $30", {"items": []})

    assert session["error"] is None
    assert seen_kwargs[0]["description"] == "vintage graphic tee"
    assert seen_kwargs[0]["max_price"] == 30


def test_run_agent_max_tool_rounds_returns_controlled_error(monkeypatch):
    item, _ = install_common_tool_fakes(monkeypatch)
    fake_client = FakeGroqClient(
        [
            tool_message("search_listings", {"description": "vintage graphic tee"}),
            tool_message("search_listings", {"description": "vintage graphic tee"}),
        ]
    )

    monkeypatch.setattr(agent, "MAX_TOOL_ROUNDS", 2)
    monkeypatch.setattr(agent, "_get_groq_client", lambda: fake_client)
    monkeypatch.setattr(agent, "search_listings", lambda **kwargs: [item])

    session = agent.run_agent("vintage graphic tee", {"items": []})

    assert "maximum number of tool-calling steps" in session["error"]


def test_run_agent_llm_unavailable_returns_controlled_error(monkeypatch):
    monkeypatch.setattr(agent, "style_profile_memory", lambda user_id, action, profile_update=None: default_profile(user_id))
    monkeypatch.setattr(
        agent,
        "_get_groq_client",
        lambda: (_ for _ in ()).throw(ValueError("missing API key")),
    )

    session = agent.run_agent("vintage graphic tee under $30", {"items": []})

    assert "couldn't reach the FitFindr planning model" in session["error"]
    assert session["selected_item"] is None
