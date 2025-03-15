# Automated Detection of Error-Handling Bugs in LLM-enabled Software Systems

This repository contains the implementation for the paper: **"Automated Detection of Error-Handling Bugs in LLM-enabled Software Systems"**.

## Environment

- Python 3.14
- OpenAI 1.63.0

## Installation

Install required packages:
```bash
pip install openai==1.63.0
```

## Project Structure

The core source code is located in the `LIE_Detector` directory.

```
LIE_Detector/
├── ...
├── Config.py
└── LIE-Detector.py
```

## Configuration

Update the paths and settings in `Config.py` before running the project:

```python
python_version = "3.14"
openai_version = "1.63.0"

# Paths
llm_funcs_path = ""  # Path to LLM functions
function_details_path = ""
defined_func_set_path = ""
multi_defined_func_dict_path = ""
defined_func_set_path = ""
call_graph_path = ""
```

## Quick Start

Run the project from the command line:

```bash
cd LIE_Detector
python LIE_Detector/LIE-Detector.py
```

Ensure all dependencies are installed:

```bash
pip install openai==1.63.0
```

For questions or issues, please open an issue in this repository.

