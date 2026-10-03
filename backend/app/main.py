from fastapi import FastAPI, HTTPException, status



app = FastAPI()


@app.get('/')
async def hello():
    return {"status", "I work fine"}
