# DBCooker: Automating Database-Native Function Code Synthesis with LLMs

DBCooker is an LLM-based system for automatically synthesizing database native functions. The system consists of three key components.
- (1) A function characterization module that aggregates multi-source declarations, identifies function units requiring specialized coding through hierarchical analysis, and traces cross-unit dependencies via static analysis; 
- (2) Synthesis operations including a pseudo-code-based coding plan generator, a hybrid fill-in-the-blank model guided by probabilistic priors, and three-level progressive validation; 
- (3) An adaptive orchestration strategy that unifies operations with existing database tools and dynamically sequences them based on orchestration history. 

**See tested functions at [[benchmark](https://anonymous.4open.science/r/DBCooker-FE81/benchmark/sqlite_functions_with_testcase_code_understand_v1.json)], and newly synthesized functions for SQLite at [[code](https://anonymous.4open.science/r/DBCooker-FE81/SQLite.pdf)].**

## 🚀 Features

- **Agent-Based Architecture**: Modular agent system for different tasks, integration with multiple LLM providers (OpenAI, Anthropic, etc.)
- **Multi-Database Support**: PostgreSQL, SQLite, DuckDB
- **Code Analysis**: Advanced code understanding and dependency analysis
- **Benchmarking**: Performance evaluation and comparison tools


## 📁 Project Structure

```
DBCooker/
├── code_agent/ # Core agent framework
│ ├── agent/ # Agent implementations
│ ├── tools/ # Tool integrations
│ ├── utils/ # Utility functions
│ └── vector_store/ # Vector database integration
├── code_utils/ # Utility modules
│ ├── extract_utils/ # Database-specific extractors
│ └── fileControl.py # File management utilities
├── understand_code/ # Code analysis and understanding
│ ├── project_analyze/ # Project analysis tools
│ └── commit_analyze/ # Commit analysis
├── benchmark/ # Benchmark data and results
│ ├── postgresql/ # PostgreSQL benchmarks
│ ├── sqlite/ # SQLite benchmarks
│ └── duckdb/ # DuckDB benchmarks
├── agent_main.py # Main execution script
├── agent_eval.py # Evaluation script
└── code_config.yaml # Configuration file
```

## 🛠️ Installation

### Prerequisites

- Python 3.8+

### Setup

1. **Clone the repository**:
```bash
git clone 
cd DBCooker
```

2. **Install dependencies**:
```bash
pip install -r requirements.txt
```

3. **Configure the environment**:
- Copy and modify `code_config.yaml` with your API keys and settings
- Update paths in `code_utils/constants.py` to match your environment

4. **Set up database environments** (optional):
- Install PostgreSQL, SQLite, DuckDB as needed
- Configure database-specific settings in the respective modules

## ⚙️ Configuration

### Model Configuration

The framework supports multiple LLM providers. Configure them in `code_config.yaml`:

```yaml
model_providers:
openai:
base_url: your_openai_base_url
api_key: your_api_key
provider: openai
anthropic:
api_key: your_anthropic_api_key
provider: anthropic
```

### Agent Configuration

Configure different agents in `code_config.yaml`:

```yaml
agents:
  plan_agent:
    model: plan_agent_model
    max_steps: 10
    tools:
      - bash
      - str_replace_based_edit_tool
      - sequentialthinking
      - task_done
  
  code_agent:
    model: code_agent_model
    max_steps: 200
    tools:
      - bash
      - str_replace_based_edit_tool
      - sequentialthinking
      - task_done
```

## 🚀 Usage

### Basic Usage

1. **Run the main agent**:
   ```bash
   python agent_main.py
   ```

2. **Evaluate generated code**:
   ```bash
   python agent_eval.py
   ```

### Database-Specific Operations

#### PostgreSQL
```python
from code_agent.tools.database.postgresql_compile_test import compile_postgresql
success, result = compile_postgresql(compile_folder, install_folder)
```

#### SQLite
```python
from code_agent.tools.database.sqlite_compile_test import compile_sqlite
success, result = compile_sqlite(compile_folder)
```

#### DuckDB
```python
from code_agent.tools.database.duckdb_compile_test import compile_incremental
success, result = compile_incremental(compile_folder)
```

### Code Analysis

```python
from understand_code.model import UnderstandRepo

# Initialize repository analysis
repo = UnderstandRepo("C++", "/path/to/project")
repo.create_udb()
repo.get_db()

# Analyze dependencies
dependencies = repo.analyze_dependency()

# Get function information
functions = repo.get_function()
```

## 🔧 Tools and Agents

### Available Tools

- **Bash Tool**: Execute shell commands
- **Edit Tool**: String-based code editing
- **JSON Edit Tool**: JSON manipulation
- **Database Tools**: Compilation and testing for different databases
- **Understand Tool**: Code analysis and understanding
- **Sequential Thinking**: Step-by-step reasoning

### Agent Types

1. **Plan Agent**: High-level planning and task decomposition
2. **Code Agent**: Code generation and implementation
3. **Test Agent**: Testing and validation

## 📊 Benchmarking

The framework includes comprehensive benchmarking capabilities:

- **Function-level benchmarks** for each database system
- **Performance metrics** and evaluation
- **Test case generation** and validation
- **Comparative analysis** across database systems

## 📈 Evaluation

The framework provides comprehensive evaluation capabilities:

- **Code Quality Assessment**: Syntax, compliance, and semantic validation
- **Performance Metrics**: Execution time and resource usage
- **Test Coverage**: Comprehensive test case validation
- **Benchmark Comparison**: Cross-database performance analysis

## 🔍 Code Analysis

### Understanding Code Structure

```python
from understand_code.project_analyze.function_analyze import UnderstandFunctionExtractor

# Extract function information
extractor = UnderstandFunctionExtractor("project.und")
functions = extractor.get_all_functions()
```

### Dependency Analysis

```python
# Analyze file dependencies
dependencies = repo.analyze_dependency()

# Get control flow information
control_flow = repo.get_control_flow("file.cpp")
```

## 📝 API Reference

### Core Classes

- **BaseAgent**: Base class for all agents
- **UnderstandRepo**: Repository analysis and understanding
- **ToolExecutor**: Tool execution framework

### Key Functions

- **compile_database()**: Compile database projects
- **run_tests()**: Execute test suites
- **analyze_code()**: Perform code analysis
- **generate_code()**: AI-powered code generation

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.