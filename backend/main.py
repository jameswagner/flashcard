from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .routers import flashcard_sets

app = FastAPI()

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # Frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(flashcard_sets.router, prefix="/api/flashcard-sets", tags=["flashcard-sets"])

@app.get("/")
async def root():
    return {"message": "Flashcards API is running"} 