from ai.gemini import call_gemini
from ai.claude import call_claude
from ai.openai_client import call_openai

def call_ai(provider, prompt, api_key, model):
    """
    Route AI queries to the appropriate provider.
    
    Args:
        provider: "gemini", "claude", or "openai"
        prompt: The user's query/prompt
        api_key: API key for claude/openai (None for gemini)
        model: Model name to use
    """
    if provider == "gemini":
        return call_gemini(prompt, model)
    elif provider == "claude":
        return call_claude(prompt, api_key, model)
    elif provider == "openai":
        return call_openai(prompt, api_key, model)
    else:
        return "Unknown provider"
