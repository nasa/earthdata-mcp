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

from ragas.llms import llm_factory
from ragas.embeddings.base import embedding_factory
from ragas.testset.graph import KnowledgeGraph, Node, NodeType
from ragas.testset.transforms import (
    apply_transforms,
    HeadlinesExtractor,
    HeadlineSplitter,
    KeyphrasesExtractor,
)
from ragas.testset.persona import Persona
from ragas.testset.synthesizers.single_hop.specific import (
    SingleHopSpecificQuerySynthesizer,
)
from ragas.testset import TestsetGenerator

from util.database import get_db_connection

# Load environment variables
load_dotenv()

# Configuration for AWS Bedrock
BEDROCK_CONFIG = {
    "region_name": "us-east-1",
    "llm": "amazon.nova-pro-v1:0",
    "embeddings": "amazon.titan-embed-text-v2:0",
    "temperature": 0.4,
}

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
            llm_model: Bedrock LLM model ID (defaults to Nova Pro)
            embedding_model: Bedrock embedding model ID (defaults to Titan)
            temperature: LLM temperature for generation
        """
        llm_model = llm_model or BEDROCK_CONFIG["llm"]
        embedding_model = embedding_model or BEDROCK_CONFIG["embeddings"]

        # Initialize LLM for generation
        self.generator_llm = llm_factory(
            f"bedrock/{llm_model}",
            provider="litellm",
            client=litellm.completion,
            temperature=temperature,
        )

        # Initialize embeddings
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

    def load_collections_from_db(
        self, limit: int = 100, query: Optional[str] = None
    ) -> List[dict]:
        """
        Load collection documents from PostgreSQL database

        Args:
            limit: Maximum number of collections to load
            query: Optional SQL WHERE clause to filter collections

        Returns:
            List of collection dictionaries with title and abstract
        """
        print(f"Loading {limit} collections from database...")

        collections = []
        conn = get_db_connection()

        try:
            with conn.cursor() as cur:
                # Query collections table
                sql = """
                    SELECT concept_id, metadata, enriched_metadata
                    FROM collections
                    ORDER BY concept_id
                    LIMIT %s
                """
                cur.execute(sql, (limit,))

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

                    # Extract title and abstract from metadata
                    title = metadata.get("ShortName", "")
                    if "EntryTitle" in metadata:
                        title = metadata["EntryTitle"]

                    # Try to get abstract from various metadata fields
                    abstract = metadata.get("Abstract", "")
                    if not abstract:
                        abstract = metadata.get("Summary", {}).get("Abstract", "")

                    # Use enriched metadata if available
                    if enriched:
                        title = enriched.get("title", title)
                        abstract = enriched.get("abstract", abstract)

                    if title and abstract:
                        collections.append(
                            {
                                "concept_id": concept_id,
                                "title": title,
                                "abstract": abstract,
                            }
                        )

            print(f"Loaded {len(collections)} collections from database")

        except Exception as e:
            print(f"Error loading collections from database: {e}")
            print("Falling back to placeholder data...")

            # Fallback to placeholder collections
            collections = [
                {
                    "concept_id": "C1234567890-ORNL_DAAC",
                    "title": "MODIS/Terra Sea Surface Temperature (SST) Daily L3 Global 4km",
                    "abstract": (
                        "This dataset provides daily sea surface temperature measurements "
                        "from the MODIS instrument aboard NASA's Terra satellite. Data is "
                        "provided at 4km spatial resolution globally. Temporal coverage spans "
                        "from 2000 to present, making it ideal for climate studies and ocean "
                        "monitoring applications."
                    ),
                },
                {
                    "concept_id": "C9876543210-LAADS",
                    "title": "VIIRS/NPP Land Surface Temperature Daily L3 Global 1km",
                    "abstract": (
                        "Daily land surface temperature from the Visible Infrared Imaging "
                        "Radiometer Suite (VIIRS) on the Suomi NPP satellite. The dataset "
                        "offers 1km resolution globally and includes quality flags. Data "
                        "available from 2012 onwards."
                    ),
                },
            ]

        finally:
            conn.close()

        return collections

    def load_collections_from_file(self, filepath: str) -> List[dict]:
        """
        Load collection documents from a JSON file

        Args:
            filepath: Path to JSON file containing collections

        Returns:
            List of collection dictionaries
        """
        with open(filepath, "r") as f:
            data = json.load(f)
            return data.get("collections", [])

    def create_knowledge_graph(self, collections: List[dict]) -> KnowledgeGraph:
        """
        Create a knowledge graph from collection documents

        Args:
            collections: List of collection dictionaries with title and abstract

        Returns:
            Knowledge graph with document nodes
        """
        print(f"Creating knowledge graph from {len(collections)} collections...")

        for collection in collections:
            # Create document content combining title and abstract
            page_content = f"# {collection['title']}\n\n{collection['abstract']}"

            # Create metadata
            metadata = {
                "concept_id": collection.get("concept_id", ""),
                "title": collection.get("title", ""),
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

    def apply_transforms(self):
        """
        Apply transforms to enrich the knowledge graph

        Transforms:
        - KeyphrasesExtractor: Extract key concepts and themes

        Note: HeadlinesExtractor and HeadlineSplitter are disabled due to
        compatibility issues with AWS Bedrock Nova model's structured output.
        """
        print("Applying transforms to knowledge graph...")

        headline_extractor = HeadlinesExtractor(llm=self.generator_llm, max_num=20)
        headline_splitter = HeadlineSplitter(max_tokens=1500)
        keyphrase_extractor = KeyphrasesExtractor(llm=self.generator_llm)

        transforms = [
            headline_extractor,
            headline_splitter,
            keyphrase_extractor,
        ]

        apply_transforms(self.kg, transforms=transforms)
        print("Transforms applied successfully")

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
        # Only using keyphrases since headlines are disabled
        query_distribution = [
            (
                SingleHopSpecificQuerySynthesizer(
                    llm=self.generator_llm, property_name="keyphrases"
                ),
                1.0,  # 100% keyphrase-based queries
            ),
        ]

        # Create test set generator
        generator = TestsetGenerator(
            llm=self.generator_llm,
            embedding_model=self.generator_embeddings,
            knowledge_graph=self.kg,
            persona_list=self.personas,
        )

        # Generate test set
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
        python test_set_generator.py
    """
    print("=" * 70)
    print("Earthdata MCP Test Set Generator")
    print("=" * 70)

    # Initialize generator
    generator = EarthdataTestSetGenerator()

    # Option 1: Load collections from database
    collections = generator.load_collections_from_db(limit=50)

    # Option 2: Load collections from file
    # collections = generator.load_collections_from_file("collections.json")

    # Create knowledge graph
    generator.create_knowledge_graph(collections)

    # Apply transforms to enrich the graph
    generator.apply_transforms()

    # Generate test set
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = f"evals/datasets/earthdata_synthetic_{timestamp}.json"

    test_data = generator.generate_testset(
        testset_size=20,  # Generate 20 test questions
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
