from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import random

app = FastAPI()

@app.post("/v1/chat/completions")
async def chat_completions(request: Request):
    body = await request.json()
    # Simulate a realistic response
    choices = [
        {
            "index": 0,
            "message": {
                "role": "assistant",
                "content": "This is a mock response from your local OpenAI server."
            },
            "finish_reason": "stop"
        }
    ]
    usage = {
        "prompt_tokens": random.randint(10, 50),
        "completion_tokens": random.randint(10, 50),
        "total_tokens": random.randint(20, 100)
    }
    return JSONResponse({
        "id": "chatcmpl-mock123",
        "object": "chat.completion",
        "created": 1234567890,
        "model": body.get("model", "gpt-4o-mini"),
        "choices": choices,
        "usage": usage
    })

@app.get("/")
def root():
    return {"message": "OpenAI Mock Server is running."}
