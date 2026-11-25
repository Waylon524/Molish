import json
from pathlib import Path
import unittest

from export_enzyme import DEFAULT_SOURCE, compile_model, export, make_unreachable_result
from finite03 import Engine, cbor
from molish04 import dg, get_case, make_query, make_result, model04, parse, verify_closure


class EnzymeTests(unittest.TestCase):
    def setUp(self):
        self.source = json.loads(DEFAULT_SOURCE.read_text())
        self.entity = self.source["entityId"]
        self.model = compile_model(self.source)
        self.core = parse(parse(self.model, 0)[0], 0, 3)

    def test_module_condition_applies_to_search_and_replay(self):
        self.core[0][2].append([3, self.entity, "context", 0, 1])
        self.core[0][4][0][3].insert(0, [0, 3, 1])
        initial = self.core[7][1][0]
        self.core[7][1] = [[[0, initial[0][1], flag], initial[1], initial[2]] for flag in (0, 1)]
        engine = Engine(self.core)
        disabled, enabled = engine.start
        binding_goal = [[], [[0, 1, 1]]]
        self.assertIsNone(engine.explore(disabled, binding_goal))
        self.assertIsNone(engine.step(disabled, 10, [self.entity]))
        self.assertIsNotNone(engine.step(enabled, 10, [self.entity]))
        _, events, binding = engine.explore(enabled, binding_goal)
        model = model04(self.core)
        query = make_query(model, binding_goal)
        result = make_result(model, query, enabled, events, binding)
        get_case(model, query, result, dg(cbor(enabled)))
        forged = make_result(model, query, disabled, events, binding)
        with self.assertRaisesRegex(ValueError, "^TRACE$"):
            get_case(model, query, forged, dg(cbor(disabled)))

    def test_slot_and_containment_rules_use_the_same_pre_state(self):
        region = self.core[7][1][0][0][1]
        second_region = 300
        self.core[0][0].append([second_region, 1, "other"])
        self.core[0][1][1][2].append(second_region)
        self.core[0][2][1][4] = 0
        self.core[0][4][0][5].append([40, [], [[1, 1], [2, second_region]], []])
        self.core[0][7][2] = [[region, second_region, [[0, 1, 1]]]]
        engine = Engine(self.core)
        self.assertIsNone(engine.step(engine.start[0], 40, []))
        bound, _ = engine.step(engine.start[0], 10, [self.entity])
        moved, delta = engine.step(bound, 40, [])
        self.assertEqual(delta, [[0, 2, second_region]])
        self.assertIn(second_region, engine.containers(moved, self.entity))
        self.assertIsNone(engine.step(bound, 40, [], [[2, self.entity, second_region]]))

    def test_declaring_a_conflicting_rule_id_is_rejected(self):
        self.core[0][4][0][5].append([10, [], [], []])
        with self.assertRaisesRegex(ValueError, "^duplicate rule$"):
            Engine(self.core)

    def test_playback_identity_material_accounting_and_source(self):
        manifest = export(self.source)
        normal = manifest["scenarios"]["normal"]
        self.assertEqual(
            [(step["phase"], step["substrate"], step["product"]) for step in normal["steps"]],
            [("free", 3, 0), ("bound", 2, 0), ("converted", 2, 0), ("released", 2, 1)],
        )
        self.assertEqual({step["entityId"] for step in normal["steps"]}, {self.entity})
        self.assertEqual([step["evidence"]["id"] for step in normal["steps"][1:]], [1, 1, 1])
        self.assertEqual(normal["proof"]["verdict"], "reachable")
        self.assertEqual(manifest, json.loads(Path(__file__).with_name("enzyme-trace.json").read_text()))

    def test_blocked_playback_has_a_distinct_verified_no_proof(self):
        blocked = export(self.source)["scenarios"]["blocked"]
        self.assertEqual([step["phase"] for step in blocked["steps"]], ["free", "bound"])
        self.assertTrue(all(step["product"] == 0 for step in blocked["steps"]))
        self.assertFalse(blocked["targetReached"])
        self.assertNotEqual(blocked["targetQueryDigest"], blocked["queryDigest"])
        query, result = [bytes.fromhex(blocked["proof"][key]) for key in ("targetQueryCbor", "targetResultCbor")]
        self.assertEqual(dg(query).hex(), blocked["targetQueryDigest"])
        self.assertEqual(dg(result).hex(), blocked["targetResultDigest"])
        states = verify_closure(self.model, query, result, bytes.fromhex(blocked["caseId"]))
        self.assertEqual({state[0][0] for state in states}, {0, 1})
        initial = Engine(self.core).start[0]
        incomplete = make_unreachable_result(self.model, query, initial, [initial])
        with self.assertRaisesRegex(ValueError, "^CLOSURE_EDGE$"):
            verify_closure(self.model, query, incomplete, bytes.fromhex(blocked["caseId"]))

    def test_source_fields_compile_and_change_the_model_digest(self):
        modified = export({"entityId": 1, "region": "second-matrix", "initialSubstrate": 5})
        normal = modified["scenarios"]["normal"]
        self.assertEqual(normal["steps"][0]["substrate"], 5)
        self.assertEqual({step["entityId"] for step in normal["steps"]}, {1})
        self.assertEqual(modified["region"], "second-matrix")
        self.assertNotEqual(normal["modelDigest"], dg(self.model).hex())


if __name__ == "__main__":
    unittest.main()
