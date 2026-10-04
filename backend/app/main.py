from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.questionnaire import router as questionnaire_router
from app.api.planning_controller import router as planning_router

app = FastAPI()


app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    # Accept the production URL and every Vercel preview deployment.
    # Preview hostnames change for each deployment, so matching only one
    # project prefix makes otherwise valid builds fail their CORS preflight.
    allow_origin_regex=r"https://.*\.vercel\.app",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(questionnaire_router)
app.include_router(planning_router)


@app.get("/")
async def hello():
    return {"status", "I work fine"}
