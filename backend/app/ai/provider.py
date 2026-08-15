"""The contract every AI provider implements.

The design rule for this whole package: **the model describes the document's
layout; it does not report the nutrition figures.** `infer_table_mapping` reads
a small sample and returns a description of which column means what — our own
code then reads every value out of the document. A model cannot hallucinate a
calorie count it was never asked to produce.

`extract_entries_from_text` is the exception, used only for prose diaries with
no table to map. There the model does transcribe, so its output is checked
against the source text before it is trusted (see `services/imports/prose.py`).
"""

from typing import Protocol, runtime_checkable

from app.schemas.import_ import RawEntry, TableMapping, TableSample


@runtime_checkable
class AIProvider(Protocol):
    """Implemented by `stub.StubProvider` and `openai_compatible.OpenAICompatibleProvider`."""

    name: str

    def infer_table_mapping(self, sample: TableSample) -> TableMapping:
        """Describe what the table's columns mean, from a small sample of rows."""
        ...

    def extract_entries_from_text(self, chunk: str) -> list[RawEntry]:
        """Pull entries out of a prose diary that has no table to map."""
        ...
