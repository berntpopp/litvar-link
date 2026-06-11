"""Command-line interface for LitVar-Link (typer).

Thin wiring layer: the actual command behaviour lives in
``litvar_link.cli_commands.{data,serve}``. The console script entry point is the
``app`` callable (``[project.scripts] litvar-link = "litvar_link.cli:app"``);
``python -m litvar_link.cli`` runs the same app via ``main``.
"""

from __future__ import annotations

import typer

from litvar_link.cli_commands import data, serve

app = typer.Typer(help="LitVar-Link CLI", no_args_is_help=True)

data.register(app)
serve.register(app)


def main() -> None:
    """Console-script entry point (also used by ``python -m litvar_link.cli``)."""
    app()


if __name__ == "__main__":
    main()
