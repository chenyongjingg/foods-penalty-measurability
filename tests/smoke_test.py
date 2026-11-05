"""Code-level smoke tests (Plan §7 M2/M3 style).

These prove the instruments fire on synthetic data before any real-data claim
is made: alignment math, anchor mapping, attack-tolerance direction, Hawkes
parameter recovery, intake rule, JSON repair.
"""
from __future__ import annotations

import math
import random
import unittest

import numpy as np


class TestAlign(unittest.TestCase):
    def test_ground_drops_hallucination(self):
        from foods_pipeline.label import align
        doc = "当事人伪造检验检测报告，被罚款。"
        ents = [{"type": "TACTIC", "text": "伪造检验检测报告"},
                {"type": "TACTIC", "text": "不存在的片段"}]
        g = align.ground(doc, ents)
        self.assertEqual(len(g), 1)
        self.assertEqual(g[0]["start"], 3)

    def test_iou_and_match(self):
        from foods_pipeline.label import align
        a = [{"type": "TACTIC", "text": "x", "start": 0, "end": 10}]
        b = [{"type": "TACTIC", "text": "y", "start": 4, "end": 14}]
        self.assertAlmostEqual(align.iou(a[0], b[0]), 6 / 14)
        _, _, f1 = align.micro_f1(a, b, tau=0.4)
        self.assertEqual(f1, 1.0)
        _, _, f1b = align.micro_f1(a, b, tau=0.5)
        self.assertEqual(f1b, 0.0)


class TestAnchors(unittest.TestCase):
    def test_map(self):
        from foods_pipeline.label import anchors
        text = "依据《中华人民共和国食品安全法》第一百二十五条之规定"
        r = anchors.label(text)
        self.assertEqual(r["category"], "FALSE_LABELING")
        self.assertFalse(r["ambiguous"])

    def test_ambiguous_excluded(self):
        from foods_pipeline.label import anchors
        text = "依据《食品安全法》第一百二十四条和第一百二十五条"
        r = anchors.label(text)
        self.assertTrue(r["ambiguous"])
        self.assertIsNone(r["category"])

    def test_macro_f1(self):
        from foods_pipeline.label.anchors import anchor_f1
        r = anchor_f1([("A", "A"), ("B", "A"), ("B", "B")])
        self.assertAlmostEqual(r["micro_f1"], 2 / 3, places=4)
        self.assertTrue(0 < r["macro_f1"] <= 1)


class TestAttack(unittest.TestCase):
    def test_targeted_faster_than_random(self):
        import networkx as nx
        from foods_pipeline.analyze.attack import auc, curve
        g = nx.Graph()
        for h in range(5):
            hub = f"hub{h}"
            for i in range(20):
                g.add_edge(hub, f"h{h}n{i}")
            g.add_edge(hub, f"hub{(h+1)%5}")
        rng = random.Random(0)
        order = sorted(g.nodes, key=lambda x: g.degree(x), reverse=True)
        targeted = auc(curve(g, order))
        nodes = list(g.nodes)
        rng.shuffle(nodes)
        rand = auc(curve(g, nodes))
        self.assertLess(targeted, rand)


class TestHawkes(unittest.TestCase):
    def test_parameter_recovery(self):
        from foods_pipeline.analyze.hawkes import _nll
        rng = np.random.default_rng(7)
        mu, alpha, beta, T = 0.05, 0.4, 1.0, 300.0
        events, t = [], 0.0
        while t < T:
            lam_bar = mu + alpha * sum(math.exp(-beta * (t - e)) for e in events)
            t += rng.exponential(1.0 / max(lam_bar, 1e-6))
            if t >= T:
                break
            lam = mu + alpha * sum(math.exp(-beta * (t - e)) for e in events)
            if rng.random() < lam / max(lam_bar, 1e-6):
                events.append(t)
        self.assertGreater(len(events), 20)
        from scipy import optimize
        tarr = np.array(events)
        best = optimize.minimize(_nll, [0.1, 0.3, 0.8], args=(tarr, T),
                                 method="L-BFGS-B",
                                 bounds=[(1e-9, None), (0, None), (1e-6, None)])
        a, b = best.x[1], best.x[2]
        self.assertGreater(a / b, 0.2)
        self.assertLess(a / b, 0.8)


class TestIntake(unittest.TestCase):
    def test_rule(self):
        from foods_pipeline.clean.normalize import intake_decision
        ok, _ = intake_decision("当事人伪造检验检测报告用于食品经营")
        self.assertTrue(ok)
        ok2, why = intake_decision("当事人销售过期食品")
        self.assertFalse(ok2)


class TestJson(unittest.TestCase):
    def test_fenced(self):
        from foods_pipeline.label.llm import parse_json
        self.assertEqual(parse_json('```json\n{"a":1}\n```')["a"], 1)
        self.assertIsNone(parse_json("not json"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
