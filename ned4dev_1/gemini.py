from vertexai.preview.generative_models import GenerativeModel

def call_gemini(prompt, model_name):
    model = GenerativeModel(model_name)
    return model.generate_content(prompt).text
