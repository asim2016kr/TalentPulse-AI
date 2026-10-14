"""Run the real model against a small curated regression set (API usage required).

This set is a smoke evaluation, not a representative estimate of market-wide accuracy.
"""
import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path

try:
    from .ai_classifier import PROMPT
    from .classification_contract import ROOT, VERSION, digest
    from .model_provider import configured_predictor, ProviderError
except ImportError:
    from ai_classifier import PROMPT
    from classification_contract import ROOT, VERSION, digest
    from model_provider import configured_predictor, ProviderError


def evaluate(cases, predict, progress=None):
    results = []
    tp = fp = fn = passed = errors = 0
    blocked = False
    attempted = 0
    for case in cases:
        if blocked:
            results.append({"expected": case, "passed": False, "not_run": True})
            continue
        attempted += 1
        try:
            prediction = predict({"job_title": case["title"], "tags": case["tags"]})
            tech = prediction.is_tech_job
            tp += int(tech and case["tech"])
            fp += int(tech and not case["tech"])
            fn += int(not tech and case["tech"])
            matched = tech == case["tech"] and prediction.role == case["role"] and prediction.experience_level == case["experience"]
            passed += int(matched)
            results.append({"expected": case, "actual": prediction.model_dump(), "passed": matched,
                            "provider_metadata": getattr(predict, "last_metadata", {})})
        except Exception as exc:
            errors += 1
            results.append({"expected": case, "error": str(exc) if isinstance(exc, ProviderError) else type(exc).__name__, "passed": False})
            # Persistent quota/auth/transport problems should not consume the whole run.
            blocked = isinstance(exc, ProviderError) or errors >= 3
        if progress:
            progress(results)
    completed = sum("actual" in result for result in results)
    return {"cases": len(cases), "attempted": attempted, "completed": completed,
            "not_run": len(cases) - attempted, "coverage": completed / len(cases) if cases else 0,
            "exact_passes": passed, "errors": errors,
            "tech_precision": tp / (tp + fp) if tp + fp else None,
            "tech_recall": tp / (tp + fn) if tp + fn else None,
            "all_passed": bool(cases) and passed == len(cases), "results": results}


def main():
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--provider", choices=["gemini", "openai"])
    parser.add_argument("--model")
    parser.add_argument("--cases", type=Path, default=ROOT / "tests/classification_cases.json")
    parser.add_argument("--output", type=Path, default=ROOT / "ingestion/output/classifier_evaluation.json")
    args = parser.parse_args()
    cases = json.loads(args.cases.read_text(encoding="utf-8"))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    def progress(results):
        result = results[-1]
        print(f"Case {len(results)}/{len(cases)}: {'PASS' if result['passed'] else 'FAIL'} - {result['expected']['title']}", flush=True)
        args.output.with_suffix('.checkpoint.json').write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding='utf-8')
    with configured_predictor(args.provider, args.model) as (provider, model, predict):
        report = evaluate(cases, predict, progress)
    report.update(provider=provider, model=model, classifier_version=VERSION,
                  prompt_sha256=digest(PROMPT), cases_sha256=digest(cases),
                  evaluated_at=datetime.now(timezone.utc).isoformat(),
                  metrics_note="Precision/recall use returned predictions only; review coverage and errors alongside them.")
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({key: value for key, value in report.items() if key != "results"}, indent=2))
    raise SystemExit(0 if report["all_passed"] else 2)


if __name__ == "__main__":
    main()
