# SPDX-License-Identifier: GPL-2.0-or-later
"""Queue evidence from recorded JSONL, including the published proof."""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT / "python"))

from sgcontrol.events import competing_wait, load_events, queue_snapshot


class EventTests(unittest.TestCase):
    def test_recorded_proof_has_competing_wait(self):
        payload = json.loads((PROJECT / "queue-proof.json").read_text(encoding="utf-8"))
        evidence = competing_wait(payload["events"])
        self.assertIsNotNone(evidence)
        self.assertGreater(evidence["wait_ms"], 20)
        self.assertAlmostEqual(evidence["wait_ms"], 925.935, places=3)
        snap = queue_snapshot(payload["events"])
        self.assertEqual(snap["starts"], 2)
        self.assertEqual(snap["finishes"], 2)

    def test_jsonl_roundtrip(self):
        text = "\n".join(
            [
                "not json",
                '{"event":"queued","op":"read","ticket":1,"time":1.0,"wait_ms":0,"pending":0,"file_tag":"a"}',
                '{"event":"start","op":"read","ticket":1,"time":1.0,"wait_ms":0,"pending":0,"file_tag":"a"}',
                '{"event":"queued","op":"metadata","ticket":2,"time":1.1,"wait_ms":0,"pending":1,"file_tag":"b"}',
                '{"event":"finish","op":"read","ticket":1,"time":2.0,"wait_ms":0,"pending":1,"file_tag":"a"}',
                '{"event":"start","op":"metadata","ticket":2,"time":2.1,"wait_ms":100,"pending":0,"file_tag":"b"}',
                '{"event":"finish","op":"metadata","ticket":2,"time":2.2,"wait_ms":0,"pending":0,"file_tag":"b"}',
            ]
        )
        events = load_events(text)
        self.assertEqual(len(events), 6)
        evidence = competing_wait(events)
        self.assertEqual(evidence["wait_ms"], 100)
        self.assertEqual(evidence["queued_op"], "metadata")


if __name__ == "__main__":
    unittest.main()
