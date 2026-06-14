import tools
from tools import create_fit_card, search_listings, suggest_outfit
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
