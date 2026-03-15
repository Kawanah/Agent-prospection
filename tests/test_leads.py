"""
Tests d'intégration pour l'API Leads.
"""

import pytest


class TestLeadsList:
    async def test_liste_vide_au_depart(self, client):
        response = await client.get("/api/leads/")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0
        assert data["leads"] == []
        assert data["page"] == 1

    async def test_pagination_parametres_par_defaut(self, client):
        response = await client.get("/api/leads/")
        data = response.json()
        assert "per_page" in data
        assert data["per_page"] == 20

    async def test_filtre_score_minimum(self, client):
        response = await client.get("/api/leads/?min_score=80")
        assert response.status_code == 200

    async def test_filtre_invalide_score_hors_plage(self, client):
        """Un score > 100 doit être rejeté par la validation Pydantic."""
        response = await client.get("/api/leads/?min_score=150")
        assert response.status_code == 422


class TestLeadsGetById:
    async def test_lead_inexistant_retourne_404(self, client):
        response = await client.get("/api/leads/99999")
        assert response.status_code == 404
        assert "non trouvé" in response.json()["detail"].lower()


class TestLeadsStats:
    async def test_stats_retourne_structure_attendue(self, client):
        response = await client.get("/api/leads/stats")
        assert response.status_code == 200
        data = response.json()
        assert "total" in data
        assert "average_score" in data

    async def test_stats_total_zero_si_db_vide(self, client):
        response = await client.get("/api/leads/stats")
        assert response.json()["total"] == 0


class TestLeadsImportValidation:
    async def test_import_chemin_invalide(self, client):
        """Un path traversal doit être bloqué."""
        response = await client.post(
            "/api/leads/import?file_path=../../etc/passwd"
        )
        assert response.status_code == 400

    async def test_import_extension_non_supportee(self, client):
        response = await client.post(
            "/api/leads/import?file_path=fichier.exe"
        )
        assert response.status_code == 400
