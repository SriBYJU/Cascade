from __future__ import annotations


def render_tutorial() -> str:
    return """CASCADE QUICK TUTORIAL

1. Check your environment
   optimizer doctor

2. Install Cascade into your project
   optimizer project-install --target /path/to/repo

3. Move into the project
   cd /path/to/repo

4. Preview a task before executing it
   optimizer plan "Fix the API validation bug" --write "src/api/**"
   optimizer why

5. Run the task
   optimizer run "Fix the API validation bug" --write "src/api/**"

6. Inspect what Cascade did
   optimizer trace
   optimizer why
   optimizer stats
   optimizer status

7. Apply a verified writer result when you want integration
   optimizer run "Fix the API validation bug" --write "src/api/**" --apply

8. Measure Cascade against plain Codex
   optimizer benchmark --suite live --configs plain,cascade --repeats 3 \
     --output .cascade/benchmarks/live
   optimizer savings .cascade/benchmarks/live/report.json

9. Remove the project integration
   optimizer project-uninstall --target /path/to/repo

Tip: omit --apply while evaluating Cascade. Writer changes remain isolated
until verification and merge gates pass.
"""
