from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.core.logging_config import logger
from app.api.routes import router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup actions
    logger.info(f"{settings.APP_NAME} starting up in {settings.APP_ENV} mode...")
    logger.info(f"Data directories initialized at: {settings.DATA_DIR}")
    yield
    # Shutdown actions
    logger.info(f"{settings.APP_NAME} shutting down...")


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.APP_NAME,
        version="1.0.0",
        description="AI-Based Legal & Policy Information Assistant for India (RAG-Powered)",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    # CORS configuration
    logger.info(f"Configuring CORS with origins: {settings.CORS_ORIGINS}")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register API Routes
    app.include_router(router)

    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host=settings.HOST, port=settings.PORT, reload=settings.DEBUG)
