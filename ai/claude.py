import anthropic

def call_claude(prompt, api_key, model):
    client = anthropic.Anthropic(api_key=api_key)
    msg = client.messages.create(model=model,max_tokens=800,messages=[{"role":"user","content":prompt}])
    return msg.content[0].text
