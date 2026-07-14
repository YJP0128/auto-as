from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .pipeline import SubmissionError, collect_evidence, load_submission, write_json
from .report import render_report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Collect evidence for an auto-as submission")
    parser.add_argument("input", type=Path, help="submission JSON")
    parser.add_argument("-o", "--output", type=Path, default=Path("output/evidence.json"))
    args = parser.parse_args(argv)

    try:
        submission = load_submission(args.input)
        base = args.input.parent.resolve()
        raw_test_files = submission.get("test_files", [])
        submission["test_files"] = []
        for path in raw_test_files:
            resolved = (base / path).resolve()
            if base not in resolved.parents:
                raise SubmissionError(f"test file escapes submission directory: {path}")
            submission["test_files"].append(str(resolved))
        result = collect_evidence(submission, args.output.parent / "screenshots")
        write_json(result, args.output)
        report_path = args.output.with_name("report.html")
        render_report(result, report_path)
    except SubmissionError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    print(args.output)
    print(report_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
