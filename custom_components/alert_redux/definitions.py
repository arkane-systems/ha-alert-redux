"""What an alert entity is built from (spec §12).

A fixed alert's definition comes straight from its subentry. A generated alert's
is made by its generator for one target (§12.3), and carries the extra template
variables that describe the target.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Any

from homeassistant.config_entries import ConfigSubentry


@dataclass(frozen=True, kw_only=True)
class AlertDefinition:
    """One alert's identity and configuration."""

    unique_id: str
    name: str
    # The alert's configuration, as a subentry stores it.
    data: Mapping[str, Any]
    # The generator's subentry ID, and the target's entity ID, for a generated
    # alert.
    generator: str | None = None
    target: str | None = None
    # Extra template variables, available to every template the alert renders.
    variables: Mapping[str, Any] = field(default_factory=dict)

    @property
    def target_key(self) -> str | None:
        """Return a generated alert's target key: what its generator knows its
        target by (spec §12.3)."""
        if self.generator is None:
            return None
        return self.unique_id.removeprefix(f"{self.generator}_")

    @classmethod
    def from_subentry(cls, subentry: ConfigSubentry) -> AlertDefinition:
        """Return a fixed alert's definition."""
        return cls(
            unique_id=subentry.subentry_id, name=subentry.title, data=subentry.data
        )


# Turns a generated alert's relationships to other generators into
# relationships to their alerts for the same target.
RelationshipResolver = Callable[
    [AlertDefinition, list[dict[str, Any]]], list[dict[str, Any]]
]


def generator_unique_id(generator: str) -> str:
    """Return a generator sensor's unique ID, from its subentry ID."""
    return f"generator_{generator}"
