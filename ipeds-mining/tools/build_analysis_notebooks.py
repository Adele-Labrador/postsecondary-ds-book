"""Generate the ten analysis notebooks (01-10) from tools/analysis_cells/.

Usage, from the repository root:

    python tools/build_analysis_notebooks.py            # write all ten
    python tools/build_analysis_notebooks.py 04 05      # write selected notebooks

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


def build(module_name: str) -> Path:
    module = importlib.import_module(f"analysis_cells.{module_name}")
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
    for i, cell in enumerate(module.CELLS):
        if cell.cell_type == "code":
            try:
                ast.parse(cell.source)
            except SyntaxError as err:
                raise SyntaxError(f"{module.FILE} cell {i}: {err}") from err
    nb.cells = module.CELLS
    path = ROOT / "notebooks" / module.FILE
    nbformat.write(nb, path)
    return path


if __name__ == "__main__":
    wanted = sys.argv[1:]
    for name in MODULES:
        if wanted and name[2:] not in wanted:
            continue
        try:
            importlib.import_module(f"analysis_cells.{name}")
        except ModuleNotFoundError:
            continue
        print("wrote", build(name).relative_to(ROOT))
