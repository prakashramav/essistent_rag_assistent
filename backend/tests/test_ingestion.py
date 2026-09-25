import io
import uuid
import pytest
from httpx import AsyncClient

from app.services.chunking.recursive_chunker import RecursiveTokenChunker
from app.services.embeddings.gemini_adapter import GeminiEmbeddingAdapter
from app.services.parsers.base import ParsedContent
from app.services.parsers.txt_parser import TxtParser


def test_txt_parser():
    content = "# Introduction\nThis is paragraph one.\n\n# Details\nThis is paragraph two."
    parser = TxtParser()
    results = parser.parse(content.encode("utf-8"), filename="test.md")
    assert len(results) == 2
    assert results[0].section == "Introduction"
    assert "paragraph one" in results[0].text
    assert results[1].section == "Details"
    assert "paragraph two" in results[1].text


def test_recursive_chunker():
    chunker = RecursiveTokenChunker(chunk_size=100, chunk_overlap=20)
    long_text = "This is a sentence. " * 20
    parsed = [ParsedContent(text=long_text, page_number=1, section="Overview")]
    chunks = chunker.chunk_document(parsed)

    assert len(chunks) > 1
    assert chunks[0].chunk_index == 0
    assert chunks[1].chunk_index == 1
    assert chunks[0].page_number == 1
    assert chunks[0].section == "Overview"
    assert chunks[0].token_count > 0


@pytest.mark.asyncio
async def test_gemini_embedding_adapter():
    adapter = GeminiEmbeddingAdapter()
    assert adapter.dimension == 768

    texts = ["Hello world", "Enterprise RAG assistant"]
    embeddings = await adapter.embed_texts(texts)
    assert len(embeddings) == 2
    assert len(embeddings[0]) == 768
    assert len(embeddings[1]) == 768


@pytest.mark.asyncio
async def test_document_upload_and_ingestion_lifecycle(client: AsyncClient):
    # 1. Signup user and get token
    random_str = str(uuid.uuid4())[:8]
    signup_res = await client.post(
        "/api/v1/auth/signup",
        json={
            "email": f"ingest_{random_str}@example.com",
            "password": "Password123!",
            "full_name": "Ingest Tester",
            "organization_name": "Ingest Corp",
        },
    )
    assert signup_res.status_code == 201
    token = signup_res.json()["access_token"]
    org_id = signup_res.json()["organization"]["id"]

    # 2. Upload a text document via multipart/form-data
    doc_content = (
        "# System Architecture\n"
        "The system consists of FastAPI backend and Next.js frontend.\n\n"
        "# Data Layer\n"
        "PostgreSQL with pgvector provides dense cosine vector retrieval."
    )
    files = {
        "file": ("architecture.md", io.BytesIO(doc_content.encode("utf-8")), "text/markdown"),
    }
    data = {"tags": "architecture, rag, database"}

    upload_res = await client.post(
        "/api/v1/documents/upload",
        files=files,
        data=data,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert upload_res.status_code == 201
    doc_data = upload_res.json()
    assert doc_data["title"] == "architecture.md"
    assert doc_data["file_type"] == "md"
    doc_id = doc_data["id"]

    # 3. List documents for organization
    list_res = await client.get(
        "/api/v1/documents",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert list_res.status_code == 200
    docs = list_res.json()
    assert len(docs) >= 1
    assert any(d["id"] == doc_id for d in docs)

    # 4. Process document pipeline synchronously for test assertion
    from app.services.ingestion.pipeline import IngestionPipeline
    await IngestionPipeline.process_document_task(
        uuid.UUID(doc_id),
        uuid.UUID(org_id),
        doc_content.encode("utf-8"),
    )

    # 5. Verify status is COMPLETED
    status_res = await client.get(
        f"/api/v1/documents/{doc_id}/status",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert status_res.status_code == 200
    status_data = status_res.json()
    assert status_data["status"] == "completed"
    assert status_data["total_chunks"] > 0

    # 6. Verify chunk inspection
    chunks_res = await client.get(
        f"/api/v1/documents/{doc_id}/chunks",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert chunks_res.status_code == 200
    chunks = chunks_res.json()
    assert len(chunks) > 0
    assert chunks[0]["document_id"] == doc_id
    assert chunks[0]["page_number"] is not None


@pytest.mark.asyncio
async def test_tenant_isolation_on_documents(client: AsyncClient):
    """Assert that User B from Org B cannot view or delete documents from Org A."""
    # Org A
    rand_a = str(uuid.uuid4())[:8]
    res_a = await client.post(
        "/api/v1/auth/signup",
        json={"email": f"a_{rand_a}@example.com", "password": "Password123!", "organization_name": "Org A"},
    )
    token_a = res_a.json()["access_token"]
    org_a_id = res_a.json()["organization"]["id"]

    # Org B
    rand_b = str(uuid.uuid4())[:8]
    res_b = await client.post(
        "/api/v1/auth/signup",
        json={"email": f"b_{rand_b}@example.com", "password": "Password123!", "organization_name": "Org B"},
    )
    token_b = res_b.json()["access_token"]

    # Upload doc to Org A
    files = {"file": ("secret_a.txt", io.BytesIO(b"Confidential Org A content"), "text/plain")}
    upload_res = await client.post(
        "/api/v1/documents/upload",
        files=files,
        headers={"Authorization": f"Bearer {token_a}"},
    )
    doc_a_id = upload_res.json()["id"]

    # User B attempts to access Org A's document
    unauthorized_get = await client.get(
        f"/api/v1/documents/{doc_a_id}",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert unauthorized_get.status_code == 404

    # User B attempts to delete Org A's document
    unauthorized_delete = await client.delete(
        f"/api/v1/documents/{doc_a_id}",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert unauthorized_delete.status_code == 404
