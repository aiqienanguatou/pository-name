# Ech0 reverse proxy for Uppcoder

This small FastAPI app forwards all HTTP requests to an Ech0 server listening
inside the same Uppcoder container at `http://127.0.0.1:6277`.

## Deploy

Connect this public Git repository to the existing Uppcoder FastAPI component.
Uppcoder starts `uvicorn main:app`; keep `main.py` and `requirements.txt` at
the repository root.

The default upstream is `http://127.0.0.1:6277`. If needed, set
`ECH0_UPSTREAM` to another reachable HTTP URL in the app environment.

After deployment, open the existing FastAPI HTTPS URL. Requests will be
forwarded to Ech0.

## Important

- Keep the Ech0 process running in the same container.
- The Ech0 port should remain private; do not expose 6277 separately.
- Anyone who can access the public FastAPI URL can reach the Ech0 login page.
  Use Ech0's own account/password protection and do not publish admin credentials.
