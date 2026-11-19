from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, SecretStr, StringConstraints, field_validator

Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=80)]
Email = Annotated[str, StringConstraints(strip_whitespace=True, max_length=254, pattern=r"^[^\s@]+@[^\s@]+\.[^\s@]+$")]
Phone = Annotated[str, StringConstraints(strip_whitespace=True, pattern=r"^\+?[0-9 ()-]{7,24}$")]


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Credentials(Input):
    email: Email
    password: SecretStr = Field(min_length=8, max_length=128)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return value.lower()


class Registration(Credentials):
    full_name: Name
    phone: Phone | None = None

    @field_validator("phone")
    @classmethod
    def check_phone(cls, value):
        if value and not 7 <= sum(c.isdigit() for c in value) <= 15:
            raise ValueError("Телефон нөмірінде 7–15 цифр болуы керек.")
        return value


class Login(Credentials):
    remember: bool = False


class Profile(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: str
    full_name: str
    phone: str | None


class StartAttempt(Input):
    count: int = Field(ge=1, le=20)


class LegacyStartAttempt(Input):
    topic: int = Field(ge=0, le=10)
    count: int = Field(ge=1, le=20)


class AttemptAnswerInput(Input):
    question_id: int = Field(gt=0)
    selected_option_index: int | None = Field(default=None, ge=0, le=3)


class SubmitAttempt(Input):
    answers: list[AttemptAnswerInput]


class DraftAttemptAnswer(AttemptAnswerInput):
    pass


class AttemptQuestionView(BaseModel):
    position: int
    question_id: int
    topic: str
    text: str
    options: list[str]
    level: str
    selected_option_index: int | None = None
    correct_option_index: int | None = None
    status: Literal["correct", "incorrect", "unanswered"] | None = None


class AttemptView(BaseModel):
    id: UUID
    test_id: int
    test_title: str
    status: Literal["in_progress", "completed"]
    started_at: datetime
    finished_at: datetime | None = None
    score: int | None = None
    question_count: int
    percent: int | None = None
    retry_of_id: UUID | None = None
    questions: list[AttemptQuestionView]


class AttemptHistoryItem(BaseModel):
    id: UUID
    test_id: int
    test_title: str
    finished_at: datetime
    score: int
    question_count: int
    percent: int


class LegacyAnswerInput(Input):
    question: int = Field(gt=0)
    choice: int = Field(ge=0, le=3)


class MistakeReviewInput(Input):
    attempt_id: UUID
    question_id: int = Field(gt=0)
    reviewed: bool



