"""PEHero — FastHTML app.

Single process, two route groups:
  - /                 marketing landing (landing/routes.py)
  - /app/*            3-pane chat product (chat/routes.py)
"""

from __future__ import annotations

from fasthtml.common import fast_app, serve

from utils.config import settings

app, rt = fast_app(
    live=False,
    static_path=".",
    pico=False,
    secret_key=settings().app_secret,
    htmx=True,
)

# Route modules register their handlers against `rt`. Importing for side effects.
from landing import routes as _landing_routes  # noqa: E402,F401
from chat import routes as _chat_routes  # noqa: E402,F401
from chat import pipeline as _pipeline_routes  # noqa: E402,F401
from chat import instructions as _instructions_routes  # noqa: E402,F401
from chat import analytics as _analytics_routes  # noqa: E402,F401
from chat import companies as _companies_routes  # noqa: E402,F401
from chat import memo_pdf as _memo_pdf_routes  # noqa: E402,F401
from chat import exports as _export_routes  # noqa: E402,F401
from chat import dataroom as _dataroom_routes  # noqa: E402,F401
from chat import help as _help_routes  # noqa: E402,F401
from chat import valuation as _valuation_routes  # noqa: E402,F401


def _serve_default():
    serve(port=settings().port)


if __name__ == "__main__":
    _serve_default()
