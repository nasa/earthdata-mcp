# RAG Evaluation

Evaluate a RAG (Retrieval Augmented Generation) system with custom metrics using AWS Bedrock and Ragas.

## Quick Start

### 1. Configure AWS Credentials

The evaluation uses AWS Bedrock for LLM and embeddings:

```bash
# Set AWS credentials
export AWS_DEFAULT_REGION="us-east-1"
export AWS_ACCESS_KEY_ID="your-access-key"
export AWS_SECRET_ACCESS_KEY="your-secret-key"

# Or use AWS profile
export AWS_PROFILE="your-profile"
```

### 2. Install Dependencies

Using `uv` (recommended):

```bash
uv sync
```

Or using `pip`:

```bash
pip install -e .
```

### 3. Run the Evaluation

Using `uv`:

```bash
uv run python evals.py
```

Or using `pip`:

```bash
python evals.py
```

## Customization

### Modify the LLM Provider

The evaluation stack currently initializes its shared LLM and embedding clients in `SingleEvaluation._initialize_components()` inside [evals.py](evals.py).

### Customize Test Cases

Edit the dataset loading in [evals.py](evals.py) to add or modify test cases.

### Change Evaluation Metrics

Update the evaluator configuration in [evals.py](evals.py) to use different Ragas metrics.

## Documentation

Visit https://docs.ragas.io for more information.
