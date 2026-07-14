from __future__ import annotations

import argparse
import json
from pathlib import Path

from .leaderboard import render_leaderboard
from .pipeline import SubmissionError, collect_evidence, load_submission, write_json


def run_batch(input_dir: Path, output_dir: Path) -> list[str]:
    teams = []
    failures = {}
    for input_path in sorted(input_dir.glob("*.json")):
        team = input_path.stem
        try:
            team_dir = output_dir / team
            submission = load_submission(input_path)
            base = input_dir.resolve()
            raw_test_files = submission.get("test_files", [])
            submission["test_files"] = []
            for path in raw_test_files:
                resolved = (input_path.parent / path).resolve()
                if base not in resolved.parents:
                    raise SubmissionError(f"test file escapes input directory: {path}")
                submission["test_files"].append(str(resolved))
            result = collect_evidence(submission, team_dir / "screenshots")
            write_json(result, team_dir / "evidence.json")
            from .report import render_report

            render_report(result, team_dir / "report.html")
            teams.append(team)
        except Exception as exc:
            failures[team] = str(exc)
    write_json({"failures": failures}, output_dir / "errors.json")
    render_leaderboard(
        [{**json.loads((output_dir / team / "evidence.json").read_text(encoding="utf-8")), "team": team} for team in teams],
        output_dir / "leaderboard.html",
    )
    return teams


def main() -> int:
    parser = argparse.ArgumentParser(description="Run auto-as for a directory of submissions")
    parser.add_argument("input_dir", type=Path)
    parser.add_argument("-o", "--output", type=Path, default=Path("output"))
    args = parser.parse_args()
    try:
        teams = run_batch(args.input_dir, args.output)
    except SubmissionError as exc:
        parser.error(str(exc))
    print(f"generated {len(teams)} submissions and {args.output / 'leaderboard.html'}")
    if (args.output / "errors.json").exists():
        print(args.output / "errors.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
