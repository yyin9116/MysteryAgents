"""
Main FastAPI application entry point.

Undercover AI Sandbox - 《谁是卧底》多智能体沙盒系统
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api import personality
from config import settings
from database import init_db

logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    logger.info('Starting Undercover AI Sandbox backend...')
    logger.info('Debug mode: %s', settings.DEBUG)
    logger.info('CORS origins: %s', settings.cors_origins_list)
    init_db()
    yield
    logger.info('Shutting down Undercover AI Sandbox backend...')


app = FastAPI(
    title='Undercover AI Sandbox API',
    description='Backend API for 《谁是卧底》多智能体沙盒系统',
    version='1.0.0',
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)

app.include_router(personality.router)

from api import (  # noqa: E402
    characters,
    config,
    discussion,
    game,
    game_stream,
    model_configs,
    models,
    replay,
    usage,
    user,
    werewolf,
    werewolf_stream,
)

app.include_router(game.router)
app.include_router(user.router)
app.include_router(config.router)
app.include_router(replay.router)
app.include_router(models.router)
app.include_router(game_stream.router)
app.include_router(discussion.router)
app.include_router(characters.router)
app.include_router(werewolf.router)
app.include_router(werewolf_stream.router)
app.include_router(model_configs.router)
app.include_router(usage.router)


@app.get('/')
async def root():
    """Root endpoint."""
    return {
        'name': 'Undercover AI Sandbox API',
        'version': '1.0.0',
        'status': 'running',
        'mode': 'local-demo',
        'docs': '/docs'
    }


@app.get('/health')
async def health_check():
    """Health check endpoint."""
    return {
        'status': 'healthy',
        'mode': 'local-demo'
    }


if __name__ == '__main__':
    import uvicorn

    uvicorn.run(
        'main:app',
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        log_level=settings.LOG_LEVEL.lower()
    )
