from types import SimpleNamespace

import pytest

from app.services.ai.assistant import AIAssistant
from app.services.ai.config import AIConfig
from app.services.ai.errors import AINotConfiguredError
from app.services.ai import tools as ai_tools


def _cfg(**over):
    base = dict(
        api_key="test-key",
        model="claude-opus-4-8",
        simple_model="claude-haiku-4-5",
        routing_enabled=False,   # existing tests assert Opus; enable per-test
        max_tokens=1024,
        effort="medium",
        max_tool_iterations=8,
    )
    base.update(over)
    return AIConfig(**base)


def text_block(t):
    return SimpleNamespace(type="text", text=t)


def tool_block(name, inp, id="toolu_1"):
    return SimpleNamespace(type="tool_use", name=name, input=inp, id=id)


class FakeMessages:
    def __init__(self, scripted):
        self._scripted = list(scripted)
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return self._scripted.pop(0)


class FakeClient:
    def __init__(self, scripted):
        self.messages = FakeMessages(scripted)


def resp(content, stop_reason, input_tokens=10, output_tokens=5):
    return SimpleNamespace(
        content=content,
        stop_reason=stop_reason,
        usage=SimpleNamespace(input_tokens=input_tokens, output_tokens=output_tokens),
    )


def test_chat_runs_tool_then_returns_final_reply(monkeypatch):
    executed = []

    def fake_execute(db, tenant_id, name, tool_input):
        executed.append((tenant_id, name, tool_input))
        return {"recipes": [], "count": 0}

    monkeypatch.setattr(ai_tools, "execute_tool", fake_execute)

    client = FakeClient([
        resp([text_block("Je regarde."), tool_block("list_recipes", {})], "tool_use"),
        resp([text_block("Tu as 0 recette.")], "end_turn"),
    ])
    assistant = AIAssistant(client=client, config=_cfg())

    out = assistant.chat(db="DB", tenant_id="tenant-A", message="Combien de recettes ?")

    assert out["reply"] == "Tu as 0 recette."
    assert out["tool_calls"] == [{"name": "list_recipes", "input": {}}]
    # tool executed strictly within the caller's tenant scope
    assert executed == [("tenant-A", "list_recipes", {})]
    # usage summed across both model calls
    assert out["usage"] == {"input_tokens": 20, "output_tokens": 10}


def test_chat_builds_messages_with_history_and_new_turn():
    client = FakeClient([resp([text_block("ok")], "end_turn")])
    assistant = AIAssistant(client=client, config=_cfg())

    assistant.chat(
        db="DB",
        tenant_id="t1",
        message="dernière question",
        history=[
            {"role": "user", "content": "bonjour"},
            {"role": "assistant", "content": "salut"},
            {"role": "system", "content": "ignored"},  # dropped — only user/assistant kept
        ],
    )

    sent = client.messages.calls[0]["messages"]
    assert [m["role"] for m in sent] == ["user", "assistant", "user"]
    assert sent[-1] == {"role": "user", "content": "dernière question"}
    # system prompt + tools are always provided
    assert client.messages.calls[0]["system"]
    assert client.messages.calls[0]["tools"]


def test_chat_stops_at_max_iterations(monkeypatch):
    monkeypatch.setattr(ai_tools, "execute_tool", lambda *a, **k: {"ok": True})
    # always asks for a tool -> loop must stop at max_tool_iterations
    client = FakeClient([
        resp([tool_block("list_recipes", {})], "tool_use") for _ in range(3)
    ])
    assistant = AIAssistant(client=client, config=_cfg(max_tool_iterations=3))

    out = assistant.chat(db="DB", tenant_id="t1", message="boucle")
    assert len(client.messages.calls) == 3
    assert len(out["tool_calls"]) == 3


def test_not_configured_raises():
    assistant = AIAssistant(client=None, config=_cfg(api_key=None))
    with pytest.raises(AINotConfiguredError):
        assistant.chat(db="DB", tenant_id="t1", message="salut")


def test_advanced_kwargs_retry_on_typeerror():
    """Older SDKs reject thinking/output_config kwargs — the loop retries without them."""

    class PickyMessages(FakeMessages):
        def create(self, **kwargs):
            if "thinking" in kwargs or "output_config" in kwargs:
                raise TypeError("unexpected keyword argument")
            return super().create(**kwargs)

    client = FakeClient([resp([text_block("ok")], "end_turn")])
    client.messages = PickyMessages([resp([text_block("ok")], "end_turn")])
    assistant = AIAssistant(client=client, config=_cfg())

    out = assistant.chat(db="DB", tenant_id="t1", message="salut")
    assert out["reply"] == "ok"
    assert "thinking" not in client.messages.calls[0]


# --- I6: cost optimisation (prompt cache + model routing) ------------------ #
from app.services.ai.config import select_model, is_simple_message


def test_is_simple_message_heuristic():
    assert is_simple_message("Quel est mon food cost moyen ?") is True
    assert is_simple_message("Combien de recettes ai-je ?") is True
    # analytical -> not simple
    assert is_simple_message("Analyse mes marges et recommande des changements") is False
    # too long -> not simple
    assert is_simple_message("x " * 120) is False
    # multi-sentence -> not simple
    assert is_simple_message("Bonjour. Peux-tu m'aider ?") is False
    assert is_simple_message("") is False


def test_select_model_routes_simple_to_haiku_complex_to_opus():
    cfg = _cfg(routing_enabled=True)
    assert select_model("Mon food cost moyen ?", cfg) == "claude-haiku-4-5"
    assert select_model("Analyse la rentabilité de mes plats", cfg) == "claude-opus-4-8"


def test_routing_disabled_always_uses_default_model():
    cfg = _cfg(routing_enabled=False)
    assert select_model("Mon food cost moyen ?", cfg) == "claude-opus-4-8"


def test_chat_caches_system_prompt_and_routes_model():
    client = FakeClient([resp([text_block("ok")], "end_turn")])
    a = AIAssistant(client=client, config=_cfg(routing_enabled=True))
    a.chat(db=None, tenant_id="t1", message="Mon food cost moyen ?")

    call = client.messages.calls[0]
    # system is a list of blocks; the first (stable SYSTEM_PROMPT) is cached
    assert isinstance(call["system"], list)
    assert call["system"][0]["cache_control"] == {"type": "ephemeral"}
    # a simple question routed to the cheaper model
    assert call["model"] == "claude-haiku-4-5"


def test_chat_complex_message_stays_on_opus():
    client = FakeClient([resp([text_block("ok")], "end_turn")])
    a = AIAssistant(client=client, config=_cfg(routing_enabled=True))
    a.chat(db=None, tenant_id="t1", message="Analyse mes marges et compare mes fournisseurs")
    assert client.messages.calls[0]["model"] == "claude-opus-4-8"
