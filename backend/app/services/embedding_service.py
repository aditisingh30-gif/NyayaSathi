from typing import List, Optional
import time
from app.config import settings
from app.core.logging_config import logger


class EmbeddingServiceError(Exception):
    """Custom exception raised during embedding generation or model loading."""
    pass


class EmbeddingService:
    """
    Reusable, high-performance embedding service.
    Supports Sentence Transformers and ChromaDB's ONNX-accelerated MiniLM embedder.
    """

    _instance: Optional["EmbeddingService"] = None

    def __init__(self, model_name: Optional[str] = None):
        self.model_name = model_name or settings.EMBEDDING_MODEL_NAME
        self._embedder = None
        self._embedding_dim: Optional[int] = None
        self._backend = "onnx"  # 'sentence-transformers' or 'onnx'
        self._initialize_embedder()

    def _initialize_embedder(self):
        """Initialize the embedding model with graceful fallback."""
        start_time = time.time()
        logger.info(f"Initializing embedding model '{self.model_name}'...")

        # Option A: Try sentence_transformers if available
        try:
            from sentence_transformers import SentenceTransformer
            self._embedder = SentenceTransformer(self.model_name)
            self._backend = "sentence-transformers"
            sample = self._embedder.encode(["Indian Law"]).tolist()[0]
            self._embedding_dim = len(sample)
            logger.info(
                f"SentenceTransformer loaded '{self.model_name}' ({self._embedding_dim} dims) "
                f"in {time.time() - start_time:.2f}s"
            )
            return
        except (ImportError, Exception) as e:
            logger.debug(f"SentenceTransformer not available or failed to load ({e}). Using ONNX MiniLM runtime.")

        # Option B: ONNX-accelerated DefaultEmbeddingFunction (all-MiniLM-L6-v2)
        try:
            from chromadb.utils import embedding_functions
            self._embedder = embedding_functions.DefaultEmbeddingFunction()
            self._backend = "onnx"
            sample = self._embedder(["Indian Law"])[0]
            self._embedding_dim = len(sample)
            logger.info(
                f"Chroma ONNX embedder initialized with '{self.model_name}' ({self._embedding_dim} dims) "
                f"in {time.time() - start_time:.2f}s"
            )
            return
        except Exception as e:
            logger.error(f"Failed to initialize embedding runtime: {e}")
            raise EmbeddingServiceError(f"Could not load any embedding runtime: {e}")

    @classmethod
    def get_instance(cls, model_name: Optional[str] = None) -> "EmbeddingService":
        """Singleton accessor for the embedding service."""
        if cls._instance is None:
            cls._instance = cls(model_name)
        elif model_name and cls._instance.model_name != model_name:
            # Reinitialize if a different model is explicitly requested
            cls._instance = cls(model_name)
        return cls._instance

    @property
    def embedding_dimension(self) -> int:
        """Dynamically return the vector dimension of the active model."""
        if self._embedding_dim is None:
            sample = self.embed_texts(["sample text"])[0]
            self._embedding_dim = len(sample)
        return self._embedding_dim

    def embed_texts(self, texts: List[str], batch_size: int = 32) -> List[List[float]]:
        """
        Generate dense vector embeddings for a list of texts in batches.
        """
        if not texts:
            return []

        embeddings: List[List[float]] = []

        try:
            for i in range(0, len(texts), batch_size):
                batch = texts[i:i + batch_size]

                if self._backend == "sentence-transformers":
                    batch_embeds = self._embedder.encode(
                        batch,
                        batch_size=len(batch),
                        show_progress_bar=False,
                        convert_to_numpy=True
                    ).tolist()
                else:
                    # ONNX / ChromaDB embedding function
                    batch_embeds = self._embedder(batch)
                    if hasattr(batch_embeds, "tolist"):
                        batch_embeds = batch_embeds.tolist()

                embeddings.extend(batch_embeds)

            return embeddings

        except Exception as e:
            logger.error(f"Error generating embeddings for batch of {len(texts)} texts: {e}")
            raise EmbeddingServiceError(f"Embedding generation failed: {str(e)}")

    def embed_query(self, query: str) -> List[float]:
        """Generate embedding vector for a single query text."""
        embeds = self.embed_texts([query])
        if not embeds:
            raise EmbeddingServiceError("Empty embedding returned for query.")
        return embeds[0]
