# AI Trip Planner

An AI-powered travel recommendation system that provides personalized place suggestions with interactive map visualization.

## Requirements

- Python 3.9 or higher
- OpenAI API key

## Setup

1. Create a virtual environment (recommended):
```bash
python -m venv venv
source venv/bin/activate  # On Windows use: venv\Scripts\activate
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Set up environment variables:
   - Copy `.env.example` to `.env`
   - Add your OpenAI API key to the `.env` file

## Running the Application

```bash
streamlit run main.py
```

## Features

- AI-powered travel recommendations using GPT-4
- Interactive map visualization with location markers
- Detailed place descriptions and coordinates
- User-friendly interface built with Streamlit 