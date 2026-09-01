from src.logging_config import configure_logging

configure_logging(process_name="api")

from src.api import create_app

app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("api_main:app", host="0.0.0.0", port=8000, reload=True)

