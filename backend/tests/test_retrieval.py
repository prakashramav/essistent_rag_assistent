import io
import uuid
import pytest
from httpx import AsyncClient
from app.services.ingestion.pipeline import IngestionPipeline


@pytest.mark.asyncio
async def test_hybrid_search_and_metadata_filtering(client: AsyncClient):
    # 1. Register User A in Org A
    rand_a = str(uuid.uuid4())[:8]
    signup_res = await client.post(
        "/api/v1/auth/signup",
        json={
            "email": f"retrieval_a_{rand_a}@example.com",
            "password": "Password123!",
            "full_name": "Retrieval Admin",
            "organization_name": "Retrieval Corp",
        },
    )
    assert signup_res.status_code == 201
    token_a = signup_res.json()["access_token"]
    org_a_id = uuid.UUID(signup_res.json()["organization"]["id"])

    # 2. Upload Document 1: AI & Engineering (tag: ai)
    doc1_content = (
        "# Artificial Intelligence Systems\n"
        "Machine learning models, neural networks, and automated transformers "
        "streamline enterprise data extraction and classification."
    )
    doc1_res = await client.post(
        "/api/v1/documents/upload",
        files={"file": ("ai_systems.md", io.BytesIO(doc1_content.encode("utf-8")), "text/markdown")},
        data={"tags": "ai, engineering"},
        headers={"Authorization": f"Bearer {token_a}"},
    )
    doc1_id = uuid.UUID(doc1_res.json()["id"])
    await IngestionPipeline.process_document_task(doc1_id, org_a_id, doc1_content.encode("utf-8"))

    # 3. Upload Document 2: Financial Regulations (tag: finance)
    doc2_content = (
        "# Accounting Guidelines\n"
        "Revenue recognition standards and financial compliance regulations "
        "dictate corporate fiscal reporting."
    )
    doc2_res = await client.post(
        "/api/v1/documents/upload",
        files={"file": ("accounting.md", io.BytesIO(doc2_content.encode("utf-8")), "text/markdown")},
        data={"tags": "finance, compliance"},
        headers={"Authorization": f"Bearer {token_a}"},
    )
    doc2_id = uuid.UUID(doc2_res.json()["id"])
    await IngestionPipeline.process_document_task(doc2_id, org_a_id, doc2_content.encode("utf-8"))

    # 4. Test Hybrid Search for AI Query
    search_payload = {
        "query": "neural networks and machine learning models",
        "hybrid": True,
        "rerank": True,
        "limit": 5,
    }
    search_res = await client.post(
        "/api/v1/retrieval/search",
        json=search_payload,
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert search_res.status_code == 200
    search_data = search_res.json()
    assert search_data["total_candidates"] >= 1
    assert len(search_data["results"]) >= 1
    top_result = search_data["results"][0]
    assert top_result["document_id"] == str(doc1_id)
    assert top_result["combined_score"] > 0
    assert top_result["rerank_score"] is not None

    # 5. Test Metadata Filtering by Tag (tag="finance")
    filtered_payload = {
        "query": "neural networks and enterprise systems",
        "tags": ["finance"],
        "hybrid": True,
        "limit": 5,
    }
    filtered_res = await client.post(
        "/api/v1/retrieval/search",
        json=filtered_payload,
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert filtered_res.status_code == 200
    filtered_data = filtered_res.json()
    # Should only match Document 2 (since Document 1 is filtered out by tag)
    for r in filtered_data["results"]:
        assert r["document_id"] == str(doc2_id)

    # 6. Test Metadata Filtering by Document ID
    doc_filter_payload = {
        "query": "standards and regulations",
        "document_ids": [str(doc1_id)],
        "limit": 5,
    }
    doc_filter_res = await client.post(
        "/api/v1/retrieval/search",
        json=doc_filter_payload,
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert doc_filter_res.status_code == 200
    doc_filter_data = doc_filter_res.json()
    for r in doc_filter_data["results"]:
        assert r["document_id"] == str(doc1_id)


@pytest.mark.asyncio
async def test_tenant_isolation_on_retrieval(client: AsyncClient):
    """
    CRITICAL SECURITY TEST:
    Assert that a search executed by a user from Organization B
    NEVER returns document chunks belonging to Organization A.
    """
    # 1. Create Org A with confidential document
    rand_a = str(uuid.uuid4())[:8]
    res_a = await client.post(
        "/api/v1/auth/signup",
        json={"email": f"isolated_a_{rand_a}@example.com", "password": "Password123!", "organization_name": "Org Secret A"},
    )
    token_a = res_a.json()["access_token"]
    org_a_id = uuid.UUID(res_a.json()["organization"]["id"])

    secret_content = "SuperConfidentialToken12345: The crown jewel algorithm parameters."
    upload_res = await client.post(
        "/api/v1/documents/upload",
        files={"file": ("secret.txt", io.BytesIO(secret_content.encode("utf-8")), "text/plain")},
        headers={"Authorization": f"Bearer {token_a}"},
    )
    doc_a_id = uuid.UUID(upload_res.json()["id"])
    await IngestionPipeline.process_document_task(doc_a_id, org_a_id, secret_content.encode("utf-8"))

    # 2. Create Org B
    rand_b = str(uuid.uuid4())[:8]
    res_b = await client.post(
        "/api/v1/auth/signup",
        json={"email": f"isolated_b_{rand_b}@example.com", "password": "Password123!", "organization_name": "Org B"},
    )
    token_b = res_b.json()["access_token"]

    # 3. User B queries for the exact secret keyword
    leak_search_res = await client.post(
        "/api/v1/retrieval/search",
        json={"query": "SuperConfidentialToken12345 crown jewel algorithm", "limit": 10},
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert leak_search_res.status_code == 200
    leak_data = leak_search_res.json()

    # User B MUST receive 0 results from Org A
    assert len(leak_data["results"]) == 0
    assert leak_data["total_candidates"] == 0
