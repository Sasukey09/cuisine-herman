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


import app.services.ai.assistant as ai_assistant


@pytest.fixture(autouse=True)
def _reset_runtime_caches():
    """The unsupported-knob caches are module-level; keep tests independent."""
    ai_assistant._UNSUPPORTED_THINKING.clear()
    ai_assistant._UNSUPPORTED_EFFORT.clear()
    yield
    ai_assistant._UNSUPPORTED_THINKING.clear()
    ai_assistant._UNSUPPORTED_EFFORT.clear()


# --------------------------------------------------------------------------- #
# Compatibility layer: only opted-in models receive the advanced knobs, and a
# model that rejects one (TypeError or provider 400) is never sent it again.
# --------------------------------------------------------------------------- #
def test_no_advanced_params_by_default():
    """The regression this fixes: with the default (empty) allowlists, NEITHER
    `thinking` NOR `output_config` is sent — so no model gets a parameter it
    rejects ("adaptive thinking is not supported on this model")."""
    client = FakeClient([resp([text_block("ok")], "end_turn")])
    assistant = AIAssistant(client=client, config=_cfg())
    out = assistant.chat(db="DB", tenant_id="t1", message="salut")
    assert out["reply"] == "ok"
    call = client.messages.calls[0]
    assert "thinking" not in call
    assert "output_config" not in call


def test_advanced_params_sent_only_when_model_opted_in():
    client = FakeClient([resp([text_block("ok")], "end_turn")])
    cfg = _cfg(
        thinking_models=frozenset({"claude-opus-4-8"}),
        effort_models=frozenset({"claude-opus-4-8"}),
    )
    assistant = AIAssistant(client=client, config=cfg)
    assistant.chat(db="DB", tenant_id="t1", message="salut")
    call = client.messages.calls[0]
    assert call["thinking"] == {"type": "adaptive"}
    assert call["output_config"] == {"effort": "medium"}


def test_retry_strips_params_on_provider_400():
    """A model opted-in but that the API rejects with the exact production error
    must self-heal: strip the knob, retry without it, and succeed."""

    class Picky(FakeMessages):
        def create(self, **kwargs):
            if "thinking" in kwargs:
                raise RuntimeError(
                    "Error code: 400 - {'type': 'error', 'error': {'type': "
                    "'invalid_request_error', 'message': 'adaptive thinking is "
                    "not supported on this model'}}"
                )
            return super().create(**kwargs)

    client = FakeClient([])
    client.messages = Picky([resp([text_block("ok")], "end_turn")])
    assistant = AIAssistant(client=client, config=_cfg(thinking_models=frozenset({"claude-opus-4-8"})))

    out = assistant.chat(db="DB", tenant_id="t1", message="salut")
    assert out["reply"] == "ok"
    # the retry that succeeded carried no advanced knob
    assert "thinking" not in client.messages.calls[-1]
    # and the model is now remembered as unsupported
    assert "claude-opus-4-8" in ai_assistant._UNSUPPORTED_THINKING


def test_advanced_kwargs_retry_on_typeerror():
    """Older SDKs reject thinking/output_config kwargs — the loop retries without them."""

    class PickyMessages(FakeMessages):
        def create(self, **kwargs):
            if "thinking" in kwargs or "output_config" in kwargs:
                raise TypeError("unexpected keyword argument 'thinking'")
            return super().create(**kwargs)

    client = FakeClient([])
    client.messages = PickyMessages([resp([text_block("ok")], "end_turn")])
    # opt the model in so the knobs are actually sent -> the retry path is exercised
    assistant = AIAssistant(client=client, config=_cfg(thinking_models=frozenset({"claude-opus-4-8"})))

    out = assistant.chat(db="DB", tenant_id="t1", message="salut")
    assert out["reply"] == "ok"
    assert "thinking" not in client.messages.calls[-1]


def test_genuine_provider_error_is_not_retried_and_wraps():
    """An auth/outage error (no incompatible-param hint) must surface as
    AIProviderError, not be retried as if it were a param problem."""
    from app.services.ai.errors import AIProviderError

    class Failing(FakeMessages):
        def create(self, **kwargs):
            self.calls.append(kwargs)
            raise RuntimeError("Error code: 401 - authentication_error: check your key")

    client = FakeClient([])
    client.messages = Failing([])
    # opt a knob in so `advanced` is non-empty: proves the retry is gated on the
    # error LOOKING like a param problem, not merely on having sent a knob.
    assistant = AIAssistant(client=client, config=_cfg(thinking_models=frozenset({"claude-opus-4-8"})))
    with pytest.raises(AIProviderError):
        assistant.chat(db="DB", tenant_id="t1", message="salut")
    # a genuine error is NOT retried -> exactly one call
    assert len(client.messages.calls) == 1


def test_multiple_models_work_without_incompatible_params(monkeypatch):
    """Routing between Haiku (simple) and Opus (complex) both succeed and neither
    sends an incompatible parameter under the default config."""
    monkeypatch.setattr(ai_tools, "execute_tool", lambda *a, **k: {"ok": True})
    for msg, expected_model in [
        ("Mon food cost moyen ?", "claude-haiku-4-5"),
        ("Analyse mes marges et compare mes fournisseurs", "claude-opus-4-8"),
    ]:
        client = FakeClient([resp([text_block("réponse")], "end_turn")])
        assistant = AIAssistant(client=client, config=_cfg(routing_enabled=True))
        out = assistant.chat(db="DB", tenant_id="t1", message=msg)
        assert out["reply"] == "réponse"
        call = client.messages.calls[0]
        assert call["model"] == expected_model
        assert "thinking" not in call and "output_config" not in call


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
