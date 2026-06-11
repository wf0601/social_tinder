"""Validates the graph algorithms on tiny hand-checkable fixtures plus the
sample dataset. Run: python -m unittest discover -s tests"""

import math
import unittest

from social_tinder import analytics
from social_tinder import build_network, generate_sample_mentions
from social_tinder.types import NetworkQuery


def _adj_from_edges(node_ids, edge_pairs):
    adj = {i: [] for i in node_ids}
    for a, b, w in edge_pairs:
        adj[a].append((b, w))
        adj[b].append((a, w))
    return adj


class TestLLR(unittest.TestCase):
    def test_perfect_association_beats_independent(self):
        # A and B always together (50/50) vs A and C independent.
        strong = analytics.log_likelihood_ratio(k11=50, count_a=50, count_b=50, n=100)
        weak = analytics.log_likelihood_ratio(k11=25, count_a=50, count_b=50, n=100)
        self.assertGreater(strong, weak)
        self.assertGreaterEqual(weak, 0.0)

    def test_independent_pair_near_zero(self):
        # Expected co-occurrence under independence -> G² ~ 0.
        g2 = analytics.log_likelihood_ratio(k11=25, count_a=50, count_b=50, n=100)
        self.assertLess(g2, 1e-6)


class TestPageRank(unittest.TestCase):
    def test_sums_to_one_and_hub_wins(self):
        # Star graph: center c connected to a, b, d.
        ids = ["c", "a", "b", "d"]
        adj = _adj_from_edges(ids, [("c", "a", 1), ("c", "b", 1), ("c", "d", 1)])
        pr = analytics.pagerank(ids, adj)
        self.assertAlmostEqual(sum(pr.values()), 1.0, places=6)
        self.assertGreater(pr["c"], pr["a"])
        self.assertTrue(all(v > 0 for v in pr.values()))


class TestBetweenness(unittest.TestCase):
    def test_bridge_node_is_highest(self):
        # Two triangles joined by a single bridge node x.
        ids = ["a", "b", "c", "x", "d", "e", "f"]
        edges = [
            ("a", "b", 1), ("b", "c", 1), ("a", "c", 1),  # triangle 1
            ("c", "x", 1), ("x", "d", 1),                  # bridge through x
            ("d", "e", 1), ("e", "f", 1), ("d", "f", 1),  # triangle 2
        ]
        bc = analytics.betweenness(ids, _adj_from_edges(ids, edges))
        self.assertEqual(max(bc, key=bc.get), "x")
        self.assertTrue(all(0.0 <= v <= 1.0 for v in bc.values()))


class TestLouvain(unittest.TestCase):
    def test_two_clear_clusters(self):
        # Two dense triangles joined by one weak edge -> two communities.
        ids = ["a", "b", "c", "d", "e", "f"]
        edges = [
            ("a", "b", 1), ("b", "c", 1), ("a", "c", 1),
            ("d", "e", 1), ("e", "f", 1), ("d", "f", 1),
            ("c", "d", 0.05),  # weak bridge
        ]
        adj = _adj_from_edges(ids, edges)
        comm = analytics.louvain(ids, adj)
        self.assertEqual(comm["a"], comm["b"])
        self.assertEqual(comm["b"], comm["c"])
        self.assertEqual(comm["d"], comm["e"])
        self.assertNotEqual(comm["a"], comm["d"])

    def test_louvain_beats_singletons_on_sample(self):
        net = build_network(
            generate_sample_mentions(),
            NetworkQuery(min_strength=0.04, min_cooccurrences=3, min_mentions=5),
        )
        ids = [n.id for n in net.nodes]
        adj = {i: [] for i in ids}
        for e in net.edges:
            adj[e.source].append((e.target, e.strength))
            adj[e.target].append((e.source, e.strength))
        comm = {n.id: n.cluster for n in net.nodes}
        singletons = {i: idx for idx, i in enumerate(ids)}
        q_louvain = analytics.modularity(ids, adj, comm)
        q_singletons = analytics.modularity(ids, adj, singletons)
        self.assertGreater(q_louvain, q_singletons)
        self.assertGreater(q_louvain, 0.3)  # themed data clusters well


class TestDeterminism(unittest.TestCase):
    def test_same_input_same_output(self):
        q = NetworkQuery(min_strength=0.04, min_cooccurrences=3, min_mentions=5)
        a = build_network(generate_sample_mentions(), q)
        b = build_network(generate_sample_mentions(), q)
        self.assertEqual(
            [(n.id, n.cluster, round(n.influence, 9)) for n in a.nodes],
            [(n.id, n.cluster, round(n.influence, 9)) for n in b.nodes],
        )


if __name__ == "__main__":
    unittest.main()
