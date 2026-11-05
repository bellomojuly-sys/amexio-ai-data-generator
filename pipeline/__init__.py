"""AMEXIO backend pipeline.

One Python service hosts the case model; each stage is a function with a typed
input and output, validated at the boundary (decision BE-01). Public surface:

    from pipeline import Analysis, CmIdOutput          # stage contracts (BE-03)
    from pipeline import LLMClient, FakeLLM, LLMError  # LLM interface (BE-04)
    from pipeline import run_chain, ChainError         # stub chain (BE-05)
    from pipeline import map_analysis                  # analysis -> ingest (BE-07)
"""

from .chain import ChainError, run_chain
from .contracts import Analysis, CmIdOutput
from .llm import FakeLLM, LLMClient, LLMError
from .mapping import map_analysis

__all__ = [
    "Analysis",
    "CmIdOutput",
    "LLMClient",
    "FakeLLM",
    "LLMError",
    "run_chain",
    "ChainError",
    "map_analysis",
]
