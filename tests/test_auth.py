"""
Tests d'intégration pour l'authentification JWT.
"""

import pytest


class TestAuthProtection:
    async def test_route_protegee_sans_token_retourne_401(
        self, unauthenticated_client
    ):
        """Accéder à une route protégée sans token doit retourner 401."""
        response = await unauthenticated_client.get("/api/leads/")
        assert response.status_code == 401

    async def test_route_protegee_avec_token_invalide_retourne_401(
        self, unauthenticated_client
    ):
        unauthenticated_client.headers["Authorization"] = "Bearer tokenbidon"
        response = await unauthenticated_client.get("/api/leads/")
        assert response.status_code == 401

    async def test_route_protegee_avec_token_valide_retourne_200(self, client):
        """Un token JWT valide doit donner accès aux routes protégées."""
        response = await client.get("/api/leads/")
        assert response.status_code == 200

    async def test_me_retourne_username_admin(self, client):
        response = await client.get("/api/auth/me")
        assert response.status_code == 200
        assert response.json()["username"] == "admin"
        assert response.json()["role"] == "admin"


class TestHealthRoutes:
    async def test_health_check_public(self, unauthenticated_client):
        """La route /health est publique — pas besoin de token."""
        response = await unauthenticated_client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"

    async def test_route_racine_publique(self, unauthenticated_client):
        response = await unauthenticated_client.get("/")
        assert response.status_code == 200
        assert "status" in response.json()
