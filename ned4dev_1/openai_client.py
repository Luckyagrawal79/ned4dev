from openai import OpenAI


def call_openai(prompt: str, api_key: str | None, model: str) -> str:
    """
    Simple wrapper around the OpenAI Chat Completions API.

    - If api_key is provided, it is used directly.
    - Otherwise, the SDK will fall back to the OPENAI_API_KEY env var.
    """
    # Only pass api_key if it's provided, otherwise let OpenAI check env var
    if api_key:
        client = OpenAI(api_key=api_key)
    else:
        client = OpenAI()  # Will use OPENAI_API_KEY env var if set

    resp = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=800,
    )

    # New-style OpenAI client returns choices[0].message.content
    return resp.choices[0].message.content


