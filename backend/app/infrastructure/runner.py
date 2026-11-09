"""Terraform execution.

* When `terraform` is on PATH, TERRAFORM_MODE=auto and CLOUD_PROVIDER_MODE=real, the runner
  executes `terraform init` + `terraform plan -out=tfplan` in an isolated working directory.
* Otherwise it produces a **clearly labelled mock plan** derived from the rendered HCL.
* `apply` is never automatic: the provisioning service only calls it after an explicit,
  token-verified confirmation, and real applies additionally require
  TERRAFORM_APPLY_ENABLED=true.
"""

from __future__ import annotations

import logging
import os
import re
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.core.config import Settings, get_settings
from app.core.errors import BusinessRuleError, ProviderError
from app.core.logging import redact_text
from app.models.enums import CloudProvider, ProvisioningAction

logger = logging.getLogger(__name__)

MOCK_BANNER = (
    "[MOCK PLAN] Terraform was NOT executed. This plan was simulated from the rendered "
    "configuration and has not been validated by Terraform or the cloud provider."
)
_PLAN_SUMMARY_RE = re.compile(r"Plan: (\d+) to add, (\d+) to change, (\d+) to destroy")
_RESOURCE_RE = re.compile(r'^resource\s+"([\w-]+)"\s+"([\w-]+)"\s*\{', re.MULTILINE)
_ATTR_RE = re.compile(r"^\s{2}([a-z_]+)\s*=\s*(.+)$")
_TIMEOUT_SECONDS = 900


@dataclass(slots=True)
class PlanResult:
    output: str
    summary: dict[str, int]
    is_mock: bool
    resources: list[str] = field(default_factory=list)


def terraform_env(provider: str, credentials: dict[str, Any]) -> dict[str, str]:
    """Map stored credentials to the environment variables each Terraform provider expects."""
    if provider == CloudProvider.AWS:
        env = {
            "AWS_ACCESS_KEY_ID": credentials.get("access_key_id", ""),
            "AWS_SECRET_ACCESS_KEY": credentials.get("secret_access_key", ""),
        }
        if credentials.get("session_token"):
            env["AWS_SESSION_TOKEN"] = credentials["session_token"]
        return env
    if provider == CloudProvider.AZURE:
        return {
            "ARM_TENANT_ID": credentials.get("tenant_id", ""),
            "ARM_CLIENT_ID": credentials.get("client_id", ""),
            "ARM_CLIENT_SECRET": credentials.get("client_secret", ""),
        }
    return {"GOOGLE_CREDENTIALS": credentials.get("service_account_json", "")}


