from fastapi import FastAPI, HTTPException, status

from api.planning_controller import router as planning_router


app = FastAPI()
app.include_router(planning_router)


@app.get('/')
async def hello():
    return {"status", "I work fine"}
