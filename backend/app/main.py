"""FastAPI application entry point."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select

from app.config import get_settings
from app.core.database import init_db, async_session_factory
from app.core.security import hash_password
from app.api.v1.router import router as api_router
from app.models.user import User

settings = get_settings()

logging.basicConfig(
    level=settings.log_level.upper(),
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown events."""
    logger.info("Starting Scoping Review AI System...")

    # Initialize database
    await init_db()
    logger.info("Database initialized with pgvector extension")

    # Create default admin user if not exists
    async with async_session_factory() as db:
        result = await db.execute(
            select(User).where(User.email == settings.default_admin_email)
        )
        admin = result.scalar_one_or_none()
        if not admin:
            admin = User(
                email=settings.default_admin_email,
                hashed_password=hash_password(settings.default_admin_password),
                full_name="Admin",
                is_admin=True,
            )
            db.add(admin)
            await db.commit()
            logger.info(f"Default admin created: {settings.default_admin_email}")

    yield

    logger.info("Shutting down Scoping Review AI System...")


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="Large Text AI Analysis for the Scoping Review Process",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://frontend:3000", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routes
app.include_router(api_router)


@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "version": settings.app_version,
        "environment": settings.environment,
    }
