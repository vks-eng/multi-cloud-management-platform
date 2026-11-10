"""Every role against every permission-protected endpoint, generated from the RBAC matrix.

Routes are discovered by introspecting the FastAPI app for `require(Permission)` dependencies,
so a new endpoint is covered automatically. A role lacking the permission must get 403;
a role holding it must never get 403 (it may get 404/422 because the test sends dummy ids).
"""

from __future__ import annotations

import re
import uuid

import pytest

from app.core.permissions import ROLE_PERMISSIONS, Role

API = "/api/v1"
DUMMY_ID = str(uuid.UUID(int=0))


def _protected_routes() -> list[tuple[str, str, str]]:
    from fastapi.routing import APIRoute

    from app.api.routes import (
        accounts,
        audit,
        auth,
        costs,
        infrastructure,
        monitoring,
        resources,
        system,
        users,
    )

    routes = [
        r
        for module in (
            auth,
            users,
            accounts,
            resources,
            infrastructure,
            monitoring,
            costs,
            audit,
            system,
        )
        for r in module.router.routes
        if isinstance(r, APIRoute)
    ]
    found: list[tuple[str, str, str]] = []
    for route in routes:
        perms = {
            getattr(dep.call, "permission", None)
            for dep in route.dependant.dependencies
            if getattr(dep.call, "permission", None) is not None
        }
        for perm in perms:
            for method in sorted(route.methods - {"HEAD", "OPTIONS"}):
                path = API + re.sub(r"\{key\}", "aws_s3_bucket", route.path)
                path = re.sub(r"\{[a-z_]+\}", DUMMY_ID, path)
                found.append((method, path, perm.value))
    return sorted(found)


ROUTES = _protected_routes()


def test_matrix_covers_every_permission():
    covered = {perm for _, _, perm in ROUTES}
    every = {p.value for perms in ROLE_PERMISSIONS.values() for p in perms}
    assert covered == every, f"permissions without an endpoint: {every - covered}"
    assert len(ROUTES) >= 40


@pytest.mark.parametrize("role", [r.value for r in Role])
def test_role_against_every_protected_endpoint(client, auth_headers, role):
    headers = auth_headers(role)
    granted = {p.value for p in ROLE_PERMISSIONS[Role(role)]}
    failures = []
    for method, path, perm in ROUTES:
        kwargs = {"json": {}} if method in {"POST", "PUT", "PATCH"} else {}
        resp = client.request(method, path, headers=headers, **kwargs)
        denied = resp.status_code == 403
        if (perm in granted) == denied:
            failures.append(f"{method} {path} [{perm}] -> {resp.status_code}")
    assert not failures, "\n".join(failures)


def test_unauthenticated_requests_rejected_everywhere(client):
    failures = [
        f"{m} {p} -> {r.status_code}"
        for m, p, _ in ROUTES
        if (
            r := client.request(m, p, **({"json": {}} if m in {"POST", "PUT", "PATCH"} else {}))
        ).status_code
        != 401
    ]
    assert not failures, "\n".join(failures)
