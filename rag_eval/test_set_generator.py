"""
Test Set Generator for Earthdata MCP RAG System

Generates synthetic test questions from NASA CMR collection data using Ragas.
Follows the pattern from: https://docs.ragas.io/en/stable/howtos/applications/singlehop_testset_gen/

Steps:
1. Load collection documents from database
2. Create knowledge graph
3. Apply transforms (headlines, splitting, keyphrases)
4. Define personas (scientist, student, data analyst)
5. Configure query synthesizers
6. Generate test set
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from dotenv import load_dotenv
import litellm
from openai import OpenAI

from ragas.llms import llm_factory
from ragas.embeddings.base import embedding_factory
from ragas.testset.graph import KnowledgeGraph, Node, NodeType
from ragas.testset.transforms import (
    apply_transforms,
    HeadlinesExtractor,
    HeadlineSplitter,
    KeyphrasesExtractor,
    Parallel,
)
from ragas.testset.transforms.extractors import TopicDescriptionExtractor

# from ragas.testset.transforms.extractors import NERExtractor
from ragas.testset.transforms.relationship_builders.traditional import (
    JaccardSimilarityBuilder,
)
from ragas.testset.persona import Persona
from ragas.testset.synthesizers.single_hop.specific import (
    SingleHopSpecificQuerySynthesizer,
)
from ragas.testset import TestsetGenerator

from util.database import get_db_connection

# Load environment variables
load_dotenv()

# Configuration for AWS Bedrock (DEFAULT - has structured output issues with Nova)
BEDROCK_CONFIG = {
    "region_name": "us-east-1",
    "llm": "amazon.nova-pro-v1:0",
    "embeddings": "amazon.titan-embed-text-v2:0",
    "temperature": 0.4,
}

# Configuration for OpenAI (ALTERNATIVE - better structured output support)
OPENAI_CONFIG = {
    "llm": "claude-4.5-sonnet",  # Using NASA API Portal with Claude (matches Continue config)
    "embeddings": "text-embedding-3-small",
    "temperature": 0.4,
    "base_url": os.getenv("OPENAI_BASE_URL"),  # Must include /v1 suffix
}

# Choose which provider to use
USE_OPENAI = os.getenv("USE_OPENAI", "false").lower() == "true"

if USE_OPENAI:
    print("🔧 Using OpenAI models")
    if not os.getenv("OPENAI_API_KEY"):
        print("❌ Error: OPENAI_API_KEY environment variable is not set.")
        print("Please set your OpenAI API key:")
        print("export OPENAI_API_KEY='your_openai_api_key'")
        exit(1)
else:
    print("🔧 Using AWS Bedrock models")
    # Set AWS region
    os.environ["AWS_REGION_NAME"] = BEDROCK_CONFIG["region_name"]


class EarthdataTestSetGenerator:
    """Generate synthetic test sets for Earthdata MCP RAG evaluation"""

    def __init__(
        self,
        llm_model: Optional[str] = None,
        embedding_model: Optional[str] = None,
        temperature: float = 0.4,
    ):
        """
        Initialize the test set generator

        Args:
            llm_model: LLM model ID (defaults to Nova Pro or GPT-4o depending on USE_OPENAI)
            embedding_model: Embedding model ID (defaults to Titan or OpenAI depending on USE_OPENAI)
            temperature: LLM temperature for generation
        """
        if USE_OPENAI:
            # OpenAI configuration (or OpenAI-compatible API like NASA API Portal)
            llm_model = llm_model or OPENAI_CONFIG["llm"]
            embedding_model = embedding_model or OPENAI_CONFIG["embeddings"]
            base_url = OPENAI_CONFIG.get("base_url")

            # Create OpenAI client instance (required by ragas llm_factory)
            openai_client = OpenAI(
                api_key=os.getenv("OPENAI_API_KEY"),
                base_url=base_url,
            )

            # Initialize OpenAI-compatible LLM with client
            # Note: When using custom client, pass model name without provider prefix
            self.generator_llm = llm_factory(
                llm_model,  # Just model name, not "openai/model"
                client=openai_client,
                temperature=temperature,
            )

            # Initialize OpenAI embeddings
            # Note: embeddings may need to use standard OpenAI endpoint even with custom base_url for LLM
            self.generator_embeddings = embedding_factory(
                "openai",
                model=embedding_model,
            )
        else:
            # AWS Bedrock configuration
            llm_model = llm_model or BEDROCK_CONFIG["llm"]
            embedding_model = embedding_model or BEDROCK_CONFIG["embeddings"]

            # Initialize Bedrock LLM
            self.generator_llm = llm_factory(
                f"bedrock/{llm_model}",
                provider="litellm",
                client=litellm.completion,
                temperature=temperature,
            )

            # Initialize Bedrock embeddings
            self.generator_embeddings = embedding_factory(
                "litellm",
                model=f"bedrock/{embedding_model}",
            )

        # Initialize knowledge graph
        self.kg = KnowledgeGraph()

        # Define personas for diverse query generation
        self.personas = self._create_personas()

    def _create_personas(self) -> List[Persona]:
        """
        Create personas representing different types of users

        Returns:
            List of Persona objects
        """
        personas = [
            Persona(
                name="Earth Science Researcher",
                role_description=(
                    "A climate scientist conducting research on Earth's natural systems and environmental changes. "
                    "Uses NASA satellite data to observe and analyze phenomena like sea ice melt, coral reef health, "
                    "ocean temperature changes, forest deforestation, and biodiversity loss. Needs datasets with "
                    "high temporal frequency, long-term records, and precise spatial resolution to identify trends "
                    "and validate climate models. Values comprehensive metadata, peer-reviewed data quality, and "
                    "datasets that enable cross-comparison with other measurements."
                ),
            ),
            Persona(
                name="Agricultural Manager",
                role_description=(
                    "A farmer or agricultural professional managing large-scale crop production and livestock operations. "
                    "Relies on NASA Earth observation data to monitor crop health, soil moisture, vegetation indices, "
                    "pest infestations, and weather patterns across hundreds or thousands of acres. Needs practical, "
                    "actionable data with frequent updates to make timely decisions about irrigation, fertilization, "
                    "and harvest timing. Interested in accessible datasets that integrate easily with farm management "
                    "systems and provide near-real-time monitoring capabilities."
                ),
            ),
            Persona(
                name="Climate Impact Student",
                role_description=(
                    "A graduate student or early-career researcher studying the impacts of climate change and natural "
                    "disasters. Focuses on greenhouse gas emissions, wildfire progression, flood extent mapping, "
                    "extreme weather events, and their effects on communities and ecosystems. Needs clear documentation, "
                    "educational resources, and datasets that are well-suited for learning Earth observation analysis "
                    "techniques. Values datasets with good tutorials, example applications, and active user communities "
                    "for support."
                ),
            ),
            Persona(
                name="Risk Assessment Planner",
                role_description=(
                    "A land use planner, insurance analyst, or government official responsible for assessing environmental "
                    "risks and making data-driven policy decisions. Uses historical NASA Earth data to evaluate flood risk, "
                    "wildfire susceptibility, coastal erosion, landslide potential, and other hazards for specific geographic "
                    "areas. Needs authoritative, well-documented datasets with long temporal records to establish baseline "
                    "conditions and identify risk patterns. Values datasets that can be integrated into GIS systems, risk "
                    "models, and regulatory compliance frameworks. Requires clear provenance and quality indicators for "
                    "defensible decision-making."
                ),
            ),
        ]
        return personas

    def load_all_entities_from_db(self, limit_per_type: int = 50) -> List[dict]:
        """
        Load ALL searchable entities from PostgreSQL database.

        This includes collections, variables, citations, instruments, and keywords
        to match what the RAG system actually searches. This ensures test questions
        reflect real user queries across all entity types.

        Args:
            limit_per_type: Maximum number of entities per type to load

        Returns:
            List of entity dictionaries with title/content
        """
        print(f"Loading entities from database (up to {limit_per_type} per type)...")

        entities = []
        conn = get_db_connection()

        try:
            with conn.cursor() as cur:
                # Query 1: Collections (from collections table with enriched metadata)
                cur.execute(
                    """
                    SELECT concept_id, metadata, enriched_metadata
                    FROM collections
                    ORDER BY concept_id
                    LIMIT %s
                """,
                    (limit_per_type,),
                )

                for row in cur.fetchall():
                    concept_id = row[0]
                    metadata = (
                        row[1] if isinstance(row[1], dict) else json.loads(row[1])
                    )
                    enriched = (
                        row[2]
                        if isinstance(row[2], dict)
                        else json.loads(row[2] or "{}")
                    )

                    title = (
                        enriched.get("title")
                        or metadata.get("EntryTitle")
                        or metadata.get("ShortName", "")
                    )
                    abstract = enriched.get("abstract") or metadata.get("Abstract", "")

                    if title and abstract:
                        entities.append(
                            {
                                "id": concept_id,
                                "type": "collection",
                                "title": title,
                                "content": abstract,
                            }
                        )

                # Query 2: All other entity types from embeddings table
                # This matches what search_all_entity_types() queries
                # Note: Multiple rows per entity (title, abstract, etc.) so we limit total rows
                cur.execute(
                    """
                    SELECT type, external_id, attribute, text_content
                    FROM embeddings
                    WHERE type IN ('variable', 'citation', 'instruments', 'platforms', 'sciencekeywords')
                    ORDER BY type, external_id, attribute
                    LIMIT %s
                """,
                    (
                        limit_per_type * 10,
                    ),  # Multiply to account for multiple rows per entity
                )

                # Group rows by (type, external_id) since title and abstract are in different rows
                entity_map = {}
                for row in cur.fetchall():
                    entity_type = row[0]
                    external_id = row[1]
                    attribute = row[2]
                    text_content = row[3]

                    key = (entity_type, external_id)
                    if key not in entity_map:
                        entity_map[key] = {
                            "type": entity_type,
                            "id": external_id,
                            "attributes": {},
                        }

                    if text_content:
                        entity_map[key]["attributes"][attribute] = text_content

                # Convert grouped entities to list format
                for (entity_type, external_id), data in entity_map.items():
                    attrs = data["attributes"]

                    # Try to get title from 'title' attribute, fallback to first available
                    title = (
                        attrs.get("title")
                        or attrs.get("name")
                        or next(iter(attrs.values()), "")[:100]
                    )

                    # Try to get content from 'abstract' attribute, fallback to combining all attributes
                    content = attrs.get("abstract") or attrs.get("description")
                    if not content:
                        # Combine all attributes as content if no abstract
                        content = "\n\n".join(
                            f"{k}: {v}" for k, v in attrs.items() if k != "title"
                        )

                    if title and content:
                        entities.append(
                            {
                                "id": external_id,
                                "type": entity_type,
                                "title": title,
                                "content": content,
                            }
                        )

            print(f"Loaded {len(entities)} total entities from database")

            # Print breakdown by type
            type_counts = {}
            for e in entities:
                t = e["type"]
                type_counts[t] = type_counts.get(t, 0) + 1
            print(f"Entity breakdown: {type_counts}")

        except Exception as e:
            print(f"Error loading entities from database: {e}")
            print("Falling back to placeholder data...")

            # Fallback to placeholder data
            entities = [
                {
                    "id": "C1234567890-ORNL_DAAC",
                    "type": "collection",
                    "title": "MODIS/Terra Sea Surface Temperature (SST) Daily L3 Global 4km",
                    "content": (
                        "This dataset provides daily sea surface temperature measurements "
                        "from the MODIS instrument aboard NASA's Terra satellite. Data is "
                        "provided at 4km spatial resolution globally. Temporal coverage spans "
                        "from 2000 to present, making it ideal for climate studies and ocean "
                        "monitoring applications."
                    ),
                },
                {
                    "id": "V1234567890-VARIABLE",
                    "type": "variable",
                    "title": "Sea Surface Temperature",
                    "content": "Sea surface temperature measured in Celsius from satellite thermal infrared sensors.",
                },
            ]

        finally:
            conn.close()

        return entities

    def create_knowledge_graph(self, entities: List[dict]) -> KnowledgeGraph:
        """
        Create a knowledge graph from all entity types

        Args:
            entities: List of entity dictionaries with id, type, title, content

        Returns:
            Knowledge graph with document nodes for all entities
        """
        print(f"Creating knowledge graph from {len(entities)} entities...")

        for entity in entities:
            # Create document content combining title and content
            page_content = f"# {entity['title']}\n\n{entity['content']}"

            # Create metadata
            metadata = {
                "id": entity.get("id", ""),
                "type": entity.get("type", ""),
                "title": entity.get("title", ""),
                "source": "cmr",
            }

            # Add node to knowledge graph
            self.kg.nodes.append(
                Node(
                    type=NodeType.DOCUMENT,
                    properties={
                        "page_content": page_content,
                        "document_metadata": metadata,
                    },
                )
            )

        print(f"Knowledge graph created: {self.kg}")
        return self.kg

    def enrich_knowledge_graph(self):
        """
        Apply transforms to enrich the knowledge graph and build relationships

        This follows the Ragas knowledge graph approach:
        1. Extract information from nodes (entities, keyphrases)
        2. Build relationships between nodes based on extracted properties

        The relationship building enables multi-hop query generation by connecting
        related documents through shared entities and concepts.

        Note: HeadlinesExtractor and HeadlineSplitter are disabled due to
        compatibility issues with AWS Bedrock Nova model's structured output.
        """
        print("Enriching knowledge graph with extractors and relationship builders...")

        # Step 1: Extract information from nodes
        # These extractors add properties to nodes that can be used for relationship building
        headline_extractor = HeadlinesExtractor(llm=self.generator_llm, max_num=20)
        headline_splitter = HeadlineSplitter(max_tokens=1500)
        topic_extractor = TopicDescriptionExtractor(llm=self.generator_llm)
        # ner_extractor = NERExtractor(llm=self.generator_llm)
        keyphrase_extractor = KeyphrasesExtractor(llm=self.generator_llm)

        # Step 2: Build relationships between nodes based on extracted properties
        # This establishes connections between documents that share similar entities/concepts
        topic_similarity_builder = JaccardSimilarityBuilder(
            property_name="topic_description",
            new_property_name="entity_jaccard_similarity",
            threshold=0.1,  # Minimum similarity threshold (0.1 = 10% overlap)
        )

        keyphrase_similarity_builder = JaccardSimilarityBuilder(
            property_name="keyphrases",
            new_property_name="keyphrase_similarity",
            threshold=0.1,
        )

        transforms = [
            # headline_extractor,  # DISABLED: Nova returns {} instead of required JSON
            # headline_splitter,
            Parallel(
                topic_extractor,  # Testing TopicDescriptionExtractor
                # ner_extractor,  # Alternative: NERExtractor
                # keyphrase_extractor,  # DISABLED: Nova structured output issue
            ),
            # keyphrase_extractor,  # DISABLED: Causes validation error - Nova returns {}
            # topic_extractor,  # DISABLED: Using TopicDescriptionExtractor instead of NER
            # ner_extractor,  # DISABLED: Nova structured output issue
            topic_similarity_builder,  # DISABLED: Needs entities from NERExtractor
            # keyphrase_similarity_builder,
        ]

        apply_transforms(self.kg, transforms=transforms)

        # Print statistics about the enriched graph
        num_nodes = len(self.kg.nodes)
        num_relationships = len(self.kg.relationships)
        print(f"✓ Knowledge graph enriched:")
        print(f"  - {num_nodes} nodes")
        print(f"  - {num_relationships} relationships established")

        if num_relationships > 0:
            print(f"  - Enables multi-hop query generation across connected documents")

    def generate_testset(
        self,
        testset_size: int = 10,
        output_path: Optional[str] = None,
    ) -> dict:
        """
        Generate synthetic test set using Ragas

        Args:
            testset_size: Number of test questions to generate
            output_path: Optional path to save the test set JSON

        Returns:
            Dictionary containing the test set
        """
        print(f"Generating test set with {testset_size} questions...")

        # Configure query distribution using synthesizers
        # SingleHopSpecificQuerySynthesizer generates specific questions based on node properties
        query_distribution = [
            (
                SingleHopSpecificQuerySynthesizer(
                    llm=self.generator_llm,
                    property_name="page_content",  # Use page_content which exists on all nodes
                ),
                1.0,  # 100% single-hop specific queries
            ),
        ]

        # Create test set generator
        generator = TestsetGenerator(
            llm=self.generator_llm,
            embedding_model=self.generator_embeddings,
            knowledge_graph=self.kg,
            persona_list=self.personas,
        )

        # Generate test set using generate_samples instead of generate
        print("Generating scenarios and samples...")
        testset = generator.generate(
            testset_size=testset_size,
            query_distribution=query_distribution,
        )

        # Convert to pandas DataFrame
        df = testset.to_pandas()
        print(f"\nGenerated {len(df)} test questions:")
        print(df[["user_input", "synthesizer_name"]].head())

        # Convert to our standard format
        test_data = {
            "version": "1.0",
            "generated_at": datetime.now().isoformat(),
            "generator": "ragas-bedrock-nova",
            "config": {
                "llm_model": BEDROCK_CONFIG["llm"],
                "embedding_model": BEDROCK_CONFIG["embeddings"],
                "testset_size": testset_size,
                "num_personas": len(self.personas),
            },
            "test_cases": [],
        }

        # Convert each row to test case format
        for idx, row in df.iterrows():
            test_case = {
                "question_id": f"q{idx+1:03d}",
                "question": row["user_input"],
                "reference_contexts": row["reference_contexts"],
                "reference": row.get("reference", ""),
                "synthesizer": row["synthesizer_name"],
                "query_type": "semantic",  # All are semantic searches for CMR
            }
            test_data["test_cases"].append(test_case)

        # Save to file if path provided
        if output_path:
            output_file = Path(output_path)
            output_file.parent.mkdir(parents=True, exist_ok=True)

            with open(output_file, "w") as f:
                json.dump(test_data, f, indent=2)

            print(f"\nTest set saved to: {output_file.resolve()}")

        return test_data


def main():
    """
    Main function to generate test set

    Usage:
        # Using AWS Bedrock (default):
        python test_set_generator.py

        # Using OpenAI (set environment variable):
        export USE_OPENAI=true
        export OPENAI_API_KEY='your-api-key'
        python test_set_generator.py
    """
    print("=" * 70)
    print("Earthdata MCP Test Set Generator")
    print("=" * 70)

    if USE_OPENAI:
        print(f"Provider: OpenAI")
        print(f"LLM: {OPENAI_CONFIG['llm']}")
        print(f"Embeddings: {OPENAI_CONFIG['embeddings']}")
    else:
        print(f"Provider: AWS Bedrock")
        print(f"LLM: {BEDROCK_CONFIG['llm']}")
        print(f"Embeddings: {BEDROCK_CONFIG['embeddings']}")
    print("=" * 70)

    # Initialize generator
    generator = EarthdataTestSetGenerator(temperature=0.01)

    # Load all entity types from database (collections, variables, keywords, etc.)
    entities = generator.load_all_entities_from_db(limit_per_type=5)

    # Create knowledge graph
    generator.create_knowledge_graph(entities)

    # Apply transforms to enrich the graph
    generator.enrich_knowledge_graph()

    # Generate test set
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = f"evals/datasets/earthdata_synthetic_{timestamp}.json"

    test_data = generator.generate_testset(
        testset_size=5,  # Generate 20 test questions
        output_path=output_path,
    )

    print("\n" + "=" * 70)
    print("✓ Test set generation complete!")
    print("=" * 70)
    print(f"\nGenerated {len(test_data['test_cases'])} test questions")
    print(f"Output: {output_path}")

    # Print sample questions
    print("\nSample questions:")
    for i, test_case in enumerate(test_data["test_cases"][:3], 1):
        print(f"\n{i}. {test_case['question']}")


if __name__ == "__main__":
    main()
