import io
import uuid
import pytest
from httpx import AsyncClient
from app.services.evaluation.retrieval_metrics import RetrievalMetricsCalculator
from app.services.ingestion.pipeline import IngestionPipeline


def test_retrieval_metrics_calculations():
    retrieved = ["doc_a", "doc_b", "doc_c", "doc_d", "doc_e"]
    relevant = {"doc_a", "doc_c"}

    # Precision@3 = 2 hits / 3 = 0.667
    prec = RetrievalMetricsCalculator.calculate_precision_at_k(retrieved, relevant, k=3)
    assert round(prec, 2) == 0.67

    # Recall@3 = 2 hits / 2 total relevant = 1.0
    rec = RetrievalMetricsCalculator.calculate_recall_at_k(retrieved, relevant, k=3)
    assert rec == 1.0

    # MRR: first relevant doc is at rank 1 -> 1.0 / 1 = 1.0
    mrr = RetrievalMetricsCalculator.calculate_mrr(retrieved, relevant)
    assert mrr == 1.0

    # Test MRR when first hit is at rank 2
    retrieved_2 = ["doc_x", "doc_a", "doc_y"]
    assert RetrievalMetricsCalculator.calculate_mrr(retrieved_2, relevant) == 0.5


@pytest.mark.asyncio
async def test_single_query_evaluation_endpoint(client: AsyncClient):
    # 1. Register User & Org
    rand = str(uuid.uuid4())[:8]
    signup = await client.post(
        "/api/v1/auth/signup",
        json={
            "email": f"eval_user_{rand}@example.com",
            "password": "Password123!",
            "full_name": "Evaluation Engineer",
            "organization_name": "Eval Testing Corp",
        },
    )
    assert signup.status_code == 201
    token = signup.json()["access_token"]
    org_id = uuid.UUID(signup.json()["organization"]["id"])

    # 2. Ingest Document
    doc_text = (
        "# NovaCloud Clustering\n"
        "NovaCloud provides multi-region active-active database clustering "
        "with 10ms cross-region synchronization and automated failover."
    )
    upload_res = await client.post(
        "/api/v1/documents/upload",
        files={"file": ("novacloud.md", io.BytesIO(doc_text.encode("utf-8")), "text/markdown")},
        data={"tags": "clustering, novacloud"},
        headers={"Authorization": f"Bearer {token}"},
    )
    doc_id = uuid.UUID(upload_res.json()["id"])
    await IngestionPipeline.process_document_task(doc_id, org_id, doc_text.encode("utf-8"))

    # 3. Evaluate Single Query
    eval_res = await client.post(
        "/api/v1/evaluation/single",
        json={
            "question": "What synchronization speed does NovaCloud provide?",
            "expected_doc_titles": ["novacloud.md"],
            "top_k": 3,
            "hybrid": True,
            "use_reranking": True,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert eval_res.status_code == 200
    data = eval_res.json()

    evaluation = data["evaluation"]
    assert evaluation["precision_at_k"] > 0
    assert evaluation["mrr"] > 0
    assert evaluation["faithfulness_score"] >= 0.7
    assert evaluation["verdict"] in ("FAITHFUL", "BORDERLINE")
    assert len(evaluation["claims"]) >= 1
    assert evaluation["latency_ms"] > 0
    assert len(data["retrieved_sources"]) >= 1


@pytest.mark.asyncio
async def test_benchmark_suite_and_tenant_isolation(client: AsyncClient):
    # 1. Setup Org A
    rand_a = str(uuid.uuid4())[:8]
    signup_a = await client.post(
        "/api/v1/auth/signup",
        json={
            "email": f"bench_a_{rand_a}@example.com",
            "password": "Password123!",
            "full_name": "Benchmark Admin A",
            "organization_name": "Bench Org A",
        },
    )
    token_a = signup_a.json()["access_token"]
    org_a_id = uuid.UUID(signup_a.json()["organization"]["id"])

    # Setup Org B
    rand_b = str(uuid.uuid4())[:8]
    signup_b = await client.post(
        "/api/v1/auth/signup",
        json={
            "email": f"bench_b_{rand_b}@example.com",
            "password": "Password123!",
            "full_name": "Benchmark Admin B",
            "organization_name": "Bench Org B",
        },
    )
    token_b = signup_b.json()["access_token"]

    # 2. Ingest Document in Org A
    doc_text = "VortexDB delivers sub-millisecond query execution on petabyte-scale graph datasets."
    upload_res = await client.post(
        "/api/v1/documents/upload",
        files={"file": ("vortex.txt", io.BytesIO(doc_text.encode("utf-8")), "text/plain")},
        data={},
        headers={"Authorization": f"Bearer {token_a}"},
    )
    doc_id = uuid.UUID(upload_res.json()["id"])
    await IngestionPipeline.process_document_task(doc_id, org_a_id, doc_text.encode("utf-8"))

    # 3. Run Benchmark in Org A
    run_res = await client.post(
        "/api/v1/evaluation/run",
        json={
            "name": "Q3 Knowledge Benchmark",
            "test_cases": [
                {
                    "question": "What query execution latency does VortexDB deliver?",
                    "ground_truth_doc_titles": ["vortex.txt"],
                    "expected_keywords": ["sub-millisecond", "vortexdb"],
                }
            ],
            "top_k": 3,
        },
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert run_res.status_code == 201
    run_data = run_res.json()
    run_id = run_data["id"]
    assert run_data["name"] == "Q3 Knowledge Benchmark"
    assert run_data["dataset_size"] == 1
    assert run_data["mean_faithfulness"] >= 0.7
    assert len(run_data["results"]) == 1

    # 4. List runs for Org A
    list_res = await client.get(
        "/api/v1/evaluation/runs",
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert list_res.status_code == 200
    runs_list = list_res.json()
    assert any(r["id"] == run_id for r in runs_list)

    # 5. Fetch specific run detail for Org A
    get_res = await client.get(
        f"/api/v1/evaluation/runs/{run_id}",
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert get_res.status_code == 200
    assert get_res.json()["id"] == run_id

    # 6. Tenant Isolation: Org B user tries to access Org A run -> Expect 404
    cross_res = await client.get(
        f"/api/v1/evaluation/runs/{run_id}",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert cross_res.status_code == 404
