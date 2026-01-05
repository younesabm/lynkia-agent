import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.whatsapp import router as whatsapp_router
from core.config import settings

# Configuration du logging
logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

logger = logging.getLogger(__name__)

# Création de l'application FastAPI
app = FastAPI(
    title="Agent Lynkia",
    description="Agent IA pour techniciens terrain via WhatsApp",
    version="1.0.0",
)

# Configuration CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Inclusion des routers
app.include_router(whatsapp_router)


@app.get("/")
async def root():
    """Endpoint racine."""
    return {
        "name": "Agent Lynkia",
        "version": "1.0.0",
        "status": "running",
    }


@app.get("/health")
async def health():
    """Endpoint de santé global."""
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
