"""S3-хранилище (MinIO / TimeWeb Cloud S3).

Использует aioboto3 для асинхронной работы.
В MVP — прямой upload через бэк (не pre-signed).
"""

from __future__ import annotations

from dataclasses import dataclass

import aioboto3


@dataclass
class S3Config:
    """Конфигурация S3-подключения."""

    endpoint_url: str
    bucket: str
    access_key: str
    secret_key: str
    region: str = "ru-1"
    public_endpoint: str = (
        ""  # URL для публичных ссылок (если отличается от endpoint_url)
    )


class S3Storage:
    """Асинхронное хранилище S3 (через aioboto3)."""

    def __init__(self, config: S3Config) -> None:
        self._config = config
        self._session = aioboto3.Session()

    def _client(self):  # type: ignore[no-untyped-def]
        """Создать асинхронный клиент S3."""
        return self._session.client(
            "s3",
            endpoint_url=self._config.endpoint_url,
            aws_access_key_id=self._config.access_key,
            aws_secret_access_key=self._config.secret_key,
            region_name=self._config.region,
        )

    async def ensure_bucket(self) -> None:
        """Создать бакет если не существует."""
        async with self._client() as client:  # type: ignore[no-untyped-call]
            try:
                await client.head_bucket(Bucket=self._config.bucket)
            except Exception:
                await client.create_bucket(Bucket=self._config.bucket)

    async def upload(
        self,
        *,
        key: str,
        data: bytes,
        content_type: str,
    ) -> None:
        """Загрузить объект в S3.

        Args:
            key: путь объекта в бакете (events/{org_id}/{event_id}/...)
            data: содержимое файла
            content_type: MIME-тип
        """
        async with self._client() as client:  # type: ignore[no-untyped-call]
            await client.put_object(
                Bucket=self._config.bucket,
                Key=key,
                Body=data,
                ContentType=content_type,
            )

    def public_url(self, key: str) -> str:
        """Сформировать публичный URL для объекта.

        Использует s3_public_endpoint если задан, иначе s3_endpoint.
        """
        base = self._config.public_endpoint or self._config.endpoint_url
        base = base.rstrip("/")
        return f"{base}/{self._config.bucket}/{key}"

    async def delete(self, key: str) -> None:
        """Удалить объект из S3."""
        async with self._client() as client:  # type: ignore[no-untyped-call]
            await client.delete_object(
                Bucket=self._config.bucket,
                Key=key,
            )
