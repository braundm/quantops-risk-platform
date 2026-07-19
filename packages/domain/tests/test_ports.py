from __future__ import annotations

import unittest

from quantops_domain import (
    AuditEventRepository,
    InstrumentRepository,
    OutboxEventRepository,
    PortfolioRepository,
    PositionRepository,
)


class StructurallyCompleteAdapter:
    async def get(self, entity_id: object) -> None:
        return None

    async def get_by_identity(self, identity: object) -> None:
        return None

    async def add(self, entity: object) -> None:
        return None

    async def save(self, entity: object, **kwargs: object) -> None:
        return None

    async def list_for_portfolio(self, portfolio_id: object, **kwargs: object) -> tuple[()]:
        return ()

    async def upsert(self, entity: object) -> None:
        return None

    async def remove(self, entity_id: object) -> None:
        return None

    async def append(self, entity: object) -> None:
        return None

    async def claim_available(self, **kwargs: object) -> tuple[()]:
        return ()


class RepositoryPortTests(unittest.TestCase):
    def test_repository_ports_are_structural_runtime_protocols(self) -> None:
        adapter = StructurallyCompleteAdapter()

        self.assertIsInstance(adapter, InstrumentRepository)
        self.assertIsInstance(adapter, PortfolioRepository)
        self.assertIsInstance(adapter, PositionRepository)
        self.assertIsInstance(adapter, AuditEventRepository)
        self.assertIsInstance(adapter, OutboxEventRepository)


if __name__ == "__main__":
    unittest.main()
