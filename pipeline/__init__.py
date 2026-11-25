"""AMEXIO backend pipeline (pipeline contract v1.1).

One Python service hosts the case model; each step is a function with a typed
input and output, validated at the boundary (decision BE-01). Public surface:

    from pipeline import RunRequest, RunResult, run_chain, ChainError   # the chain (§3)
    from pipeline import LLMClient, BaseLLMClient, FakeLLM, LLMError    # LLM client (§8)
    from pipeline import AnthropicLLM, ProviderError, create_llm        # real provider (§8)
    from pipeline import Analysis, map_analysis                         # seed employees (§3, BE-07)
"""

from .chain import ChainError, run_chain
from .contracts import Analysis, CmIdOutput, RunRequest, RunResult
from .llm import AnthropicLLM, BaseLLMClient, FakeLLM, LLMClient, LLMError, ProviderError, create_llm
from .mapping import map_analysis

__all__ = [
    "Analysis",
    "CmIdOutput",
    "RunRequest",
    "RunResult",
    "LLMClient",
    "BaseLLMClient",
    "FakeLLM",
    "LLMError",
    "AnthropicLLM",
    "ProviderError",
    "create_llm",
    "run_chain",
    "ChainError",
    "map_analysis",
]
