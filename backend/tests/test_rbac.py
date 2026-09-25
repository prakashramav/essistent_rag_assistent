import uuid
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_org_scoping_isolation_and_rbac(client: AsyncClient):
    """
    Assert that:
    1. An Admin in Org A can add a member to Org A.
    2. A Viewer or Member cannot perform Admin actions (403 Forbidden).
    3. Multi-tenant isolation: A user belonging exclusively to Org B CANNOT
       access or administer Org A's resources (403 Forbidden).
    """
    # 1. Create Org A with Admin User A
    rand_a = str(uuid.uuid4())[:8]
    user_a_email = f"admin_a_{rand_a}@example.com"
    res_a = await client.post(
        "/api/v1/auth/signup",
        json={
            "email": user_a_email,
            "password": "Password123!",
            "full_name": "Admin A",
            "organization_name": "Organization Alpha",
        },
    )
    assert res_a.status_code == 201
    token_a = res_a.json()["access_token"]
    org_a_id = res_a.json()["organization"]["id"]

    # 2. Create Org B with User B (Tenant B)
    rand_b = str(uuid.uuid4())[:8]
    user_b_email = f"admin_b_{rand_b}@example.com"
    res_b = await client.post(
        "/api/v1/auth/signup",
        json={
            "email": user_b_email,
            "password": "Password123!",
            "full_name": "Admin B",
            "organization_name": "Organization Beta",
        },
    )
    assert res_b.status_code == 201
    token_b = res_b.json()["access_token"]
    org_b_id = res_b.json()["organization"]["id"]

    # 3. Create a third user to invite
    rand_c = str(uuid.uuid4())[:8]
    user_c_email = f"user_c_{rand_c}@example.com"
    res_c = await client.post(
        "/api/v1/auth/signup",
        json={
            "email": user_c_email,
            "password": "Password123!",
            "full_name": "User C",
            "organization_name": "Organization Charlie",
        },
    )
    assert res_c.status_code == 201
    token_c = res_c.json()["access_token"]

    # 4. Admin A invites User C to Org A with VIEWER role
    invite_res = await client.post(
        f"/api/v1/organizations/{org_a_id}/members",
        json={"email": user_c_email, "role": "viewer"},
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert invite_res.status_code == 201
    assert invite_res.json()["role"] == "viewer"

    # 5. User C switches context to Org A
    # User C is a Viewer in Org A, so trying to add another member must fail with 403
    viewer_attempt = await client.post(
        f"/api/v1/organizations/{org_a_id}/members",
        json={"email": user_b_email, "role": "member"},
        headers={
            "Authorization": f"Bearer {token_c}",
            "X-Organization-Id": org_a_id,
        },
    )
    assert viewer_attempt.status_code == 403
    assert "Permission denied" in viewer_attempt.json()["detail"]

    # 6. CRITICAL TEST: Tenant Isolation / Org-Scoping Assertion
    # User B (from Organization Beta) attempts to view or modify Organization Alpha's resources
    tenant_violation_res = await client.get(
        f"/api/v1/organizations/{org_a_id}/members",
        headers={
            "Authorization": f"Bearer {token_b}",
            "X-Organization-Id": org_a_id,
        },
    )
    # Must be 403 Forbidden because User B does NOT belong to Org A
    assert tenant_violation_res.status_code == 403
    assert "not authorized for this organization" in tenant_violation_res.json()["detail"]

    # Even without the header, requesting Org A with User B's token scoped to Org B fails
    cross_tenant_attempt = await client.get(
        f"/api/v1/organizations/{org_a_id}/members",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert cross_tenant_attempt.status_code == 403
