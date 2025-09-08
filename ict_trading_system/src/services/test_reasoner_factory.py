# Test for ReasonerFactory and GeminiAdapter

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../..')))
from ict_trading_system.src.services.reasoner_factory import ReasonerFactory

def test_gemini_reasoner():
    reasoner = ReasonerFactory.create()
    response = reasoner.chat("Test Gemini reasoning.")
    print("Gemini Reasoner Response:", response.text)
    assert hasattr(response, 'text')

def test_openai_reasoner():
    import os
    os.environ['REASONER_PROVIDER'] = 'openai'
    reasoner = ReasonerFactory.create()
    response = reasoner.chat("Test OpenAI reasoning.")
    print("OpenAI Reasoner Response:", response.text)
    assert hasattr(response, 'text')

if __name__ == "__main__":
    test_gemini_reasoner()
    test_openai_reasoner()
