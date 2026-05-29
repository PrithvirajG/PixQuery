# Repository Guidelines

## Project Structure & Module Organization

PixQuery is split into a Python backend and a React frontend. Backend code lives in `backend/src`: FastAPI routes are in `api`, ingestion in `ingestion`, image pipelines in `processing`, search in `query`, storage adapters in `storage`, and repository implementations in `repositories`. Backend tests and fixtures are in `backend/tests`.

Frontend code lives in `frontend/src`. Reusable UI components are in `components`, page-level screens are in `pages` and `views`, and static browser assets are in `frontend/public`. Root-level `docker-compose.yml` starts Redis, RabbitMQ, and Qdrant.

## Build, Test, and Development Commands

- `docker compose up redis rabbitmq qdrant`: starts local infrastructure used by the backend.
- `cd backend && pip install -r requirements.txt`: installs backend runtime dependencies.
- `cd backend && uvicorn src.api.main:app --reload`: runs the FastAPI API locally.
- `cd backend && python -m unittest discover tests`: runs backend tests.
- `cd frontend && npm install`: installs React dependencies.
- `cd frontend && npm start`: starts the React development server at `http://localhost:3000`.
- `cd frontend && npm test`: runs Jest/React Testing Library tests.
- `cd frontend && npm run build`: creates a production frontend build.
- `cd frontend && npm run build:css`: regenerates minified Tailwind output in `src/output.css`.

## Coding Style & Naming Conventions

Use 4-space indentation for Python and lowercase `snake_case` module filenames. Prefer explicit imports from `src.*` packages and keep API, storage, repository, and processing concerns separated. React components use PascalCase filenames and exports, such as `ImageCard.js`; hooks, helpers, and local variables use camelCase. Follow the Create React App ESLint configuration and avoid committing generated caches such as `__pycache__`.

## Testing Guidelines

Backend tests use `unittest`; name files `test_*.py` and keep fixtures in `backend/tests`. Add focused tests for processing, search, storage, and API behavior when changing those areas. Frontend tests use Jest with React Testing Library; colocate component tests as `*.test.js` when practical.

## Commit & Pull Request Guidelines

Recent commits use short, descriptive summaries, for example `Fixed and shifted to Rabbit MQ`. Keep commits focused on one change. Pull requests should include a concise description, affected backend/frontend areas, test results, linked issues when applicable, and screenshots for UI changes.

## Security & Configuration Tips

Do not commit local databases, model outputs, credentials, or watched photo directories. Keep service credentials and paths configurable through environment variables. The API currently allows CORS from `http://localhost:3000`; update this deliberately for deployed environments.
