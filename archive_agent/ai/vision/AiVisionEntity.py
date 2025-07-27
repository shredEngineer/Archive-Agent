#  Copyright © 2025 Dr.-Ing. Paul Wilhelm <paul@wilhelm.dev>
#  This file is part of Archive Agent. See LICENSE for details.

from typing import Callable, Dict, List, Tuple

from archive_agent.ai.vision.AiVisionSchema import VisionSchema, Entity


class AiVisionRelation:
    """
    Registry for all canonical relation types and their human formatting.
    """
    _registry: Dict[str, Tuple[str, Callable[[Entity, Entity], str]]] = {}

    @classmethod
    def register(cls, predicate: str, description: str, formatter: Callable[[Entity, Entity], str]) -> None:
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
    def format(cls, predicate: str, subject: Entity, object_: Entity) -> str:
        """
        Format a relation using its formatter. Fallback to generic for unknown.
        """
        if predicate in cls._registry:
            _, fmt = cls._registry[predicate]
            return fmt(subject, object_)
        # Fallback: Graceful, readable, still parseable.
        return f"The {subject.name} ({subject.description}) {predicate.replace('_', ' ')} the {object_.name} ({object_.description})"

    @classmethod
    def for_prompt(cls) -> str:
        """
        Returns formatted lines for prompt inclusion, defining each relation.
        """
        lines = []
        for pred, (desc, fmt) in cls._registry.items():
            example = fmt(Entity(name="X", description="example X desc"), Entity(name="Y", description="example Y desc"))
            lines.append(f"- `{pred}`: {desc} (e.g., \"{example}\")")
        return "\n".join(lines)


# Initialize canonical relations

# Spatial relations
AiVisionRelation.register("left_of",
                          "X is visually to the left of Y.",
                          lambda s, o: f"The {s.name} ({s.description}) is positioned to the left of the {o.name} ({o.description})")
AiVisionRelation.register("right_of",
                          "X is visually to the right of Y.",
                          lambda s, o: f"The {s.name} ({s.description}) is positioned to the right of the {o.name} ({o.description})")
AiVisionRelation.register("above",
                          "X is visually above Y.",
                          lambda s, o: f"The {s.name} ({s.description}) is positioned above the {o.name} ({o.description})")
AiVisionRelation.register("below",
                          "X is visually below Y.",
                          lambda s, o: f"The {s.name} ({s.description}) is positioned below the {o.name} ({o.description})")
AiVisionRelation.register("inside",
                          "X is inside Y.",
                          lambda s, o: f"The {s.name} ({s.description}) is located within the {o.name} ({o.description})")
AiVisionRelation.register("contains",
                          "X contains Y.",
                          lambda s, o: f"The {s.name} ({s.description}) contains the {o.name} ({o.description})")
AiVisionRelation.register("on",
                          "X is on top of Y (e.g., resting or placed).",
                          lambda s, o: f"The {s.name} ({s.description}) is on the {o.name} ({o.description})")
AiVisionRelation.register("under",
                          "X is under Y.",
                          lambda s, o: f"The {s.name} ({s.description}) is under the {o.name} ({o.description})")
AiVisionRelation.register("behind",
                          "X is behind Y.",
                          lambda s, o: f"The {s.name} ({s.description}) is behind the {o.name} ({o.description})")
AiVisionRelation.register("in_front_of",
                          "X is in front of Y.",
                          lambda s, o: f"The {s.name} ({s.description}) is in front of the {o.name} ({o.description})")
AiVisionRelation.register("next_to",
                          "X is next to Y (adjacent).",
                          lambda s, o: f"The {s.name} ({s.description}) is next to the {o.name} ({o.description})")
AiVisionRelation.register("adjacent_to",
                          "X is adjacent to Y.",
                          lambda s, o: f"The {s.name} ({s.description}) is adjacent to the {o.name} ({o.description})")
AiVisionRelation.register("intersects",
                          "X intersects Y (e.g., overlapping or crossing).",
                          lambda s, o: f"The {s.name} ({s.description}) intersects the {o.name} ({o.description})")

# Structural relations
AiVisionRelation.register("part_of",
                          "X is a part of Y.",
                          lambda s, o: f"The {s.name} ({s.description}) is a component of the {o.name} ({o.description})")
