"""AMEXIO backend pipeline.

One Python service hosts the case model; each stage is a function with a typed
input and output, validated at the boundary (decision BE-01). The stage
contracts live in ``contracts``:

    from pipeline import Analysis, CmIdOutput
"""

from .contracts import Analysis, CmIdOutput

__all__ = ["Analysis", "CmIdOutput"]
