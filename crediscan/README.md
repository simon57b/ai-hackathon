# Crediscan - AI Crawler Application

An advanced AI-powered web crawler built with FastAPI that integrates multiple AI services for comprehensive company analysis and data aggregation.

## Features

- FastAPI-based REST API with async support
- Integration with multiple AI services:
  - OpenAI GPT-4o for content analysis
  - Serper API for web search
  - Custom AI models for data aggregation
- Intelligent job position detection for AI and Web3 companies
- Comprehensive company analysis including:
  - Company background and history
  - Founders' information
  - Funding details
  - Legal issues
  - Security assessment
  - User reviews
  - Current job openings
- Caching system for improved performance
- Asynchronous HTTP requests using httpx
- Robust error handling and retry mechanisms

## Setup Instructions

### 1. Create Virtual Environment
```bash
python -m venv venv
```

### 2. Activate Virtual Environment
```bash
# On Unix/macOS
source venv/bin/activate

# On Windows
.\venv\Scripts\activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables
Create a `.env` file in the project root with the following:
```env
SERPER_API_KEY=your_serper_api_key
OPENAI_API_KEY=your_openai_api_key
AGGREGATE_TOKENS=token1,token2
```

Required API keys:
- `SERPER_API_KEY`: For web search functionality
- `OPENAI_API_KEY`: For AI content analysis
- `AGGREGATE_TOKENS`: For data aggregation services (comma-separated)

### 5. Run the Application
```bash
# Method 1: Using run.py
python crediscan/run.py

# Method 2: Using uvicorn directly
uvicorn app.main:app --reload --host 0.0.0.0 --port 8010
```

## Development

### Project Structure
```
crediscan/
├── app/
│   ├── routers/         # API endpoints
│   ├── services/        # Business logic
│   ├── utils/           # Utility functions
│   └── models.py        # Data models
├── cache/               # Cache directory
└── run.py              # Application entry point
```

### Cache System
- Results are cached to improve performance
- Cache files are stored in the `cache/` directory
- Separate caches for different operations:
  - `discover_result.json`
  - `analyzer_result.json`
  - `aggregate_result.json`

## API Documentation

Once the application is running, access the API documentation at:
- Swagger UI: `http://localhost:8010/docs`
- ReDoc: `http://localhost:8010/redoc`

## License

MIT License

