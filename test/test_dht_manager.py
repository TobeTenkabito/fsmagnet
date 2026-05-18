import unittest
from unittest.mock import patch

from network import dht


class FakeSession:
    def __init__(self):
        self.nodes = []

    def add_dht_node(self, node):
        self.nodes.append(node)


class DHTManagerTests(unittest.IsolatedAsyncioTestCase):
    async def test_async_bootstrap_resolves_once_and_dedupes_added_nodes(self):
        session = FakeSession()
        manager = dht.DHTManager(session)
        lookups = []

        async def fake_lookup(host, port, timeout):
            lookups.append((host, port, timeout))
            return ["10.0.0.1", "10.0.0.1", "10.0.0.2"]

        manager._lookup_host = fake_lookup

        with (
            patch.object(dht, "BOOTSTRAP_NODES", [
                ("8.8.8.8", 6881),
                ("router.test", 6881),
                ("router.test", 6881),
            ]),
            patch.object(dht.config, "get", return_value=[
                ("router.test", 6881),
                ("8.8.8.8", 6881),
            ]),
        ):
            first = await manager.add_bootstrap_nodes_async()
            second = await manager.add_bootstrap_nodes_async()

        self.assertEqual(first, 3)
        self.assertEqual(second, 0)
        self.assertEqual(lookups, [("router.test", 6881, dht.DNS_TIMEOUT)])
        self.assertEqual(session.nodes, [
            ("8.8.8.8", 6881),
            ("10.0.0.1", 6881),
            ("10.0.0.2", 6881),
        ])

    def test_normalize_nodes_filters_invalid_entries(self):
        with patch.object(dht.logger, "warning"):
            nodes = dht.DHTManager._normalize_nodes([
                ("Router.Test", "6881"),
                ("router.test", 6881),
                ("", 6881),
                ("bad-port.test", "x"),
                ("too-high.test", 70000),
            ])

        self.assertEqual(nodes, [("Router.Test", 6881)])


if __name__ == "__main__":
    unittest.main()
