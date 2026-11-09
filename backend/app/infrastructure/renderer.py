"""Render HCL from Jinja2 templates with strict, injection-safe escaping."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, StrictUndefined

from app.infrastructure.catalog import TemplateSpec

TEMPLATE_DIR = Path(__file__).parent / "templates"


def hcl_string(value: Any) -> str:
    """Render a value as an HCL literal. Strings are JSON-quoted and interpolation-escaped."""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int | float):
        return str(value)
    text = json.dumps(str(value))
    # Disable HCL template interpolation/directives inside user-provided strings.
    return text.replace("${", "$${").replace("%{", "%%{")


def hcl_map(value: dict[str, Any]) -> str:
    if not value:
        return "{}"
    inner = "\n".join(f"    {hcl_string(k)} = {hcl_string(v)}" for k, v in sorted(value.items()))
    return "{\n" + inner + "\n  }"


def _env() -> Environment:
    env = Environment(  # noqa: S701 - output is HCL, not HTML; values escaped via filters
        loader=FileSystemLoader(str(TEMPLATE_DIR)),
        undefined=StrictUndefined,
        trim_blocks=True,
        lstrip_blocks=True,
        keep_trailing_newline=True,
    )
    env.filters["hcl"] = hcl_string
    env.filters["hcl_map"] = hcl_map
    env.filters["tf_id"] = lambda v: "".join(c if c.isalnum() else "_" for c in str(v)).lower()
    return env


def render_template(spec: TemplateSpec, params: dict[str, Any], *, account_external_id: str) -> str:
    tags = {**params.get("tags", {}), "managed_by": "mcmp", "mcmp_template": spec.key}
    context = {**params, "tags": tags, "account_external_id": account_external_id}
    return _env().get_template(spec.file).render(**context)
