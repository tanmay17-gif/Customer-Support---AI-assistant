"""
RAG Service — Multi-tenant ChromaDB + sentence-transformers over business policy documents.
Provides isolated collections per business_id.
"""
import asyncio
from pathlib import Path
from loguru import logger
from typing import Optional, Dict

from app.core.config import settings


class RAGService:
    """Multi-tenant RAG service with isolated business policy indexes."""

    _instance: Optional["RAGService"] = None

    def __init__(self):
        self._collections: Dict[str, any] = {}
        self._encoder = None
        self._client = None
        self._initialized_businesses = set()

    @classmethod
    def get_instance(cls) -> "RAGService":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    async def initialize_business(self, business_id: str, policy_doc_path: Optional[str] = None):
        """Indexes the policy doc for a specific business_id into its isolated collection."""
        if business_id in self._initialized_businesses:
            return

        if not policy_doc_path:
            if business_id == "biz_apparel":
                policy_doc_path = str(Path(settings.POLICY_DOC_PATH).parent / "stylehub_policy.txt")
            else:
                policy_doc_path = str(Path(settings.POLICY_DOC_PATH).parent / "techgadgets_policy.txt")

        path = Path(policy_doc_path).resolve()
        if not path.exists():
            path = Path(settings.POLICY_DOC_PATH).resolve()

        policy_text = path.read_text(encoding="utf-8") if path.exists() else ""

        try:
            await asyncio.to_thread(self._setup_chroma_business, business_id, policy_text)
            self._initialized_businesses.add(business_id)
            logger.info(f"RAG: Initialized business '{business_id}' collection")
        except Exception as e:
            logger.warning(f"RAG: Setup failed for business '{business_id}' ({e})")

    def _setup_chroma_business(self, business_id: str, policy_text: str):
        import chromadb
        from chromadb.utils.embedding_functions import DefaultEmbeddingFunction

        if self._client is None:
            persist_dir = str(Path(settings.CHROMA_PERSIST_DIR).resolve())
            self._client = chromadb.PersistentClient(path=persist_dir)

        if self._encoder is None:
            # Uses a local ONNX model bundled with chromadb — no internet needed
            self._encoder = DefaultEmbeddingFunction()

        collection_name = f"policy_{business_id}"
        collection = self._client.get_or_create_collection(
            collection_name,
            embedding_function=self._encoder,
            metadata={"hnsw:space": "cosine"},
        )

        if collection.count() == 0 and policy_text:
            chunks = self._split_policy(policy_text)
            if chunks:
                ids = [f"{business_id}-chunk-{i}" for i in range(len(chunks))]
                collection.add(documents=chunks, ids=ids)
                logger.info(f"RAG: Indexed {len(chunks)} chunks for '{business_id}'")

        self._collections[business_id] = collection

    def _split_policy(self, text: str) -> list[str]:
        chunks = []
        current = []
        for line in text.splitlines():
            if line.strip() and line[0].isdigit() and "." in line[:3]:
                if current:
                    chunks.append("\n".join(current).strip())
                current = [line]
            else:
                current.append(line)
        if current:
            chunks.append("\n".join(current).strip())
        return [c for c in chunks if len(c) > 20]

    async def query(self, query: str, business_id: str = "biz_tech", n_results: int = 2) -> str:
        """Query policy for a specific business account."""
        if business_id not in self._initialized_businesses:
            await self.initialize_business(business_id)

        collection = self._collections.get(business_id)
        if collection is None or self._encoder is None or collection.count() == 0:
            return "Standard policy applies. Verify refund eligibility and escalation criteria."

        try:
            return await asyncio.to_thread(self._query_sync_business, collection, query, n_results)
        except Exception as e:
            logger.warning(f"RAG query failed for '{business_id}' ({e})")
            return "Policy context unavailable."

    def _query_sync_business(self, collection, query: str, n_results: int) -> str:
        results = collection.query(
            query_texts=[query],
            n_results=min(n_results, collection.count()),
        )
        docs = results.get("documents", [[]])[0]
        return "\n\n---\n\n".join(docs)

    async def reindex_business_policy(self, business_id: str, updated_policy_text: str):
        """Re-indexes policy text after a human-approved policy amendment."""
        def _reindex():
            from chromadb.utils.embedding_functions import DefaultEmbeddingFunction
            collection_name = f"policy_{business_id}"
            if self._client and collection_name in [c.name for c in self._client.list_collections()]:
                self._client.delete_collection(collection_name)
            self._setup_chroma_business(business_id, updated_policy_text)

        await asyncio.to_thread(_reindex)
        logger.info(f"RAG: Successfully re-indexed policy for '{business_id}' following human approval")
