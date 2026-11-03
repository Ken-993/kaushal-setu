"""Request bodies for the POST endpoints.

Pydantic checks every incoming JSON body against these classes. If a field is missing or out
of range, FastAPI answers with HTTP 422 and a message saying which field is wrong, so the
model code never sees bad input.
"""
from pydantic import BaseModel, Field


class SkillScores(BaseModel):
    """JDS technical skill scores, each on the documented 1-5 scale."""
    big_data_skills: float = Field(..., ge=1, le=5, examples=[3.2])
    maths_stats_skills: float = Field(..., ge=1, le=5, examples=[3.8])
    coding_skills: float = Field(..., ge=1, le=5, examples=[3.5])
    ai_and_ml_skills: float = Field(..., ge=1, le=5, examples=[3.4])
    dashboard_and_storytelling_skills: float = Field(..., ge=1, le=5, examples=[3.9])


class PersonalityScores(BaseModel):
    """SDS Big-Five scores on the file's normalised scale (observed range roughly 17-68)."""
    neuroticism: float = Field(..., ge=0, le=100, examples=[36])
    extraversion: float = Field(..., ge=0, le=100, examples=[43])
    openness_to_experience: float = Field(..., ge=0, le=100, examples=[41])
    agreeableness: float = Field(..., ge=0, le=100, examples=[45])
    conscientiousness: float = Field(..., ge=0, le=100, examples=[45])


class JobPosting(BaseModel):
    """A job posting to place in a salary band."""
    exp_min: float = Field(..., ge=0, le=40, description="minimum years of experience", examples=[3])
    exp_max: float = Field(..., ge=0, le=45, description="maximum years of experience", examples=[6])
    skills: list[str] = Field(default_factory=list, description="skills, e.g. ['python', 'sql']",
                              examples=[["python", "sql", "machine learning"]])
    job_title: str = Field("", max_length=200, examples=["Data Scientist"])
    city: str = Field("bengaluru", max_length=60, examples=["bengaluru"])
