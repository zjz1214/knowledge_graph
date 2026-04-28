import httpx
from app.config import get_settings

settings = get_settings()


class OllamaEmbedding:
    """Ollama embedding model wrapper"""

    def __init__(self, model: str = None):
        self.model = model or settings.ollama_embedding_model
        self.base_url = settings.ollama_base_url

    async def embed(self, text: str) -> list[float]:
        """Generate embedding for a single text"""
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(
                f"{self.base_url}/api/embed",
                json={"model": self.model, "input": text}
            )
            response.raise_for_status()
            data = response.json()
            return data["embeddings"][0]

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for multiple texts"""
        async with httpx.AsyncClient(timeout=120) as client:
            response = await client.post(
                f"{self.base_url}/api/embed",
                json={"model": self.model, "input": texts}
            )
            response.raise_for_status()
            data = response.json()
            return data["embeddings"]


# Global instance
embedding_model = OllamaEmbedding()


async def get_embedding(text: str) -> list[float]:
    """Quick helper for single embedding"""
    return await embedding_model.embed(text)