class TerraformRunner:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    # -- capability detection ----------------------------------------------------------
    def binary_path(self) -> str | None:
        return shutil.which(self.settings.terraform_binary)

    def mock_reason(self) -> str | None:
        """Return why a mock plan is used, or None when real Terraform will run."""
        if self.settings.terraform_mode == "mock":
            return "TERRAFORM_MODE=mock"
        if self.settings.cloud_provider_mode != "real":
            return "CLOUD_PROVIDER_MODE=mock (no real credentials to plan against)"
        if not self.binary_path():
            return f"terraform binary '{self.settings.terraform_binary}' not found on PATH"
        return None

    def _workdir(self, run_id: str) -> Path:
        path = Path(self.settings.terraform_workdir).resolve() / run_id
        path.mkdir(parents=True, exist_ok=True)
        return path

    def _run(self, args: list[str], cwd: Path, env: dict[str, str]) -> str:
        binary = self.binary_path()
        if not binary:
            raise ProviderError("terraform binary not available")
        full_env = {**os.environ, "TF_IN_AUTOMATION": "1", "TF_INPUT": "0", **env}
        proc = subprocess.run(
            [binary, *args],
            cwd=cwd,
            env=full_env,
            capture_output=True,
            text=True,
            timeout=_TIMEOUT_SECONDS,
            check=False,
        )
        output = redact_text((proc.stdout or "") + (proc.stderr or ""))
        if proc.returncode != 0:
            logger.warning("terraform %s failed with exit code %s", args[0], proc.returncode)
            raise ProviderError(
                f"terraform {args[0]} failed (exit {proc.returncode})",
                details={"output": output[-4000:]},
            )
        return output

    # -- plan --------------------------------------------------------------------------
    def plan(
        self, run_id: str, hcl: str, action: str, env: dict[str, str] | None = None
    ) -> PlanResult:
        reason = self.mock_reason()
        if reason:
            return self.mock_plan(hcl, action, reason)
        workdir = self._workdir(run_id)
        (workdir / "main.tf").write_text(hcl, encoding="utf-8")
        env = env or {}
        init_out = self._run(["init", "-input=false", "-no-color"], workdir, env)
        plan_args = ["plan", "-input=false", "-no-color", "-out=tfplan"]
        if action == ProvisioningAction.DESTROY:
            plan_args.append("-destroy")
        plan_out = self._run(plan_args, workdir, env)
        match = _PLAN_SUMMARY_RE.search(plan_out)
        summary = (
            {"add": int(match[1]), "change": int(match[2]), "destroy": int(match[3])}
            if match
            else {"add": 0, "change": 0, "destroy": 0}
        )
        return PlanResult(
            output=f"{init_out}\n{plan_out}",
            summary=summary,
            is_mock=False,
            resources=[f"{t}.{n}" for t, n in _RESOURCE_RE.findall(hcl)],
        )

    @staticmethod
    def mock_plan(hcl: str, action: str, reason: str) -> PlanResult:
        blocks = _RESOURCE_RE.findall(hcl)
        destroying = action == ProvisioningAction.DESTROY
        symbol, verb = ("-", "destroyed") if destroying else ("+", "created")
        lines = [
            MOCK_BANNER,
            f"Reason: {reason}",
            "",
            "Resource actions are indicated with the following symbols:",
            f"  {symbol} {'destroy' if destroying else 'create'}",
            "",
            "Terraform will perform the following actions:",
            "",
        ]
        attrs_by_block = _attributes_by_block(hcl)
        for rtype, rname in blocks:
            lines.append(f"  # {rtype}.{rname} will be {verb}")
            lines.append(f'  {symbol} resource "{rtype}" "{rname}" {{')
            for key, value in attrs_by_block.get((rtype, rname), []):
                lines.append(f"      {symbol} {key:<24} = {value}")
            if not destroying:
                lines.append(f"      {symbol} {'id':<24} = (known after apply)")
            lines.append("    }")
            lines.append("")
        count = len(blocks)
        summary = {
            "add": 0 if destroying else count,
            "change": 0,
            "destroy": count if destroying else 0,
        }
        lines.append(
            f"Plan: {summary['add']} to add, {summary['change']} to change, "
            f"{summary['destroy']} to destroy."
        )
        return PlanResult(
            output="\n".join(lines),
            summary=summary,
            is_mock=True,
            resources=[f"{t}.{n}" for t, n in blocks],
        )

    # -- apply -------------------------------------------------------------------------
    def apply(self, run_id: str, env: dict[str, str] | None = None) -> str:
        if not self.settings.terraform_apply_enabled:
            raise BusinessRuleError(
                "Real terraform apply is disabled. Set TERRAFORM_APPLY_ENABLED=true to allow it."
            )
        workdir = self._workdir(run_id)
        if not (workdir / "tfplan").exists():
            raise BusinessRuleError("No saved plan found for this request; re-run the plan")
        # Applying a saved plan file never prompts and applies exactly what was reviewed.
        return self._run(["apply", "-input=false", "-no-color", "tfplan"], workdir, env or {})


def _attributes_by_block(hcl: str) -> dict[tuple[str, str], list[tuple[str, str]]]:
    result: dict[tuple[str, str], list[tuple[str, str]]] = {}
    current: tuple[str, str] | None = None
    for line in hcl.splitlines():
        header = _RESOURCE_RE.match(line)
        if header:
            current = (header[1], header[2])
            result[current] = []
            continue
        if current and line.startswith("}"):
            current = None
            continue
        if current:
            attr = _ATTR_RE.match(line)
            if attr and not attr[2].strip().startswith("{"):
                result[current].append((attr[1], attr[2].strip()))
    return result
