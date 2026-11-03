"""Small capability-checked adapter to the same registry used by HACS' add UI.

HACS exposes no stable integration API for this operation. Keep its internal
runtime calls here; never modify .storage files or bypass repository validation.
"""

from __future__ import annotations

import inspect
from dataclasses import dataclass, field


class HacsUnavailable(Exception):
    """HACS is absent, still starting, disabled or has an incompatible API."""


@dataclass
class RegistrationResult:
    added: list[str] = field(default_factory=list)
    existing: list[str] = field(default_factory=list)
    failed: dict[str, str] = field(default_factory=dict)


async def async_register_repositories(hass, catalog: list[dict]) -> RegistrationResult:
    """Register and persist repository metadata, without downloading components."""
    hacs = hass.data.get("hacs")
    if hacs is None:
        raise HacsUnavailable("HACS is not loaded")
    if getattr(getattr(hacs, "system", None), "disabled", False):
        raise HacsUnavailable("HACS is disabled")
    if getattr(getattr(hacs, "status", None), "startup", False):
        raise HacsUnavailable("HACS is still starting")
    register = getattr(hacs, "async_register_repository", None)
    lookup = getattr(getattr(hacs, "repositories", None), "get_by_full_name", None)
    save = getattr(getattr(hacs, "data", None), "async_write", None)
    categories = getattr(getattr(hacs, "common", None), "categories", ())
    if not callable(register) or not callable(lookup) or not callable(save) or "integration" not in categories:
        raise HacsUnavailable("This HACS version does not provide the expected registry API")
    try:
        inspect.signature(register).bind(
            repository_full_name="seb5594/example", category="integration", check=True,
        )
    except (TypeError, ValueError) as err:
        raise HacsUnavailable("The HACS repository registration API has changed") from err

    result = RegistrationResult()
    try:
        for item in catalog:
            repository = item["repository"]
            renamed = getattr(hacs.common, "renamed_repositories", {})
            lookup_name = renamed.get(repository, repository)
            if lookup(lookup_name) is not None:
                result.existing.append(repository)
                continue
            try:
                # Preserve HACS' skip/removed-repository policies, unlike the add UI
                # which clears skip on an explicit manual retry.
                errors = await register(
                    repository_full_name=repository, category="integration", check=True,
                )
                if lookup(lookup_name) is None:
                    result.failed[repository] = str(errors or "HACS did not register the repository")
                else:
                    result.added.append(repository)
            except Exception as err:
                result.failed[repository] = str(err)
    finally:
        # Persist successful additions even if another repository or task fails.
        if result.added:
            await save()
    return result
