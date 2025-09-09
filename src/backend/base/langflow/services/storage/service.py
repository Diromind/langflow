from __future__ import annotations

from abc import abstractmethod
from typing import TYPE_CHECKING

import anyio

from langflow.services.base import Service

if TYPE_CHECKING:
    from lfx.services.settings.service import SettingsService

    from langflow.services.session.service import SessionService


class StorageService(Service):
    name = "storage_service"

    def __init__(self, session_service: SessionService, settings_service: SettingsService):
        self.settings_service = settings_service
        self.session_service = session_service
        self.data_dir: anyio.Path = anyio.Path(settings_service.settings.config_dir)
        self.set_ready()

    def build_full_path(self, identifier: str, file_name: str) -> str:
        """Build the full path of a file."""
        return self._build_path(identifier, file_name)

    def _build_path(self, identifier: str, file_name: str) -> str:
        """Internal method to build path - to be implemented by subclasses."""
        raise NotImplementedError

    def set_ready(self) -> None:
        self.ready = True

    @abstractmethod
    async def save_file(self, identifier: str, file_name: str, data: bytes) -> None:
        """Save a file."""
        raise NotImplementedError

    @abstractmethod
    async def get_file(self, identifier: str, file_name: str) -> bytes:
        """Get a file."""
        raise NotImplementedError

    @abstractmethod
    async def list_files(self, identifier: str) -> list[str]:
        """List files."""
        raise NotImplementedError

    @abstractmethod
    async def get_file_size(self, identifier: str, file_name: str) -> int:
        """Get file size."""
        raise NotImplementedError

    @abstractmethod
    async def delete_file(self, identifier: str, file_name: str) -> None:
        """Delete a file."""
        raise NotImplementedError

    async def teardown(self) -> None:
        raise NotImplementedError
