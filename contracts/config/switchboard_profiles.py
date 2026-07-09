"""Schema for config/switchboard-profiles.yaml.

Validate-only: catches typos, wrong types, and negative budgets before a bad
edit reaches the running switchboard (hot-reload consults this). Does NOT
reshape — switchboard.py's _load_profile_catalog still consumes the raw doc.

null is meaningful here: it inherits the Python/env default (see the file's
_meta.note), so every tunable is Optional and null passes validation.
"""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

from . import register

_VALID_PROVIDERS = {"local", "remote", None}


class Profile(BaseModel):
    """One switchboard profile card. Unknown keys allowed (forward-compat)."""

    model_config = ConfigDict(extra="allow")

    forceProvider: Optional[str] = None
    injectHints: Optional[bool] = None
    modelAlias: Optional[str] = None
    advertisedContextWindow: Optional[int] = None
    maxInputTokens: Optional[int] = Field(default=None, ge=0)
    maxMessages: Optional[int] = Field(default=None, ge=0)
    maxOutputTokens: Optional[int] = Field(default=None, ge=0)
    embeddingsOnly: Optional[bool] = None
    toolExecution: Optional[str] = None
    ctxSize_min: Optional[int] = Field(default=None, ge=0)
    profileCard: Optional[str] = None

    @model_validator(mode="after")
    def _check_provider(self) -> "Profile":
        if self.forceProvider not in _VALID_PROVIDERS:
            raise ValueError(
                f"forceProvider must be one of {sorted(str(p) for p in _VALID_PROVIDERS)}, "
                f"got {self.forceProvider!r}"
            )
        return self


@register("config/switchboard-profiles.yaml")
class SwitchboardProfileCatalog(BaseModel):
    """Top-level catalog document. profiles is required; metadata keys allowed."""

    model_config = ConfigDict(extra="allow")

    profiles: dict[str, Profile]

    @model_validator(mode="before")
    @classmethod
    def _coerce(cls, data: Any) -> Any:
        # The YAML has _meta and _shared_bodies siblings of `profiles`; extra=allow
        # keeps them. Nothing to coerce, but guard against a non-dict root.
        if not isinstance(data, dict):
            raise ValueError("switchboard profile catalog root must be a mapping")
        return data

    @model_validator(mode="after")
    def _non_empty(self) -> "SwitchboardProfileCatalog":
        if not self.profiles:
            raise ValueError("catalog must define at least one profile")
        if "default" not in self.profiles:
            raise ValueError("catalog must define a 'default' profile")
        return self
