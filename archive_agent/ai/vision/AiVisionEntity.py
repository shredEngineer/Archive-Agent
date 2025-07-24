#  Copyright © 2025 Dr.-Ing. Paul Wilhelm <paul@wilhelm.dev>
#  This file is part of Archive Agent. See LICENSE for details.

import logging
from typing import Callable, Dict, List, Tuple

from archive_agent.ai.vision.AiVisionSchema import VisionSchema

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


class AiVisionEntity:

    @staticmethod
    def get_prompt_vision() -> str:
        return "\n".join([
            "Act as a vision agent for a semantic retrieval system (Retrieval-Augmented Generation / RAG).",
            "Your task is to extract clean, modular, maximally relevant units of visual information from an image.",
            "You must output structured information using the exact response fields described below.",
            "Do not return any explanations, commentary, or additional fields.",
            "",
            "RESPONSE FIELDS:",
            "",
            "- `entities`:",
            "    A list of entities extracted from the image. Extract the maximum number of unique entities possible.",
            "    Each entity has these fields:",
            "        - `name`:",
            "            The name, label, or primary identifier of the entity.",
            "        - `description`:",
            "            A short, factual description of the entity, faithful to the image. For formulas, use LaTeX enclosed in $...$.",
            "",
            "- `relations`:",
            "    A list of relations connecting entities. Extract the maximum number of meaningful relations possible.",
            "    Each relation has these fields:",
            "        - `subject`:",
            "            The name of the subject entity.",
            "        - `predicate`:",
            "            The relation type, as defined below.",
            "        - `object`:",
            "            The name of the object entity.",
            "",
            "- `is_rejected`:",
            "    A Boolean flag. Set `is_rejected: true` ONLY if the image is unreadable or corrupted",
            "    and cannot be meaningfully processed.",
            "    If `is_rejected` is true, set `entities: []`, `relations: []` and populate `rejection_reason`.",
            "",
            "- `rejection_reason`:",
            "    A short, factual reason for rejection.",
            "    Required ONLY if `is_rejected` is `true`. Leave this field blank if `is_rejected` is `false`.",
            "    Examples: 'image is too blurred to read', 'image file is corrupted'",
            "",
            "ADDITIONAL REQUIRED BLANK FIELDS:"
            "",
            "- `answer`: Empty string."
            "",
            "EXTRACTION RULES:",
            "",
            "- ENTITY EXTRACTION:",
            "    - Identify all distinct, meaningful entities such as objects, people, concepts, key terms, text snippets, dates,",
            "      numbers, or visual elements like shapes, labels, or symbols.",
            "    - Extract the maximum number of unique entities without fabrication, staying faithful to the image content.",
            "    - Use concise, unique names (e.g., 'Invoice #123' instead of 'Invoice', 'John Doe' for a person).",
            "    - For textual elements like labels or captions, explicitly mark them as such to distinguish them from actual objects",
            "      (e.g., 'label \"apple\"' instead of 'apple').",
            "    - Descriptions must be short, factual, and context-specific (e.g., 'date of invoice issuance' for '2023-10-15').",
            "",
            "- RELATION EXTRACTION:",
            "    - Identify all possible connections between entities, capturing their spatial, semantic, structural,",
            "      or contextual relationships.",
            "    - Extract the maximum number of meaningful relations without fabrication, staying faithful to the image content.",
            "    - From text: Parse sentences for subject-predicate-object structures, implied hierarchies, or references.",
            "    - From visuals: Use arrows, proximity, groupings, flows, or hierarchies to infer relations.",
            "    - Use only relation types from the following list whenever possible. If none fits, create a short, descriptive predicate:",
            "",
            AiVisionRelation.for_prompt(),
            "",
            "IMPORTANT GLOBAL CONSTRAINTS:",
            "- Select the correct output behavior based solely on the visual characteristics of the image.",
            "- The `entities` and `relations` fields MUST strictly follow the rules above — no duplicates, no fabrication.",
            "- Every output unit MUST be clean, faithful to the image, and suitable for downstream semantic indexing.",
            "- Avoid vague predicates like 'related_to' unless no specific relation applies.",
            "- Ensure all entities are used in at least one relation, if possible, to maximize connectivity.",
            "- Only set `is_rejected: true` if the image is technically unreadable or corrupted, and cannot be interpreted",
            "  meaningfully (e.g. blurred, distorted, broken file).",
            "- ALWAYS include the additional required blank `answer` field.",
            "",
            "Image input is provided separately."
        ])

    @staticmethod
    def format_vision_answer(vision_result: VisionSchema) -> str:
        """
        Format vision result as single line (without linebreaks — required for downstream logic).
        Each statement is explicit, self-contained, and optimized for RAG embedding.
        Relations are formatted first, followed by descriptions for entities not used in relations.
        """
        assert not vision_result.is_rejected

        entities = vision_result.entities
        used_in_relation = set()
        statements = []

        # Format relations as explicit, atomic sentences
        for r in vision_result.relations:
            statement = AiVisionRelation.format(r.predicate, r.subject, r.object)
            statements.append(statement)
            used_in_relation.add(r.subject)
            used_in_relation.add(r.object)

        # Add descriptions only for entities not used in any relation
        for e in entities:
            if e.name not in used_in_relation:
                logger.warning(f"Entity '{e.name}' not included in any relation.")
                desc = e.description.strip().rstrip('.')
                if desc:
                    statements.append(f"The {e.name} is described as {desc.lower()}.")

        # Fallback for no relations
        if not statements:
            statements.append("No meaningful information was extracted from the image.")

        # Join into a single line
        return " ".join(statement.rstrip('.') + "." for statement in statements if statement.strip())
