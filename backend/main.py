"""FastAPI web server: the bridge between the models and the website.

In the container (local or on Render) the Dockerfile starts it with:

    uvicorn backend.main:app --host 0.0.0.0 --port $PORT

Then open
    /          the website (files in frontend/)
    /docs      interactive API documentation, try every endpoint here

How the pieces talk:
    browser (frontend/app.js)  --fetch("/api/...")-->  this file  --calls-->  services.py
    services.py  --reads-->  artifacts/*.json + *.joblib  (made by `python run_all.py`)
"""
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from backend import services
from backend.resume import MAX_BYTES, ResumeError
from backend.schemas import JobPosting, PersonalityScores, SkillProfile, SkillScores

FRONTEND = Path(__file__).resolve().parent.parent / "frontend"
log = logging.getLogger("uvicorn.error")


@asynccontextmanager
async def lifespan(_app):
    # Load every model and result file once at start-up, so the first visitor is not kept waiting
    # (on Render's free plan the server has only a tenth of a CPU).
    try:
        services.store()
        log.info("Kaushal Setu: artifacts loaded")
    except services.ArtifactsMissing as e:
        log.error("Kaushal Setu: %s", e)
    yield


app = FastAPI(title="Kaushal Setu API",
              description="Statistics, ML predictions and job-profile similarity for the SAS CU hackathon datasets.",
              version="1.0.0", lifespan=lifespan)

# Compress responses (JSON, JS, CSS) - roughly 3-4x less data per page view.
app.add_middleware(GZipMiddleware, minimum_size=1000)
# CORS lets a page served from another address (e.g. VS Code Live Server on :5500) call this API.
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


@app.exception_handler(services.ArtifactsMissing)
def _missing(_, exc):
    return JSONResponse(status_code=503, content={"detail": str(exc)})


def _lookup(fn, *args):
    """Turn 'unknown role / view' KeyErrors into a clean HTTP 404."""
    try:
        return fn(*args)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e).strip("'\""))


# ----------------------------------------------------------------- GET endpoints
@app.get("/api/health", tags=["system"])
def health():
    services.store()  # raises ArtifactsMissing (-> 503) if the pipeline has not been run
    return {"status": "ok"}


@app.get("/api/overview", tags=["data"])
def overview():
    """Dataset audit, every cleaning decision and the plain-language findings."""
    return services.overview()


@app.get("/api/options", tags=["data"])
def options():
    """Lists the website needs for its forms: roles, skills, cities, input ranges."""
    return services.options()


@app.get("/api/stats", tags=["statistics"])
def stats():
    """Phase 2 output: hypothesis tests, effect sizes and the internal-vs-market alignment."""
    return services.store()["stats"]


@app.get("/api/models", tags=["models"])
def models():
    """Phase 3 output: model comparison, ROC curves, coefficients, confusion matrices."""
    return services.models_summary()


@app.get("/api/profiles", tags=["job profiles"])
def profiles():
    """One summary row per job profile."""
    return services.profiles_list()


@app.get("/api/profiles/{role:path}", tags=["job profiles"])
def profile(role: str):
    """Full profile of one role, plus its five nearest roles in every distance view."""
    return _lookup(services.profile, role)


@app.get("/api/similarity", tags=["job profiles"])
def similarity(view: str = Query("skills", description="skills | competency | salary | career | blended")):
    """Distance matrix, 2-D map coordinates, clusters and dendrogram for one view."""
    return _lookup(services.similarity, view)


@app.get("/api/compare", tags=["job profiles"])
def compare(a: str = Query(..., examples=["Data Scientist"]), b: str = Query(..., examples=["Data Analyst"])):
    """Two roles side by side: distances on every view, significance tests, skill overlap."""
    if a == b:
        raise HTTPException(status_code=400, detail="pick two different roles")
    return _lookup(services.compare, a, b)


# ---------------------------------------------------------------- POST endpoints
@app.post("/api/predict/hike", tags=["models"])
def predict_hike(body: SkillScores):
    """Junior data scientist: probability of a HIGH salary hike from five skill scores (1-5)."""
    return services.predict_hike(body.model_dump())


@app.post("/api/predict/success", tags=["models"])
def predict_success(body: PersonalityScores):
    """Senior data scientist: probability of HIGH success from Big-Five personality scores."""
    return services.predict_success(body.model_dump())


@app.post("/api/predict/salary-band", tags=["models"])
def predict_band(body: JobPosting):
    """Job posting: probability of each salary band (lakhs per year)."""
    return services.predict_band(**body.model_dump())


@app.post("/api/match", tags=["job profiles"])
def match(body: SkillScores):
    """Rank job profiles by how well your skill strengths fit what each role asks for."""
    return services.match_roles(body.model_dump())


@app.post("/api/fit", tags=["resume"])
def fit(body: SkillProfile):
    """No resume? Send your skills and years of experience; get your fit for every role."""
    return services.assess_fit(body.skills, body.years, body.city)


@app.get("/api/fit/sample", tags=["resume"])
def fit_sample(city: str = "bengaluru"):
    """The fit result for the bundled sample resume (for demos)."""
    return services.sample_resume(city)


@app.get("/api/skill-picker", tags=["resume"])
def skill_picker():
    """Popular skills grouped into areas, for the 'pick your skills' form."""
    return services.skill_picker()


@app.post("/api/resume", tags=["resume"])
async def resume(file: UploadFile = File(..., description="your resume: .pdf, .docx or .txt, max 5 MB"),
                 city: str = Form("bengaluru")):
    """Upload a resume: detected skills and experience, best-fitting roles, skills to add, salary band.
    The file is processed in memory and never saved."""
    content = await file.read(MAX_BYTES + 1)  # never read more than the limit into memory
    try:
        return services.analyse_resume(file.filename, content, city)
    except ResumeError as e:
        raise HTTPException(status_code=422, detail=str(e))


# ------------------------------------------------------------ serve the website
# Mounted LAST so the /api/... routes above always win. html=True makes "/" return index.html.
app.mount("/", StaticFiles(directory=FRONTEND, html=True), name="frontend")
