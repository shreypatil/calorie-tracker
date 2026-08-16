"""The contract every AI provider implements.

The design rule for this whole package: **the model describes the document's
layout; it does not report the nutrition figures.** `infer_table_mapping` reads
a small sample and returns a description of which column means what — our own
code then reads every value out of the document. A model cannot hallucinate a
calorie count it was never asked to produce.

`extract_entries_from_text` is the exception, used only for prose diaries with
no table to map. There the model does transcribe, so its output is checked
against the source text before it is trusted (see `services/imports/prose.py`).

`converse` is the chat primitive, and it follows the same principle from the
other direction: the model does not act, it *asks* to act. It returns the name
of a tool and some arguments, and `services/chat/` decides whether that tool
exists, validates the arguments, supplies the user's identity, and runs it.
"""

from typing import TYPE_CHECKING, Protocol, runtime_checkable

from app.schemas.chat import AssistantTurn, ProviderMessage, ToolSpec
from app.schemas.import_ import RawEntry, TableMapping, TableSample
from app.schemas.nutrition import NutritionEstimate, NutritionEstimateRequest
from app.schemas.photo import PhotoExtraction, PhotoKind

if TYPE_CHECKING:  # avoids a cycle: the photo service imports this module
    from app.services.photo.prepare import PreparedImage


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

    def converse(self, messages: list[ProviderMessage], tools: list[ToolSpec]) -> AssistantTurn:
        """Continue the conversation, optionally requesting tool calls."""
        ...

    def analyze_image(self, image: "PreparedImage", kind: PhotoKind) -> PhotoExtraction:
        """Read a nutrition label, or estimate the contents of a plate of food.

        For a label the result must include the panel transcribed verbatim: the caller checks
        every reported figure against it and discards any that was not actually written there.
        """
        ...

    def estimate_nutrition(self, request: NutritionEstimateRequest) -> NutritionEstimate:
        """Estimate the nutrition of a described dish.

        Unlike every other method here there is no source document to check the answer against —
        this is judgement, not transcription. What keeps it honest is that the caller asked for
        specific fields and gets only those back, and that a person sees every figure in a form
        before anything is saved.
        """
        ...
