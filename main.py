import uvicorn


def main() -> None:
    """Run the Meeting STT FastAPI application."""

    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)


if __name__ == "__main__":
    main()
