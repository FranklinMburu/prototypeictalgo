import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from ict_trading_system.src.services.reasoner_factory import ReasonerFactory


def test_gemini_reasoner():
    reasoner = ReasonerFactory.create()
    response = reasoner.chat("Test Gemini reasoning.")
    # GeminiAdapter returns a dict, OpenAIAdapter returns ReasonerResponse
    if isinstance(response, dict):
        # Normalize to ReasonerResponse-like for test
        text = response.get("choices", [{}])[0].get("message", {}).get("content", "")
    else:
        text = getattr(response, "text", None)
    print("Gemini Reasoner Response:", text)
    assert text is not None and isinstance(text, str)


def test_openai_reasoner():
    import os
    os.environ['REASONER_PROVIDER'] = 'openai'
    reasoner = ReasonerFactory.create()
    response = reasoner.chat("Test OpenAI reasoning.")
    if isinstance(response, dict):
        text = response.get("choices", [{}])[0].get("message", {}).get("content", "")
    else:
        text = getattr(response, "text", None)
    print("OpenAI Reasoner Response:", text)
    assert text is not None and isinstance(text, str)

if __name__ == "__main__":
    test_gemini_reasoner()
    test_openai_reasoner()
