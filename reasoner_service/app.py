from fastapi import FastAPI
from .admin import router as admin_router, bind_orchestrator


def create_app(orchestrator=None):
    app = FastAPI(title="Reasoner Service Admin")
    app.include_router(admin_router, prefix="/admin")
    if orchestrator is not None:
        bind_orchestrator(orchestrator)
    return app


# convenience for running locally
if __name__ == '__main__':
    import uvicorn
    app = create_app()
    uvicorn.run(app, host='0.0.0.0', port=8001)
