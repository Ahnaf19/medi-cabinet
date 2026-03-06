# LLM Integration Layer

Provider-agnostic LLM integration using a factory pattern with registry.

## Architecture

```
llm/
  base.py          # Abstract BaseLLMProvider, LLMMessage, LLMResponse, ToolCall
  factory.py       # LLMProviderFactory — register/create/from_config
  parser.py        # LLMParser — Tier 2 NLU fallback using tool calling
  tools.py         # Tool schemas for structured extraction
  providers/
    groq.py        # Groq (primary, fully implemented via httpx)
    openai.py      # OpenAI (placeholder)
    anthropic.py   # Anthropic (placeholder)
```

## Key Concepts

**Multi-Tier NLU**:
1. **Tier 1** — Regex parsers (free, instant, deterministic)
2. **Tier 2** — LLM fallback via `LLMParser` (only when regex returns `unknown`)

**Factory Pattern**: Providers self-register on import. Create a provider from config:
```python
provider = LLMProviderFactory.from_config(settings)  # Returns None if disabled
```

**Tool Calling**: The LLM extracts structured data via tool schemas defined in `tools.py`, avoiding free-form JSON parsing.

**No SDK Dependencies**: All providers use raw `httpx` for HTTP calls, keeping the dependency footprint small.

## Adding a New Provider

1. Create `providers/my_provider.py`
2. Subclass `BaseLLMProvider`, implement `complete()` and `complete_with_vision()`
3. Auto-register: `LLMProviderFactory.register("my_provider", MyProvider)`
4. Import in `providers/__init__.py`

## Configuration

Set in `.env`:
```
LLM_PROVIDER=groq          # or "openai", "anthropic", leave empty to disable
LLM_API_KEY=your-key
LLM_MODEL=llama-3.3-70b-versatile
LLM_TEMPERATURE=0.0
```
