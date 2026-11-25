"""Pydantic request/response schemas."""

from app.schemas.scheduler import (
    AvailabilityMatrixPayload,
    ConflictLogItem,
    CourseEligibilityItem,
    MeetingDTO,
    OfferingDTO,
    RelaxationSuggestion,
    ScheduleOptionDTO,
    SolveRequest,
    SolveResponse,
    SubmitScheduleRequest,
    SubmitScheduleResponse,
    SwapActionDTO,
    SwapRecommendationDTO,
    TranscriptUpdateItem,
    TranscriptUpdateRequest,
)

__all__ = [
    "AvailabilityMatrixPayload",
    "ConflictLogItem",
    "CourseEligibilityItem",
    "MeetingDTO",
    "OfferingDTO",
    "RelaxationSuggestion",
    "ScheduleOptionDTO",
    "SolveRequest",
    "SolveResponse",
    "SubmitScheduleRequest",
    "SubmitScheduleResponse",
    "SwapActionDTO",
    "SwapRecommendationDTO",
    "TranscriptUpdateItem",
    "TranscriptUpdateRequest",
]
