# VentureFlux

VentureFlux is an AI-assisted city trip planner. It converts a short questionnaire into a timed itinerary, selects attractions with OR-Tools, calculates real walking, bicycle, and car routes with OpenRouteService, and displays the result on a Leaflet map.

## Try the project

### Hosted version

> **Live demo:** add the deployment URL here before submitting the repository.

### Run locally

The application consists of a FastAPI backend and a Next.js frontend. They run in two separate terminals.

### Requirements

- Python 3.12
- Node.js 20 or newer
- npm
- internet access
- an [Ollama API key](https://ollama.com/settings/keys)
- an [OpenRouteService API key](https://openrouteservice.org/log-in/) for real route distances, durations, and geometry

No local database or Docker setup is required for the current demo flow.

## 1. Clone the repository

```bash
git clone https://github.com/danielsterzel/hackyeah-ds-ir-jk-kk-km.git
cd hackyeah-ds-ir-jk-kk-km
```

## 2. Configure environment variables

Create the backend environment file in the repository root:

```bash
cp .env.example .env
```

Set the two API keys in `.env`:

```dotenv
DATABASE_URL=not-used-by-current-demo
DATABASE_PASSWORD=not-used-by-current-demo
OLLAMA_API_KEY=your_ollama_api_key
ORS_API_KEY=your_openrouteservice_api_key
```

`OLLAMA_API_KEY` is required to process questionnaire answers. `ORS_API_KEY` enables real routing for walking, bicycle, and car. If ORS is unavailable, the planner remains operational but uses its approximate straight-line routing fallback.

Do not commit the `.env` file.

## 3. Start the backend — terminal 1

Run these commands from the repository root:

```bash
python3.12 -m venv backend/.venv
source backend/.venv/bin/activate
python -m pip install --upgrade pip
pip install -r backend/requirements.txt
cd backend
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

The API should now be available at:

- API: [http://127.0.0.1:8000](http://127.0.0.1:8000)
- Swagger UI: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

## 4. Start the frontend — terminal 2

Run these commands from the repository root:

```bash
cd frontend
cp .env.example .env.local
npm ci
npm run dev
```

The frontend environment file should contain:

```dotenv
NEXT_PUBLIC_BACKEND_URL=http://127.0.0.1:8000
```

Open [http://localhost:3000](http://localhost:3000) in a browser. The questionnaire is available directly at [http://localhost:3000/planner](http://localhost:3000/planner).

Allow location access when the browser asks for it. The user's real location becomes the first routing node, so travel time from the starting point to the first attraction is included in the timeline.

## Windows PowerShell notes

The setup is identical, except for these commands:

```powershell
Copy-Item .env.example .env
py -3.12 -m venv backend\.venv
backend\.venv\Scripts\Activate.ps1
```

For the frontend environment file:

```powershell
Copy-Item frontend\.env.example frontend\.env.local
```

Then use the same `pip`, `uvicorn`, `npm ci`, and `npm run dev` commands shown above.

## Quick jury test

One useful scenario for verifying the complete flow:

1. Open `/planner` and allow browser location access.
2. Select Kraków and a trip lasting several hours.
3. Enter a budget such as `200 PLN`.
4. Ask for museums or historical attractions.
5. Enable food and select one or two preferred cuisines.
6. Choose walking or bicycle transport.
7. Submit the questionnaire and wait for the generated plan.

Verify that:

- the first leg starts at **Your location**;
- arrival times include travel duration;
- exactly one restaurant is included when food is requested and a matching candidate is available;
- the map follows streets instead of drawing straight lines when ORS is configured;
- the summary contains total cost, travel time, and distance;
- the plan warns when it exceeds the declared budget.

## Optional verification commands

Backend tests:

```bash
cd backend
source .venv/bin/activate
PYTHONPATH=. pytest -q app/tests
```

Frontend checks:

```bash
cd frontend
npm run lint
npm run build -- --webpack
```

## Troubleshooting

### The backend reports missing settings

Make sure `.env` exists in the repository root, not inside `backend/`, and restart the backend after changing it.

### The questionnaire cannot generate a plan

Check `OLLAMA_API_KEY` and internet access. The backend uses the hosted Ollama API, so the local Ollama desktop application is not required.

### Routes are straight lines or a routing fallback warning appears

Check `ORS_API_KEY`, restart the backend, and confirm that the machine can access `https://api.heigit.org`. Public transport still intentionally uses the project's fallback model; GTFS and real-time transit are outside the current MVP.

### The browser does not provide the starting location

Allow location permission for `localhost`. If permission was previously denied, reset it in the browser's site settings and reload the page.

### The frontend cannot reach the backend

Confirm that:

- FastAPI is running on port `8000`;
- Next.js is running on port `3000`;
- `frontend/.env.local` contains `NEXT_PUBLIC_BACKEND_URL=http://127.0.0.1:8000`;
- the frontend was restarted after changing `.env.local`.

## How it works

```text
Questionnaire
    -> structured preferences extracted by the LLM
    -> attraction and restaurant candidate search
    -> OpenRouteService distance/duration matrix
    -> OR-Tools selection and visit ordering
    -> geometry for final route legs
    -> timeline, summary, stop list, and Leaflet map
```

More detailed technical documentation:

- [Planner decision process](docs/PROCES_DECYZYJNY_PLANERA.md)
- [System and presentation notes](docs/OPIS_SYSTEMU_PREZENTACJA.md)

## Technology

- Next.js, React, TypeScript, and Leaflet
- FastAPI, Python, and Pydantic
- OR-Tools for plan optimization
- OpenRouteService for walking, bicycle, and car routing
- Ollama Cloud for questionnaire interpretation and ticket-price research

## Team

- Jarosław Klima
- Daniel Sterzel
- Iwo Ropa
- Kamil Marchewka
- Kacper Kaszuba

## Use of AI tools

The application uses an Ollama-hosted language model to transform free-form answers into structured planning preferences and to support ticket-price research. OpenAI Codex was used as a development assistant during implementation, testing, and documentation.
