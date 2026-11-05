
# AURORA SQL Agent

### Intelligent Multi-Agent Natural Language to SQL Application

AURORA SQL Agent is an AI-powered application that converts natural-language questions into SQL queries, executes them against connected databases, and presents the results in an understandable format.

The application uses a multi-agent architecture powered by LangGraph, LangChain, and Google Gemini.

---

## Features

- Convert natural-language questions into SQL queries.
- Connect to PostgreSQL and MySQL databases.
- Automatically discover database schemas and relationships.
- Generate SQL queries using Google Gemini.
- Validate SQL queries before execution.
- Execute read-only SQL queries.
- Automatically retry failed SQL generation and execution.
- Explain query results using AI.
- Generate visualizations using Plotly.
- Explore database schemas, tables, columns, keys, and indexes.
- View generated SQL in an editable SQL workspace.
- Export query results to CSV and Excel.
- Maintain conversation history during the application session.

---

## Technology Stack

| Component | Technology |
|---|---|
| Programming Language | Python |
| User Interface | Streamlit |
| LLM | Google Gemini |
| Agent Orchestration | LangGraph |
| LLM Framework | LangChain |
| Database Connectivity | SQLAlchemy |
| SQL Parsing | SQLGlot |
| Data Processing | Pandas |
| Visualization | Plotly |
| Supported Databases | PostgreSQL, MySQL |
| Testing | Pytest |
| Observability | LangSmith |

---

## Project Architecture

AURORA uses a multi-agent architecture where individual agents handle specific responsibilities.

### Agents

1. **Supervisor Agent** – Understands the user's request and determines the workflow.
2. **Schema Agent** – Discovers relevant database tables, columns, and relationships.
3. **SQL Generation Agent** – Generates SQL queries using Gemini.
4. **SQL Validation Agent** – Validates SQL syntax and checks query safety.
5. **Execution Agent** – Executes approved SQL queries against the connected database.
6. **Result Analysis Agent** – Interprets and explains query results.
7. **Visualization Agent** – Creates charts when visualization is appropriate.

### Workflow

```text
User Question
      |
      v
Supervisor Agent
      |
      v
Schema Agent
      |
      v
SQL Generation Agent
      |
      v
SQL Validation Agent
      |
      +---- Invalid SQL
      |         |
      |         v
      |    Regenerate SQL
      |         |
      |         +---- Retry
      |
      v
Execution Agent
      |
      +---- Execution Error
      |         |
      |         v
      |    Regenerate SQL
      |
      v
Result Analysis Agent
      |
      v
Visualization Agent
      |
      v
Display Results
```

---

## Project Structure

```text
sql-agent/
│
├── app.py
├── config.py
├── requirements.txt
├── .env
├── .env.example
├── .gitignore
├── README.md
│
├── agents/
│   ├── supervisor.py
│   ├── schema_agent.py
│   ├── sql_generation_agent.py
│   ├── sql_validation_agent.py
│   ├── execution_agent.py
│   ├── result_analysis_agent.py
│   └── visualization_agent.py
│
├── graph/
│   ├── workflow.py
│   ├── state.py
│   └── routing.py
│
├── database/
│   ├── connection.py
│   ├── schema_discovery.py
│   ├── metadata.py
│   └── query_executor.py
│
├── tools/
│   ├── sql_parser.py
│   ├── sql_validator.py
│   ├── query_optimizer.py
│   └── visualization_tools.py
│
├── ui/
│   ├── chat_interface.py
│   ├── database_panel.py
│   ├── schema_explorer.py
│   ├── sql_editor.py
│   ├── results_panel.py
│   └── sidebar.py
│
├── evaluation/
│   ├── benchmark.py
│   ├── test_cases.json
│   └── metrics.py
│
├── tests/
│   ├── test_database.py
│   ├── test_schema.py
│   ├── test_sql_generation.py
│   ├── test_validation.py
│   ├── test_execution.py
│   └── test_workflow.py
│
└── utils/
    ├── logging.py
    └── helpers.py
```

