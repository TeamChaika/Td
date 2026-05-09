"""Integration-тесты загрузки изображений событий (S3/MinIO).

Проверяет валидацию формата/размера, tenant isolation, вызовы S3.
Real-тесты требуют MinIO и пока пропущены.
"""

from __future__ import annotations

import io
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

# ---------------------------------------------------------------------------
# Mock-тесты (не требуют MinIO)
# ---------------------------------------------------------------------------


class TestEventImageUpload:
    """Тесты загрузки изображений с моком S3."""

    @pytest.fixture(autouse=True)
    async def _setup(self, organizer_user, superadmin_user) -> None:
        pass

    async def _get_organizer_token(self, client: AsyncClient) -> str:
        resp = await client.post(
            "/api/v1/auth/login",
            json={
                "email": "organizer@test-org.example.com",
                "password": "Organizer123!",
            },
        )
        assert resp.status_code == 200
        return resp.json()["access_token"]

    def _jpeg_bytes(self, width: int = 100, height: int = 100) -> bytes:
        """Создать минимальный JPEG."""
        from PIL import Image

        img = Image.new("RGB", (width, height), color=(255, 0, 0))
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=85)
        return buf.getvalue()

    def _large_jpeg_bytes(self) -> bytes:
        """Создать JPEG > 5MB."""
        from PIL import Image

        img = Image.new("RGB", (5000, 5000), color=(0, 255, 0))
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=100)
        # Если меньше 5MB — форсируем
        data = buf.getvalue()
        while len(data) < 5_242_880:  # 5MB + 1KB
            data += data
        return data

    # --- Валидация формата ---

    async def test_upload_valid_jpeg(
        self, client: AsyncClient, async_session
    ) -> None:
        """Загрузка валидного JPEG возвращает URL."""
        from paytools.db.models.organization import Organization
        from paytools.db.repositories.organization import OrganizationRepository
        from paytools.domain.events.service import CreateEventInput, EventService
        from paytools.db.repositories.event import EventRepository

        org_repo = OrganizationRepository(async_session)
        org = await org_repo.get_by_slug("test-org")

        svc = EventService(
            async_session,
            event_repo=EventRepository(async_session),
            org_repo=org_repo,
        )
        event = await svc.create(
            org.id,
            CreateEventInput(
                title="Image Test",
                slug=None,
                schedule={
                    "type": "single",
                    "starts_at": "2026-12-31T20:00:00+03:00",
                    "ends_at": "2027-01-01T03:00:00+03:00",
                },
                capacity_policy={"type": "unlimited"},
            ),
        )

        token = await self._get_organizer_token(client)
        files = {"file": ("test.jpg", self._jpeg_bytes(), "image/jpeg")}

        with patch(
            "paytools.integrations.storage.s3.S3Storage.upload",
            new_callable=AsyncMock,
        ):
            resp = await client.post(
                f"/api/v1/organizer/events/{event.id}/images",
                headers={"Authorization": f"Bearer {token}"},
                data={"kind": "card"},
                files=files,
            )
        assert resp.status_code == 200
        body = resp.json()
        assert "url" in body
        assert "card" in body["url"] or body["kind"] == "card"

    async def test_upload_pdf_rejected_400(
        self, client: AsyncClient, async_session
    ) -> None:
        """Загрузка PDF возвращает 400."""
        from paytools.db.models.organization import Organization
        from paytools.db.repositories.organization import OrganizationRepository
        from paytools.db.repositories.event import EventRepository
        from paytools.domain.events.service import CreateEventInput, EventService

        org_repo = OrganizationRepository(async_session)
        org = await org_repo.get_by_slug("test-org")
        svc = EventService(
            async_session,
            event_repo=EventRepository(async_session),
            org_repo=org_repo,
        )
        event = await svc.create(
            org.id,
            CreateEventInput(
                title="PDF Test",
                slug=None,
                schedule={
                    "type": "single",
                    "starts_at": "2026-12-31T20:00:00+03:00",
                    "ends_at": "2027-01-01T03:00:00+03:00",
                },
                capacity_policy={"type": "unlimited"},
            ),
        )

        token = await self._get_organizer_token(client)
        files = {"file": ("doc.pdf", b"%PDF-1.4 fake pdf", "application/pdf")}

        resp = await client.post(
            f"/api/v1/organizer/events/{event.id}/images",
            headers={"Authorization": f"Bearer {token}"},
            data={"kind": "card"},
            files=files,
        )
        assert resp.status_code == 400

    async def test_upload_exceeds_5mb_rejected_400(
        self, client: AsyncClient, async_session
    ) -> None:
        """Загрузка файла > 5MB возвращает 400."""
        from paytools.db.models.organization import Organization
        from paytools.db.repositories.organization import OrganizationRepository
        from paytools.db.repositories.event import EventRepository
        from paytools.domain.events.service import CreateEventInput, EventService

        org_repo = OrganizationRepository(async_session)
        org = await org_repo.get_by_slug("test-org")
        svc = EventService(
            async_session,
            event_repo=EventRepository(async_session),
            org_repo=org_repo,
        )
        event = await svc.create(
            org.id,
            CreateEventInput(
                title="Large Test",
                slug=None,
                schedule={
                    "type": "single",
                    "starts_at": "2026-12-31T20:00:00+03:00",
                    "ends_at": "2027-01-01T03:00:00+03:00",
                },
                capacity_policy={"type": "unlimited"},
            ),
        )

        token = await self._get_organizer_token(client)
        big_data = self._large_jpeg_bytes()
        files = {"file": ("big.jpg", big_data, "image/jpeg")}

        resp = await client.post(
            f"/api/v1/organizer/events/{event.id}/images",
            headers={"Authorization": f"Bearer {token}"},
            data={"kind": "card"},
            files=files,
        )
        assert resp.status_code == 400

    async def test_upload_without_auth_returns_401(
        self, client: AsyncClient
    ) -> None:
        """Загрузка без авторизации возвращает 401."""
        files = {"file": ("test.jpg", b"fake", "image/jpeg")}
        resp = await client.post(
            "/api/v1/organizer/events/00000000-0000-0000-0000-000000000000/images",
            data={"kind": "card"},
            files=files,
        )
        assert resp.status_code == 401

    # --- Tenant isolation ---

    async def test_upload_to_event_of_other_org_returns_404(
        self, client: AsyncClient, async_session
    ) -> None:
        """Organizer A не может загрузить изображение в событие org B → 404."""
        from paytools.db.models.organization import Organization
        from paytools.db.repositories.organization import OrganizationRepository
        from paytools.db.repositories.event import EventRepository
        from paytools.domain.events.service import CreateEventInput, EventService

        # Регистрируем вторую организацию
        reg_resp = await client.post(
            "/api/v1/public/organizations/register",
            json={
                "email": "img-iso@example.com",
                "password": "StrongPass123!",
                "first_name": "Img",
                "last_name": "Iso",
                "organization_name": "Image Iso",
                "organization_slug": "img-iso",
                "accept_terms": True,
            },
        )
        assert reg_resp.status_code == 201
        org_id_b = reg_resp.json()["organization_id"]

        # Одобряем
        sa_resp = await client.post(
            "/api/v1/auth/login",
            json={
                "email": "superadmin@tdpay.example.com",
                "password": "SuperAdmin123!",
            },
        )
        sa_token = sa_resp.json()["access_token"]
        await client.post(
            f"/api/v1/admin/organizations/{org_id_b}/approve",
            headers={"Authorization": f"Bearer {sa_token}"},
        )

        # Создаём событие во второй организации
        org_repo = OrganizationRepository(async_session)
        org_b = await org_repo.get_by_slug("img-iso")
        svc = EventService(
            async_session,
            event_repo=EventRepository(async_session),
            org_repo=org_repo,
        )
        event_b = await svc.create(
            org_b.id,
            CreateEventInput(
                title="B's Image Event",
                slug=None,
                schedule={
                    "type": "single",
                    "starts_at": "2026-12-31T20:00:00+03:00",
                    "ends_at": "2027-01-01T03:00:00+03:00",
                },
                capacity_policy={"type": "unlimited"},
            ),
        )

        # Организатор A пытается загрузить в событие B
        token_a = await self._get_organizer_token(client)
        files = {"file": ("test.jpg", self._jpeg_bytes(), "image/jpeg")}
        resp = await client.post(
            f"/api/v1/organizer/events/{event_b.id}/images",
            headers={"Authorization": f"Bearer {token_a}"},
            data={"kind": "card"},
            files=files,
        )
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Real-тесты (требуют MinIO в docker-compose)
# ---------------------------------------------------------------------------


@pytest.mark.skip(reason="requires running MinIO container")
class TestEventImageUploadReal:
    """Real-тесты загрузки изображений с реальным MinIO."""

    @pytest.fixture(autouse=True)
    async def _setup(self, organizer_user, superadmin_user) -> None:
        pass

    async def _get_organizer_token(self, client: AsyncClient) -> str:
        resp = await client.post(
            "/api/v1/auth/login",
            json={
                "email": "organizer@test-org.example.com",
                "password": "Organizer123!",
            },
        )
        assert resp.status_code == 200
        return resp.json()["access_token"]

    async def test_upload_and_resize_to_max_1920x1080(self) -> None:
        pass

    async def test_upload_small_image_no_resize_needed(self) -> None:
        pass
