# code_analyzer.py

import networkx as nx
from typing import List, Dict, Set
from call_graph_builder import get_python_files, build_call_graph
from function_detail_extractor import extract_all_functions_exceptions_logs
from storage_utils import save_call_graph, load_call_graph, save_function_details, load_function_details, save_variable_to_file
from Config import call_graph_path, llm_funcs_path, function_details_path

def bcg_init(project_path: str):
    print("Preprocessing project: building call graph and extracting function details...")
    python_files = get_python_files(project_path)
    print(f"Found {len(python_files)} Python files in the project.")

    # Build call graph
    call_graph, llm_funcs = build_call_graph(python_files)

    print("Call graph saved")

def preprocess_project(project_path: str):
    print("Preprocessing project: building call graph and extracting function details...")
    python_files = get_python_files(project_path)
    print(f"Found {len(python_files)} Python files in the project.")

    # Build call graph
    call_graph, llm_funcs = build_call_graph(python_files)
    print(f"Call graph has {call_graph.number_of_nodes()} nodes and {call_graph.number_of_edges()} edges.")
    print(f"LLM-related functions: {llm_funcs}")

    # Print call graph edges for debugging
    '''print("Call graph edges:")
    for edge in call_graph.edges():
        print(f"  {edge[0]} -> {edge[1]}")'''

    #save_call_graph(call_graph, call_graph_path)
    #save_variable_to_file(llm_funcs, llm_funcs_path)

    # Extract function exception and log details
    function_details = extract_all_functions_exceptions_logs(python_files)
    print(f"Extracted details for {len(function_details)} functions.")
    save_function_details(function_details, function_details_path)

def load_preprocessed_data(call_graph_path: str, function_details_path: str) -> (nx.DiGraph, Dict[str, Dict]):
    call_graph = load_call_graph(call_graph_path)
    function_details = load_function_details(function_details_path)
    return call_graph, function_details

# Helper function to get all functions in the call tree recursively
def get_call_tree(function: str, call_graph: nx.DiGraph) -> set:
        # Start with the given function
        call_tree = {function}
        # Get all the functions called directly by the given function
        for called_function in call_graph.successors(function):
            # Recursively get the call tree for each called function
            if (called_function not in call_tree):
                call_tree.update(get_call_tree(called_function, call_graph))
        return call_tree

def analyze_function(target_function: str, call_graph: nx.DiGraph, function_details: Dict[str, Dict]) -> Dict:
    if target_function not in function_details:
        print(f"Function '{target_function}' not found in function details.")
        return {}

    # Get all functions in the call tree (including the target function)
    if target_function not in call_graph:
        print(f"Function '{target_function}' has no outgoing edges in the call graph.")
        involved_functions = {target_function}
    else:
        involved_functions = get_call_tree(target_function, call_graph)

    aggregated_exceptions = []
    aggregated_logs = []
    exception_code_snippets = {}

    for func in involved_functions:
        details = function_details.get(func, {})
        print("analyze_function func", func)
        print("details.get exceptions", details.get("exceptions", []))
        print("details.get logs", details.get("logs", []))
        print("details.get logs", details.get("exception_code_snippets", []))
        aggregated_exceptions.extend(details.get("exceptions", []))
        aggregated_logs.extend(details.get("logs", []))
        # Merge exception_code_snippets
        for exc, snippets in details.get("exception_code_snippets", {}).items():
            if exc not in exception_code_snippets:
                exception_code_snippets[exc] = []
            exception_code_snippets[exc].extend(snippets)

    # Remove duplicate exceptions
    aggregated_exceptions = list(set(aggregated_exceptions))

    return {
        "functions": list(involved_functions),
        "exceptions": aggregated_exceptions,
        "logs": aggregated_logs,
        "exception_code_snippets": exception_code_snippets
    }


def get_exception_code_snippets(exception_query: str, function_details: Dict[str, Dict]) -> List[Dict]:
    snippets = []
    is_full_name = '.' in exception_query  # Determine if the query is a full name

    for func, details in function_details.items():
        exc_snippets = details.get("exception_code_snippets", {})
        for full_exc, snips in exc_snippets.items():
            if is_full_name:
                # Full name match
                if full_exc == exception_query:
                    snippets.extend(snips)
            else:
                # Match only the exception class name
                if full_exc.split('.')[-1] == exception_query:
                    snippets.extend(snips)
    return snippets