---

## Installation and Setup

### 1. Clone the Repository

```bash
git clone https://github.com/DEEPAKT09/aurora-sql-agent.git
cd sql-agent
```

### 2. Create a Virtual Environment

Windows:

```bash
python -m venv venv
venv\Scripts\activate
```

Linux / macOS:

```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables

Create a `.env` file in the project root directory.

Use `.env.example` as the reference.

Configure your Gemini API key:

```dotenv
APP_ENV=development

GEMINI_API_KEY=your_gemini_api_key
GEMINI_MODEL=gemini-2.5-flash

LANGSMITH_TRACING=false
LANGSMITH_API_KEY=
LANGSMITH_PROJECT=aurora-sql-agent
LANGSMITH_ENDPOINT=https://api.smith.langchain.com
```

Obtain your Gemini API key from:

https://aistudio.google.com/app/apikey

Never commit your actual `.env` file or expose API keys publicly.

---

## Running the Application

Start the Streamlit application:

```bash
streamlit run app.py
```

The application will be available at:

```text
http://localhost:8501
```

---

## Database Configuration

AURORA currently supports the following databases.

### PostgreSQL

Provide the following connection details in the Database Connection panel:

- Host
- Port
- Database name
- Username
- Password
- Schema
- SSL mode, where applicable

Default PostgreSQL port:

```text
5432
```

### MySQL

Provide:

- Host
- Port
- Database name
- Username
- Password

Default MySQL port:

```text
3306
```

Use a dedicated database account with read-only permissions.

---

## Example Natural Language Queries

Once the database is connected, users can ask questions such as:

```text
Show all customers.
```

```text
Find the top five customers by total purchase amount.
```

```text
How many orders were placed in 2025?
```

```text
Show the monthly sales trend.
```

```text
Compare the sales performance of different products.
```

AURORA generates the corresponding SQL, validates it, executes it, and presents the results.

The generated SQL depends on the actual database schema.

---

## SQL Safety

AURORA is designed to execute read-only queries.

The application includes:

- SQL parsing and validation.
- Restrictions on write operations.
- Query execution limits.
- Configurable row limits.
- Query timeouts.
- A controlled SQL regeneration and retry workflow.

**Important:** Application-level validation should be supplemented with database-level read-only permissions. Use a dedicated database account that cannot modify or delete production data.

---

## Testing

Run the complete test suite:

```bash
python -m pytest -v
```

Run an individual test module:

```bash
python -m pytest tests/test_database.py -v
```

The project includes tests for:

- Database connections.
- Schema discovery.
- SQL generation.
- SQL validation.
- Query execution.
- LangGraph workflow orchestration.

---

## LangSmith Observability

LangSmith can optionally be enabled for tracing and monitoring LLM operations.

Configure the following variables in `.env`:

```dotenv
LANGSMITH_TRACING=true
LANGSMITH_API_KEY=your_langsmith_api_key
LANGSMITH_PROJECT=aurora-sql-agent
LANGSMITH_ENDPOINT=https://api.smith.langchain.com
```

Keep tracing disabled if you do not want to use LangSmith.

Review tracing and data-handling settings before sending sensitive database information to external services.

---

## Deployment

AURORA can be deployed to a hosting platform that supports Python and Streamlit, such as Render.

Before deployment:

1. Configure environment variables securely.
2. Install dependencies from `requirements.txt`.
3. Configure database network access.
4. Use read-only database credentials.
5. Verify the application and database connection.
6. Avoid committing secrets or sensitive database information.

---

## Future Enhancements

Potential improvements include:

- Additional database integrations.
- Persistent conversation history.
- Advanced query optimization.
- Improved SQL evaluation and benchmarking.
- Role-based access control.
- Query audit logging.
- Enhanced multilingual natural-language support.
- More advanced visualization recommendations.

---

## License

Add the appropriate license information before distributing this project.
