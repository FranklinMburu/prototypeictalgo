# ...existing code from reasoner_service/reasoner_service/fallback.py...

def build_fallback(snapshot):
    class Fallback:
        recommendation = "do_nothing"
        confidence = 0.0
        summary = "fallback"
        def model_dump(self):
            return {"recommendation": self.recommendation, "confidence": self.confidence, "summary": self.summary}
    return Fallback()
