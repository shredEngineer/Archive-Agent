#  Copyright © 2025 Dr.-Ing. Paul Wilhelm <paul@wilhelm.dev>
#  This file is part of Archive Agent. See LICENSE for details.

import logging
from typing import Callable, Dict, List, Tuple

logger = logging.getLogger(__name__)


class AiVisionRelation:
    """
    Registry for all canonical relation types and their human formatting.
    """
    _registry: Dict[str, Tuple[str, Callable[[str, str], str]]] = {}

    @classmethod
    def register(cls, predicate: str, description: str, formatter: Callable[[str, str], str]) -> None:
        """
        Register a relation type with its description and formatter.
        """
        cls._registry[predicate] = (description, formatter)

    @classmethod
    def all_predicates(cls) -> List[str]:
        """
        Return all registered relation type keys.
        """
        return list(cls._registry.keys())

    @classmethod
    def format(cls, predicate: str, subject: str, object_: str) -> str:
        """
        Format a relation using its formatter. Fallback to generic for unknown.
        """
        if predicate in cls._registry:
            _, fmt = cls._registry[predicate]
            return fmt(subject, object_)
        # Fallback: Graceful, readable, still parseable.
        return f"The {subject} {predicate.replace('_', ' ')} the {object_}."

    @classmethod
    def for_prompt(cls) -> str:
        """
        Returns formatted lines for prompt inclusion, defining each relation.
        """
        lines = []
        for pred, (desc, fmt) in cls._registry.items():
            example = fmt("X", "Y")
            lines.append(f"- `{pred}`: {desc} (e.g., \"{example}\")")
        return "\n".join(lines)


# Initialize canonical relations
AiVisionRelation.register("left_of",
                          "X is visually to the left of Y.",
                          lambda s, o: f"The {s} is positioned to the left of the {o}.")
AiVisionRelation.register("right_of",
                          "X is visually to the right of Y.",
                          lambda s, o: f"The {s} is positioned to the right of the {o}.")
AiVisionRelation.register("above",
                          "X is visually above Y.",
                          lambda s, o: f"The {s} is positioned above the {o}.")
AiVisionRelation.register("below",
                          "X is visually below Y.",
                          lambda s, o: f"The {s} is positioned below the {o}.")
AiVisionRelation.register("inside",
                          "X is inside Y.",
                          lambda s, o: f"The {s} is located within the {o}.")
AiVisionRelation.register("contains",
                          "X contains Y.",
                          lambda s, o: f"The {s} contains the {o}.")
AiVisionRelation.register("part_of",
                          "X is a part of Y.",
                          lambda s, o: f"The {s} is a component of the {o}.")
AiVisionRelation.register("describes",
                          "X describes Y (e.g., text describes a figure or object).",
                          lambda s, o: f"The {s} describes the entity {o}.")
AiVisionRelation.register("references",
                          "X references Y (e.g., text or document refers to an entity).",
                          lambda s, o: f"The {s} refers to the entity {o}.")
AiVisionRelation.register("links_to",
                          "X is connected to Y in a visual or logical flow.",
                          lambda s, o: f"The {s} is connected to the {o} in a flow.")
AiVisionRelation.register("has_attribute",
                          "X has the attribute Y (e.g., object has value, date, or property).",
                          lambda s, o: f"The {s} has the attribute {o}.")
AiVisionRelation.register("defines",
                          "X defines Y (e.g., term defines a concept).",
                          lambda s, o: f"The {s} defines the concept of {o}.")
