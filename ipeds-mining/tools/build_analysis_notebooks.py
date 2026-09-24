"""Generate the ten analysis notebooks (01-10) from tools/analysis_cells/.

Usage, from the repository root:

    python tools/build_analysis_notebooks.py            # write all ten
    python tools/build_analysis_notebooks.py 04 05      # write selected notebooks
    python tools/build_analysis_notebooks.py --check    # verify, write nothing

Every code cell is parsed with ``ast`` before it is written, so a syntax error fails
the build rather than surfacing halfway through an executed notebook.
"""

from __future__ import annotations

import ast
import importlib
import sys
from pathlib import Path

import nbformat

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

MODULES = [f"nb{i:02d}" for i in range(1, 11)]


def cells_for(module_name: str):
    module = importlib.import_module(f"analysis_cells.{module_name}")
    for i, cell in enumerate(module.CELLS):
        if cell.cell_type == "code":
            try:
                ast.parse(cell.source)
            except SyntaxError as err:
                raise SyntaxError(f"{module.FILE} cell {i}: {err}") from err
    return module


def check(module_name: str) -> list[str]:
    """Return drift problems between a cell module and its committed notebook."""
    module = cells_for(module_name)
    path = ROOT / "notebooks" / module.FILE
    if not path.exists():
        return [f"{module.FILE}: missing; run the builder"]
    committed = nbformat.read(path, as_version=4).cells
    expected = module.CELLS
    if len(committed) != len(expected):
        return [f"{module.FILE}: {len(committed)} cells, source defines {len(expected)}"]
    return [
        f"{module.FILE} cell {i}: source differs from tools/analysis_cells/{module_name}.py"
        for i, (a, b) in enumerate(zip(committed, expected))
        if a.cell_type != b.cell_type or a.source != b.source
    ]


def build(module_name: str) -> Path:
    module = cells_for(module_name)
    nb = nbformat.v4.new_notebook()
    nb.metadata["kernelspec"] = {
        "name": "python3",
        "display_name": "Python 3",
        "language": "python",
    }
    nb.metadata["ipeds_mining"] = {
        "notebook": module.FILE,
        "title": module.TITLE,
        "generated_by": "tools/build_analysis_notebooks.py",
    }
    nb.cells = module.CELLS
    path = ROOT / "notebooks" / module.FILE
    nbformat.write(nb, path)
    return path


if __name__ == "__main__":
    args = sys.argv[1:]
    if "--check" in args:
        problems = [msg for name in MODULES for msg in check(name)]
        for msg in problems:
            print(msg)
        print(f"{len(MODULES)} notebooks checked, {len(problems)} problems")
        sys.exit(1 if problems else 0)
    wanted = args
    for name in MODULES:
        if wanted and name[2:] not in wanted:
            continue
        try:
            importlib.import_module(f"analysis_cells.{name}")
        except ModuleNotFoundError:
            continue
        print("wrote", build(name).relative_to(ROOT))
