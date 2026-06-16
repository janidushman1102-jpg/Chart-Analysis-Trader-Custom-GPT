from fastapi import FastAPI

app = FastAPI(
    title="Chart Analysis Trader API",
    version="1.0.0",
    servers=[
        {
            "url": https://chart-analysis-trader-custom-gpt-production.up.railway.app/openapi.json
        }
    ]
)

@app.get("/")
def root():
    return {"status": "running"}