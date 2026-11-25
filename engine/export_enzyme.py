"""Compile an enzyme lesson and export its verified Molish playback steps."""

import argparse
import json
from pathlib import Path

from finite03 import Engine, cbor, cmp, eff, num, skel, template
from molish04 import assemble, dg, get_case, make_query, make_result, model04, pack, parse, verify_closure

PHASES = ("free", "bound", "converted", "released")
PHASE_SLOT, REGION_SLOT = 1, 2
SUBSTRATE, PRODUCT = 1, 2
BIND, CONVERT, RELEASE = 10, 20, 30
RULES = {
    BIND: "结合底物",
    CONVERT: "转化已结合的底物",
    RELEASE: "释放产物",
}
EVIDENCE = "教学模型的示意假设"
UNIT = "molecule"
DEFAULT_SOURCE = Path(__file__).with_name("enzyme.json")


def compile_model(source):
    if not isinstance(source, dict) or set(source) != {"entityId", "region", "initialSubstrate"}:
        raise ValueError("Expected entityId, region, and initialSubstrate")
    enzyme, region, substrate = source["entityId"], source["region"], source["initialSubstrate"]
    if type(enzyme) is not int or not 1 <= enzyme < 2**32:
        raise ValueError("entityId must be a positive 32-bit integer")
    if not isinstance(region, str) or not region.strip():
        raise ValueError("region must be a nonempty logical region name")
    if type(substrate) is not int or not 1 <= substrate < 2**32:
        raise ValueError("initialSubstrate must be a positive 32-bit integer")
    compartment = 1 if enzyme != 1 else 2
    one = num(UNIT, 1)
    steps = [
        ([cmp(5, num(UNIT, terms=[[SUBSTRATE, 1]]), one)], [eff(SUBSTRATE, 1, one)]),
        ([], []),
        ([], [eff(PRODUCT, 0, one)]),
    ]
    templates = []
    for phase, (rule, (guards, effects)) in enumerate(zip(RULES, steps)):
        templates.append(template(
            rule, [1], [[0, PHASE_SLOT, phase], *guards],
            [[0, PHASE_SLOT, phase + 1], *effects],
        ))
    core = skel(
        [enzyme, compartment], sorts=[[1, [enzyme]]],
        counter=[[SUBSTRATE, compartment, UNIT, substrate, 0], [PRODUCT, compartment, UNIT, 1, 0]],
        initial=[([], [substrate, 0])], templates=templates,
    )
    core[0][0] = sorted([[enzyme, 0, "tracked-enzyme"], [compartment, 1, region]])
    core[0][1] = [[1, 0, list(range(len(PHASES)))], [2, 1, [compartment]]]
    core[0][2] = [[PHASE_SLOT, enzyme, "phase", 1, 0], [REGION_SLOT, enzyme, "region", 2, 1]]
    core[0][3] = [[1, 0, EVIDENCE, "E + S → ES → EP → E + P", []]]
    core[0][4][0][3] = [[1, enzyme, compartment]]
    core[0][7] = [1, [[enzyme, REGION_SLOT]], []]
    core[7][1][0][0] = [0, compartment]
    sources = [[1, 3, "Molish", "symbolic-enzyme-lesson", "1", "scheme", [0]]]
    claims = [[index, 1, 1, [1, rule], 0] for index, rule in enumerate(RULES, 1)]
    return model04(core, sources=sources, claims=claims)


def make_unreachable_result(model, query, initial, states):
    core_bytes = parse(model, 0)[0]
    query_bytes = parse(query, 1)[1]
    nested = pack(2, [dg(core_bytes), dg(query_bytes), 1, 1, 0, [[initial, 1, sorted(states)]]], 3)
    return pack(2, [dg(model), dg(query), nested])


def export_scenario(model, engine, enzyme, block_conversion):
    initial, = engine.start
    case_id = dg(cbor(initial))
    forbidden = [[0, CONVERT]] if block_conversion else []
    target = [[], [[0, PHASE_SLOT, 3], cmp(5, num(UNIT, terms=[[PRODUCT, 1]]), num(UNIT, 1))]]
    target_query = make_query(model, target, forbidden)
    target_witness = engine.explore(initial, target, forbidden)

    if target_witness is not None:
        query = target_query
        _, events, target_binding = target_witness
        result = target_result = make_result(model, query, initial, events, target_binding)
    else:
        states = engine.explore(initial, forbid=forbidden)
        target_result = make_unreachable_result(model, target_query, initial, states)
        verify_closure(model, target_query, target_result, case_id)
        binding_target = [[], [[0, PHASE_SLOT, 1]]]
        query = make_query(model, binding_target, forbidden)
        _, events, target_binding = engine.explore(initial, binding_target, forbidden)
        result = make_result(model, query, initial, events, target_binding)

    states, checked_events, _ = get_case(model, query, result, case_id)
    output_steps = []
    for index, (slots, _, counters) in enumerate(states):
        rule = evidence = None
        if index:
            rule_id, binding, _ = checked_events[index - 1]
            if binding != [enzyme]:
                raise ValueError("Trace changed the tracked enzyme identity")
            rule = {"id": rule_id, "name": RULES[rule_id]}
            applicable = engine.applicable_evidence(states[index - 1], rule_id)
            if applicable:
                evidence_id, _, evidence_label, *_ = applicable[0]
                evidence = {"id": evidence_id, "label": evidence_label}
        output_steps.append({
            "index": index, "phase": PHASES[slots[engine.slot_id[PHASE_SLOT]]],
            "substrate": counters[engine.counter_id[SUBSTRATE]],
            "product": counters[engine.counter_id[PRODUCT]],
            "entityId": enzyme, "rule": rule, "evidence": evidence,
        })

    return {
        "modelDigest": dg(model).hex(), "queryDigest": dg(query).hex(),
        "resultDigest": dg(result).hex(), "caseId": case_id.hex(),
        "targetReached": target_witness is not None,
        "targetQueryDigest": dg(target_query).hex(), "targetResultDigest": dg(target_result).hex(),
        "proof": {
            "target": "release",
            "verdict": "reachable" if target_witness is not None else "unreachable",
            "modelCbor": model.hex(), "queryCbor": query.hex(), "resultCbor": result.hex(),
            "targetQueryCbor": target_query.hex(), "targetResultCbor": target_result.hex(),
        },
        "steps": output_steps,
    }


def export(source):
    model = compile_model(source)
    core, _, _ = assemble(model, {})
    enzyme = source["entityId"]
    engine = Engine(core)
    return {
        "version": 1, "entityId": enzyme, "region": source["region"],
        "scenarios": {
            "normal": export_scenario(model, engine, enzyme, False),
            "blocked": export_scenario(model, engine, enzyme, True),
        },
    }


def main():
    args = argparse.ArgumentParser(description=__doc__)
    args.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    args.add_argument("output", type=Path, nargs="?")
    params = args.parse_args()
    text = json.dumps(export(json.loads(params.source.read_text())), ensure_ascii=False, indent=2)
    if params.output is None:
        print(text)
    else:
        params.output.write_text(text + "\n")


if __name__ == "__main__":
    main()