AiVisionRelation.register("has_part",
                          "X has Y as a part.",
                          lambda s, o: f"The {s.name} ({s.description}) has the {o.name} ({o.description}) as a part")
AiVisionRelation.register("composed_of",
                          "X is composed of Y.",
                          lambda s, o: f"The {s.name} ({s.description}) is composed of the {o.name} ({o.description})")

# Semantic relations
AiVisionRelation.register("describes",
                          "X describes Y (e.g., text describes a figure or object).",
                          lambda s, o: f"The {s.name} ({s.description}) describes the entity {o.name} ({o.description})")
AiVisionRelation.register("references",
                          "X references Y (e.g., text or document refers to an entity).",
                          lambda s, o: f"The {s.name} ({s.description}) refers to the entity {o.name} ({o.description})")
AiVisionRelation.register("links_to",
                          "X is connected to Y in a visual or logical flow.",
                          lambda s, o: f"The {s.name} ({s.description}) is connected to the {o.name} ({o.description}) in a flow")
AiVisionRelation.register("has_attribute",
                          "X has the attribute Y (e.g., object has value, date, or property).",
                          lambda s, o: f"The {s.name} ({s.description}) has the attribute {o.name} ({o.description})")
AiVisionRelation.register("defines",
                          "X defines Y (e.g., term defines a concept).",
                          lambda s, o: f"The {s.name} ({s.description}) defines the concept of {o.name} ({o.description})")
AiVisionRelation.register("is_a",
                          "X is a type of Y (hierarchical classification).",
                          lambda s, o: f"The {s.name} ({s.description}) is a {o.name} ({o.description})")
AiVisionRelation.register("used_for",
                          "X is used for Y (functional relation).",
                          lambda s, o: f"The {s.name} ({s.description}) is used for {o.name} ({o.description})")
AiVisionRelation.register("similar_to",
                          "X is similar to Y.",
                          lambda s, o: f"The {s.name} ({s.description}) is similar to the {o.name} ({o.description})")
AiVisionRelation.register("holding",
                          "X is holding Y (interaction).",
                          lambda s, o: f"The {s.name} ({s.description}) is holding the {o.name} ({o.description})")
AiVisionRelation.register("wearing",
                          "X is wearing Y.",
                          lambda s, o: f"The {s.name} ({s.description}) is wearing the {o.name} ({o.description})")
AiVisionRelation.register("riding",
                          "X is riding Y.",
                          lambda s, o: f"The {s.name} ({s.description}) is riding the {o.name} ({o.description})")
