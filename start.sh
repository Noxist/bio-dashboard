#!/bin/bash
set -e

echo "[bio-dashboard] Starting FastAPI on :8000 ..."
uvicorn app.main:app --host 0.0.0.0 --port 8000 --log-level info &
FASTAPI_PID=$!

echo "[bio-dashboard] Starting Streamlit on :8501 ..."
streamlit run app/dashboard/streamlit_app.py \
    --server.port 8501 \
    --server.address 0.0.0.0 \
    --server.headless true \
    --browser.gatherUsageStats false \
    --theme.base dark \
    &
STREAMLIT_PID=$!

# Wait for either process to exit, then kill the other
trap "kill $FASTAPI_PID $STREAMLIT_PID 2>/dev/null; exit" SIGTERM SIGINT

while kill -0 $FASTAPI_PID 2>/dev/null && kill -0 $STREAMLIT_PID 2>/dev/null; do
    sleep 2
done

echo "[bio-dashboard] A process exited, shutting down..."
kill $FASTAPI_PID $STREAMLIT_PID 2>/dev/null || true
exit 1
