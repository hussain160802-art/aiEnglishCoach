from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routes import learning_path_routes, daily_plan_routes, exercise_routes
from app.database import engine, Base

# Create all database tables
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="English Coach API",
    description="Autonomous English learning coach that generates personalized learning paths, daily plans, and exercises.",
    version="1.0.0",
)

# CORS middleware configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(
    learning_path_routes.router,
    prefix="/api/learning-path",
    tags=["Learning Path"],
)
app.include_router(
    daily_plan_routes.router,
    prefix="/api/daily-plan",
    tags=["Daily Plan"],
)
app.include_router(
    exercise_routes.router,
    prefix="/api/exercises",
    tags=["Exercises"],
)


@app.get("/", tags=["Health"])
def root():
    """Health check endpoint."""
    return {"status": "ok", "message": "English Coach API is running."}


@app.get("/health", tags=["Health"])
def health_check():
    """Detailed health check."""
    return {"status": "healthy", "version": "1.0.0"}
