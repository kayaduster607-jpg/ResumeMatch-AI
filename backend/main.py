import uvicorn

if __name__ == "__main__":
    # On Windows + Playwright, uvicorn reload spawns another process and can
    # keep Edge profile locks.  Keep reload disabled for the crawler version.
    uvicorn.run("app.main:app", host="0.0.0.0", port=9000, reload=False)
