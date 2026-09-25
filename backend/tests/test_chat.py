import io
import json
import uuid
import pytest
from httpx import AsyncClient
from app.services.ingestion.pipeline import IngestionPipeline


@pytest.mark.asyncio
async def test_conversation_crud_and_tenant_isolation(client: AsyncClient):
    # 1. Register User A in Org A
    rand_a = str(uuid.uuid4())[:8]
    signup_a = await client.post(
        "/api/v1/auth/signup",
        json={
            "email": f"chat_user_a_{rand_a}@example.com",
            "password": "Password123!",
            "full_name": "Chat User A",
            "organization_name": "Chat Org A",
        },
    )
    assert signup_a.status_code == 201
    token_a = signup_a.json()["access_token"]

    # 2. Register User B in Org B
    rand_b = str(uuid.uuid4())[:8]
    signup_b = await client.post(
        "/api/v1/auth/signup",
        json={
            "email": f"chat_user_b_{rand_b}@example.com",
            "password": "Password123!",
            "full_name": "Chat User B",
            "organization_name": "Chat Org B",
        },
    )
    assert signup_b.status_code == 201
    token_b = signup_b.json()["access_token"]

    # 3. User A creates a conversation
    create_res = await client.post(
        "/api/v1/chat/conversations",
        json={"title": "Q3 Financial Analysis"},
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert create_res.status_code == 201
    conv_data = create_res.json()
    conv_id = conv_data["id"]
    assert conv_data["title"] == "Q3 Financial Analysis"

    # 4. User A lists conversations
    list_res = await client.get(
        "/api/v1/chat/conversations",
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert list_res.status_code == 200
    list_data = list_res.json()
    assert list_data["total"] >= 1
    assert any(c["id"] == conv_id for c in list_data["items"])

    # 5. User B tries to view User A's conversation -> Expect 404 (Tenant Isolation)
    cross_get = await client.get(
        f"/api/v1/chat/conversations/{conv_id}",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert cross_get.status_code == 404

    # 6. User B tries to delete User A's conversation -> Expect 404 (Tenant Isolation)
    cross_del = await client.delete(
        f"/api/v1/chat/conversations/{conv_id}",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert cross_del.status_code == 404

    # 7. User A updates title
    update_res = await client.patch(
        f"/api/v1/chat/conversations/{conv_id}",
        json={"title": "Updated Financial Analysis"},
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert update_res.status_code == 200
    assert update_res.json()["title"] == "Updated Financial Analysis"

    # 8. User A deletes conversation
    del_res = await client.delete(
        f"/api/v1/chat/conversations/{conv_id}",
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert del_res.status_code == 200


@pytest.mark.asyncio
async def test_rag_generation_with_citations_and_memory(client: AsyncClient):
    # 1. Setup Org and ingest document
    rand = str(uuid.uuid4())[:8]
    signup = await client.post(
        "/api/v1/auth/signup",
        json={
            "email": f"rag_user_{rand}@example.com",
            "password": "Password123!",
            "full_name": "RAG User",
            "organization_name": "RAG Enterprises",
        },
    )
    token = signup.json()["access_token"]
    org_id = uuid.UUID(signup.json()["organization"]["id"])

    # Ingest document
    doc_text = (
        "# Enterprise Cloud Infrastructure\n"
        "Apex Systems provides enterprise multi-cloud container orchestration "
        "with 99.999% uptime SLAs and end-to-end zero-trust network encryption."
    )
    upload_res = await client.post(
        "/api/v1/documents/upload",
        files={"file": ("apex_infra.md", io.BytesIO(doc_text.encode("utf-8")), "text/markdown")},
        data={"tags": "infrastructure, cloud"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert upload_res.status_code == 201
    doc_id = uuid.UUID(upload_res.json()["id"])
    await IngestionPipeline.process_document_task(doc_id, org_id, doc_text.encode("utf-8"))

    # 2. Create conversation
    conv_res = await client.post(
        "/api/v1/chat/conversations",
        json={"title": "Cloud Inquiries"},
        headers={"Authorization": f"Bearer {token}"},
    )
    conv_id = conv_res.json()["id"]

    # 3. Send message
    msg_res = await client.post(
        f"/api/v1/chat/conversations/{conv_id}/messages",
        json={
            "content": "What uptime SLA does Apex Systems provide for container orchestration?",
            "top_k": 3,
            "hybrid": True,
            "use_reranking": True,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert msg_res.status_code == 200
    msg_data = msg_res.json()
    assert msg_data["sender_type"] == "assistant"
    assert len(msg_data["content"]) > 0
    assert len(msg_data["citations"]) >= 1

    # Verify citation attributes
    cite = msg_data["citations"][0]
    assert cite["document_id"] == str(doc_id)
    assert "Apex Systems" in cite["snippet"] or "orchestration" in cite["snippet"]

    # 4. Check conversation detail contains history
    detail_res = await client.get(
        f"/api/v1/chat/conversations/{conv_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert detail_res.status_code == 200
    detail = detail_res.json()
    assert len(detail["messages"]) == 2  # 1 User + 1 Assistant
    assert detail["messages"][0]["sender_type"] == "user"
    assert detail["messages"][1]["sender_type"] == "assistant"
    assert len(detail["messages"][1]["citations"]) >= 1


@pytest.mark.asyncio
async def test_stream_message_sse(client: AsyncClient):
    # 1. Setup user & document
    rand = str(uuid.uuid4())[:8]
    signup = await client.post(
        "/api/v1/auth/signup",
        json={
            "email": f"sse_user_{rand}@example.com",
            "password": "Password123!",
            "full_name": "SSE User",
            "organization_name": "Streaming Corp",
        },
    )
    token = signup.json()["access_token"]
    org_id = uuid.UUID(signup.json()["organization"]["id"])

    doc_text = "SolarisDB provides instant horizontal sharding across five global regions."
    upload_res = await client.post(
        "/api/v1/documents/upload",
        files={"file": ("solaris.txt", io.BytesIO(doc_text.encode("utf-8")), "text/plain")},
        data={},
        headers={"Authorization": f"Bearer {token}"},
    )
    doc_id = uuid.UUID(upload_res.json()["id"])
    await IngestionPipeline.process_document_task(doc_id, org_id, doc_text.encode("utf-8"))

    # 2. Create conversation
    conv_res = await client.post(
        "/api/v1/chat/conversations",
        json={"title": "Solaris Questions"},
        headers={"Authorization": f"Bearer {token}"},
    )
    conv_id = conv_res.json()["id"]

    # 3. Stream assistant message
    sse_response = await client.post(
        f"/api/v1/chat/conversations/{conv_id}/messages/stream",
        json={
            "content": "How does SolarisDB handle sharding across regions?",
            "top_k": 3,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert sse_response.status_code == 200
    assert "text/event-stream" in sse_response.headers.get("content-type", "")

    # Parse SSE events from response text
    body = sse_response.text
    assert "data: " in body

    events = []
    for line in body.split("\n"):
        line = line.strip()
        if line.startswith("data: "):
            try:
                event_json = json.loads(line[6:])
                events.append(event_json)
            except json.JSONDecodeError:
                pass

    event_types = [e["type"] for e in events]
    assert "retrieval_status" in event_types
    assert "sources" in event_types
    assert "delta" in event_types
    assert "done" in event_types

    done_event = next(e for e in events if e["type"] == "done")
    assert done_event["data"]["content"]
    assert len(done_event["data"]["citations"]) >= 1
