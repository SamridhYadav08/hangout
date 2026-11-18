# Hangout for two

FastAPI + python-socketio. One file per activity (bouquet, notes, chess_game, photobooth, car_race, dress_duel).

## Run locally
    pip install -r requirements.txt
    uvicorn main:asgi --reload        # http://localhost:8000
    python smoke_test.py http://localhost:8000

## Deploy (Render, free tier)
1. Push this folder to a GitHub repo.
2. Render > New > Blueprint > pick the repo (it reads `render.yaml`). JWT_SECRET is generated for you.
3. When it is live: `python smoke_test.py https://<your-app>.onrender.com`
4. Open the URL in two browsers (or phone + laptop): create a room in one, join with the code in the other.

Notes: keep a single worker (state is in memory). Free tier sleeps after idle, so the first load can take ~30s.
Photo Booth needs HTTPS for the camera (Render gives you that). If video won't connect on some networks, set TURN_URL / TURN_USER / TURN_CRED.
