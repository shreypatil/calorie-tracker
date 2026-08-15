"""Photo extraction schemas (FR-5).

Two quite different jobs share one shape. Reading a **nutrition label** is transcription: the
numbers exist in the image and the model's task is to report them without inventing any.
Estimating a **plate of food** is judgement: no figure in the result is written anywhere, and
the honest output is a set of informed guesses.

`PhotoExtraction` carries both, and `kind` is what tells the verification layer which rules
apply. The `transcript` field is the load-bearing one for labels — the model returns the panel
verbatim, and our code then checks that every structured number it reported actually occurs
there. A value that does not is dropped. That check is why the label path can be trusted
without a second OCR engine, and it is meaningless for a plate, where the field stays empty.
"""

import enum
from typing import Annotated

from pydantic import BaseModel, Field

from app.schemas.import_ import DraftRow, NutritionBasis


class PhotoKind(enum.StrEnum):
    """What the user says they photographed. Chosen before upload, so each prompt is tuned."""

    LABEL = "label"
    MEAL = "meal"


class RawFoodItem(BaseModel):
    """One food the model reported. Every figure is optional — absent beats invented."""

    food_name: Annotated[str, Field(max_length=200)]
    quantity: Annotated[float | None, Field(default=None, gt=0)]
    unit: Annotated[str | None, Field(default=None, max_length=30)]

    calories: Annotated[float | None, Field(default=None, ge=0)] = None
    protein_g: Annotated[float | None, Field(default=None, ge=0)] = None
    carbs_g: Annotated[float | None, Field(default=None, ge=0)] = None
    fat_g: Annotated[float | None, Field(default=None, ge=0)] = None
    fiber_g: Annotated[float | None, Field(default=None, ge=0)] = None
    sugar_g: Annotated[float | None, Field(default=None, ge=0)] = None
    sodium_mg: Annotated[float | None, Field(default=None, ge=0)] = None


class PhotoExtraction(BaseModel):
    """What a provider returns for one image."""

    kind: PhotoKind = PhotoKind.MEAL

    #: The label panel copied out verbatim. Checked against, never shown as data.
    #: Empty for meal photos, which have no text to transcribe.
    transcript: str = ""

    basis: NutritionBasis = NutritionBasis.PER_SERVING
    serving_size_g: Annotated[
        float | None,
        Field(default=None, gt=0, description="Grams per serving, when the panel states it."),
    ]

    items: Annotated[list[RawFoodItem], Field(default_factory=list, max_length=20)]
    notes: str = Field(default="", description="Anything the user should check")
    confidence: Annotated[float, Field(default=0.5, ge=0, le=1)]


class PhotoDraft(BaseModel):
    """The reviewed result handed to the client. **Nothing here has been saved.**"""

    kind: PhotoKind
    source_filename: str
    basis: NutritionBasis
    serving_size_g: float | None
    confidence: float
    notes: str
    #: One per food found. Photo rows are never `ok` — a person looks at all of them.
    rows: list[DraftRow]