AiVisionRelation.register("under_condition_of",
                          "X exists under the condition of Y.",
                          lambda s, o: f"The {s.name} ({s.description}) exists under the condition of {o.name} ({o.description})")


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
            "            Use descriptions to infer additional entities and relations where applicable",
            "            (e.g., 'divided into four sectors' suggests 'four sector lines' as an entity with 'contains' relation).",
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
            "    Examples: 'image is blank', 'image is too blurred to read', 'image file is corrupted'",
            "",
            "ADDITIONAL REQUIRED BLANK FIELDS:",
            "",
            "- `answer`: Empty string.",
            "",
            "EXTRACTION RULES:",
            "",
            "- ENTITY EXTRACTION:",
            "    - Identify all distinct, meaningful entities such as objects, people, concepts, key terms, text snippets, dates,",
            "      numbers, or visual elements like shapes, labels, or symbols.",
            "    - Decompose complex visuals into sub-entities where appropriate",
            "      (e.g., for a diagram, extract the overall shape, internal patterns, ",
            "       labels as separate entities if they add unique value).",
            "      Break down compound text phrases into granular parts",
            "      (e.g., main term and parentheticals) if they represent distinct ideas.",
            "    - Extract the maximum number of unique entities without fabrication, staying faithful to the image content.",
            "    - Use concise, unique names (e.g., 'Invoice #123' instead of 'Invoice', 'John Doe' for a person).",
            "    - For textual elements like labels or captions, explicitly mark them as such to distinguish them from actual objects",
            "      (e.g., 'label \"apple\"' instead of 'apple').",
            "    - Descriptions must be short, factual, and context-specific (e.g., 'date of invoice issuance' for '2023-10-15').",
            "    - Use descriptions to extract additional entities (e.g., 'divided into four sectors' implies 'four sector lines').",
            "    - Examples:",
            "        - For a dotted circle diagram, entities could include 'circle: enclosing boundary shape',",
            "         'dots: symmetrical point pattern inside circle', 'four sector lines: radiating lines'.",
            "        - For text '2D closed surface (sphere)', entities could include '2D closed surface: main phrase',",
            "          'sphere: parenthetical example'.",
            "",
            "- RELATION EXTRACTION:",
            "    - Identify all possible connections between entities, capturing their spatial, semantic, structural,",
            "      or contextual relationships.",
            "    - Prioritize spatial relations (e.g., 'above', 'below', 'inside') for visual layouts,",
            "      and use them exhaustively where evident (e.g., text below a diagram, elements inside a shape).",
            "      Infer hierarchies from groupings or flows.",
            "    - Extract the maximum number of meaningful relations without fabrication, staying faithful to the image content.",
            "    - From text: Parse sentences for subject-predicate-object structures, implied hierarchies, or references.",
            "    - From visuals: Use arrows, proximity, groupings, flows, or hierarchies to infer relations.",
            "    - Use entity descriptions to infer additional relations",
            "      (e.g., 'filled with a symmetrical dotted pattern' suggests 'contains symmetrical dotted pattern').",
            "    - Use relation types from the following list whenever possible.",
            "      If none fits, create a short, descriptive predicate matching existing styles",
            "      (e.g., 'under_condition_of' instead of 'for').",
            "    - Avoid overusing 'below'; prefer 'has_attribute' or 'under_condition_of' for textual conditions.",
            "    - Examples:",
            "        - For a circle with sectors, use 'circle contains four sector lines'.",
            "        - For text '2D closed surface (sphere)', use '2D closed surface has_attribute sphere'.",
            "",
            AiVisionRelation.for_prompt(),
            "",
            "IMPORTANT GLOBAL CONSTRAINTS:",
            "- Select the correct output behavior based solely on the visual characteristics of the image.",
            "- The `entities` and `relations` fields MUST strictly follow the rules above — no duplicates, no fabrication.",
            "- Every output unit MUST be clean, faithful to the image, and suitable for downstream semantic indexing.",
            "- Avoid vague predicates like 'related_to' unless no specific relation applies.",
            "- Ensure all entities are used in at least one relation, if possible, to maximize connectivity.",
            "- The chunked text output MUST be a single, cohesive sentence reflecting all entities and relations, joined with ', and ',",
            "  matching the format_vision_answer output.",
            "- Only set `is_rejected: true` if the image is technically unreadable or corrupted, and cannot be interpreted",
            "  meaningfully (e.g. blurred, distorted, broken file).",
            "- ALWAYS include the additional required blank `answer` field.",
            "",
            "Image input is provided separately."
        ])

    @staticmethod
    def format_vision_answer(vision_result: VisionSchema) -> str:
        """
        Format vision result as a single line compound sentence with ', and ' connectors for NLP compatibility.
        Each statement integrates entity descriptions directly into relations for concise output.
        :param vision_result: Vision result.
        :return: Formatted answer.
        """
        assert not vision_result.is_rejected

        entities = vision_result.entities
        entity_dict = {e.name: e for e in entities}  # Efficient lookup
        used_in_relation = set()
        statements = []

        # Format relations, integrating descriptions via formatters
        for r in vision_result.relations:
            subject = entity_dict.get(r.subject)
            object_ = entity_dict.get(r.object)
            if subject and object_:
                statement = AiVisionRelation.format(r.predicate, subject, object_)
                statements.append(statement)
                used_in_relation.add(r.subject)
                used_in_relation.add(r.object)

        # Include unused entities as standalone clauses
        for e in entities:
            if e.name not in used_in_relation:
                statements.append(f"there is the {e.name} ({e.description})")

        # Fallback for no relations
        if not statements:
            return "No meaningful information was extracted from the image."

        # Join into a single compound sentence: Capitalize first, lowercase starting letter of others, connect with ', and '
        first_statement = statements[0].capitalize()
        remaining_statements = []
        for s in statements[1:]:
            if s:
                remaining_statements.append(s[0].lower() + s[1:])
        joined = ", and ".join([first_statement] + remaining_statements) + "."
        return joined
