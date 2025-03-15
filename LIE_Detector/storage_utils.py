# storage_utils.py

import networkx as nx
import pickle
import json
from typing import Dict


def save_call_graph(call_graph: nx.DiGraph, filepath: str):

    with open(filepath, "wb") as f:
        pickle.dump(call_graph, f)
    print(f"Call graph saved to {filepath}.")

def load_call_graph(filepath: str) -> nx.DiGraph:

    with open(filepath, "rb") as f:
        call_graph = pickle.load(f)
    print(f"Call graph loaded from {filepath}.")
    return call_graph

def save_function_details(function_details: Dict[str, Dict], filepath: str):

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(function_details, f, indent=4)
    print(f"Function details saved to {filepath}.")

def load_function_details(filepath: str) -> Dict[str, Dict]:

    with open(filepath, "r", encoding="utf-8") as f:
        function_details = json.load(f)
    print(f"Function details loaded from {filepath}.")
    return function_details


def save_dict_to_file(dictionary, file_path):

    with open(file_path, 'wb') as file:
        pickle.dump(dictionary, file)

def load_dict_from_file(file_path):

    try:
        with open(file_path, 'rb') as file:
            dictionary = pickle.load(file)

        return dictionary
    except FileNotFoundError:

        return {}
    except pickle.UnpicklingError:

        return {}

def save_variable_to_file(variable, filename):
    with open(filename, 'wb') as f:
        pickle.dump(variable, f)

def load_variable_from_file(filename):
    with open(filename, 'rb') as f:
        variable = pickle.load(f)
    return variable