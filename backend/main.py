"""
EDI Healthcare Data Integration POC - FastAPI Backend
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from src.database import init_database, close_database

# Import API routes
from src.api import file_routes, chat_routes, mapping_routes

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle"""
    # Startup
    await init_database()
    yield
    # Shutdown
    await close_database()

app = FastAPI(
    title="EDI Healthcare Data Integration POC",
    description="POC for processing SmithRx claims with 3-panel UI and AI chat",
    version="0.1.0-poc",
    lifespan=lifespan
)

# CORS middleware for frontend communication
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # Next.js frontend
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    """Health check endpoint"""
    return {"message": "EDI Healthcare Data Integration POC Backend", "version": "0.1.0-poc"}

@app.get("/health")
async def health_check():
    """Detailed health check"""
    return {
        "status": "healthy",
        "service": "edi-backend-poc",
        "version": "0.1.0-poc"
    }

# API routes
app.include_router(file_routes.router, prefix="/api/v1")
app.include_router(chat_routes.router, prefix="/api/v1")  
app.include_router(mapping_routes.router, prefix="/api/v1")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)