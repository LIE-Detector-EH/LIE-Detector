import ast
import os
from typing import List
import networkx as nx
from tqdm import tqdm
from Config import llm_libraries, func2ast_path, multi_defined_func_dict_path, call_graph_path, llm_funcs_path, defined_func_set_path
from storage_utils import save_dict_to_file, save_call_graph, save_variable_to_file

def get_python_files(project_path: str) -> List[str]:
    python_files = []
    for root, dirs, files in os.walk(project_path):
        for file in files:
            if file.endswith(".py"):
                python_files.append(os.path.join(root, file))
    return python_files

ast_node_dict = {}
multi_defined_func_dict = {}
defined_func_set = set()

def update_multi_defined_func_dict(ast_name, search_name):
    global multi_defined_func_dict
    search_name = search_name.split(".")[-1]
    if (search_name not in multi_defined_func_dict):
        multi_defined_func_dict[search_name] = [ast_name]
    elif(ast_name not in multi_defined_func_dict[search_name]):
        multi_defined_func_dict[search_name].append(ast_name)

class CallGraphVisitor(ast.NodeVisitor):#function call, defination call
    def __init__(self, module_name: str, source_code: str):
        self.module_name = module_name
        self.current_function = None
        self.calls = []  # List of (caller, callee) tuples
        self.func_imports = {}  # To store imported functions or modules
        self.module_imports_alias = {}
        self.defined_funcs = {}#save the func List defined in the current file
        self.hardcoded_strings = {}  # Dictionary to store hardcoded strings by function name
        self.source_code = source_code.split("\n")
        self.current_class = None
        self.llm_related_functions = []  # Store LLM-related functions
        self.class_list = []

    def collect_hard_code_string(self, funcType, hard_code_string, line_no):
        if (self.current_function == None):
            return
        if (funcType == "arg" and hard_code_string!=''):
            return
        self.hardcoded_strings[self.current_function].append([hard_code_string, line_no, self.source_code[line_no-1]])

    def visit_If(self, node):
        # Collect hardcoded strings in the condition of an 'if' statement
        if isinstance(node.test, ast.Compare):
            for comparator in node.test.comparators:
                if isinstance(comparator, ast.Str):  # Check if it's a hardcoded string
                    # Add a tuple (value, line, code) to the set to avoid duplicates
                    self.collect_hard_code_string("branch", comparator.s, node.lineno)
        self.generic_visit(node)

    def visit_Str(self, node):
        # Collect all hardcoded strings encountered
        self.collect_hard_code_string("str", node.s, node.lineno)
        self.generic_visit(node)

    def visit_Import(self, node):
        for alias in node.names:
            if (alias.asname != None):
                self.module_imports_alias[alias.asname] = alias.name#import openai as oi, os as key, openai as value
                #print("visit_Import alias.name", alias.asname, alias.name)
        self.generic_visit(node)

    def visit_ImportFrom(self, node):
        for alias in node.names:
            full_name = f"{node.module}.{alias.name}"
            self.func_imports[alias.name] = full_name
            #print("visit_Import full_name", full_name, alias.asname, alias.name)
        self.generic_visit(node)

    def visit_ClassDef(self, node):#the __init__ function need to be considered as a call.
        for base in node.bases:
            if isinstance(base, ast.Name):
                print(f"Class {node.name} inherits from {base.id}")
                self.calls.append((node.name, base.id))

        self.current_class = node.name

        self.save_ast(self.current_class, node)

        if (self.current_class not in self.class_list):
            self.class_list.append(self.current_class)
            print("Added class name", self.current_class)

        self.generic_visit(node)
        self.current_class = None

    def save_ast(self, func_name, node):
        start_line = node.lineno - 1  # Adjusting for 0-indexed list
        end_line = node.end_lineno if hasattr(node, 'end_lineno') else start_line + len(node.body)
        func_def_body = self.source_code[start_line:end_line]
        if (func_name in ast_node_dict):
            ast_node_dict[func_name].append([node, func_def_body, node.lineno])
        else:
            ast_node_dict[func_name] = [[node, func_def_body, node.lineno]]
    def visit_FunctionDef(self, node):
        global ast_node_dict, defined_func_set
        previous_function = self.current_function

        func_search_name = node.name
        defined_func_set.add(func_search_name)
        self.current_function = f"{self.module_name}.{node.name}"
        if (node.name == "__init__" and self.current_class != None):
            self.current_function = self.current_class
            #print("__init__ module name", self.current_class)
        elif (self.current_class != None):
            self.current_function = f"{self.current_class}.{node.name}"

        update_multi_defined_func_dict(self.current_function, func_search_name)

        if (self.current_function not in self.defined_funcs):
            self.defined_funcs[node.name] = self.current_function
        else:
            print("Warning: current_function is repeated in self.defined_funcs", self.defined_funcs)

        if self.current_function not in self.hardcoded_strings:
            self.hardcoded_strings[self.current_function] = []

        if (node.name != "__init__"):#the ast of this clas has been saved during visit_ClassDef
            self.save_ast(self.current_function, node)

        self.generic_visit(node)
        self.current_function = previous_function

    def visit_AsyncFunctionDef(self, node):
        # Handle async functions similarly
        self.visit_FunctionDef(node)

    def visit_Call(self, node):
        if self.current_function:
            # Get the function name being called
            func = node.func
            func_search_name = None
            if isinstance(func, ast.Attribute):
                # Handle calls like module.function or self.method
                value = func.value
                if isinstance(value, ast.Name):
                    module = value.id
                    if (module in self.module_imports_alias):
                        #print("change module to alas")
                        #print("before", module)
                        module = self.module_imports_alias[module]
                        #print("after", module)
                    called_function = f"{module}.{func.attr}"
                else:
                    # For calls like some_func().method(), we cannot resolve the module
                    called_function = func.attr
                func_search_name = func.attr
                #print("visit_Call 1", func_search_name, self.source_code[node.lineno - 1])
                #print("ast.Attribute", called_function)
            elif isinstance(func, ast.Name):
                # Handle direct function calls
                called_function = func.id
                func_search_name = called_function
                #print("visit_Call called_function", called_function)
                if called_function in self.func_imports:
                    # Resolve function to full name based on imports
                    called_function = f"{self.func_imports[called_function]}"#save full name
                elif called_function in self.defined_funcs:
                    #print("before defined_funcs", called_function)
                    called_function = self.defined_funcs[called_function]
                    #print("after defined_funcs", called_function)

            else:
                # For other types of calls, use a placeholder
                called_function = ast.dump(func)
                func_search_name = called_function
                #print("visit_Call 3", func_search_name, self.source_code[node.lineno - 1])

            #called_function will be stored in the ast
            update_multi_defined_func_dict(called_function, func_search_name)

            if ("OpenAI" in called_function):
                print("visit_Call OpenAI", self.current_function, called_function)
            # Record the (caller, callee) pair
            self.calls.append((self.current_function, called_function))

            # Check the arguments of the function call for hardcoded strings
            for arg in node.args:
                if isinstance(arg, ast.Str):  # Check if it's a hardcoded string
                    # Add a tuple (value, line, code) to the set to avoid duplicates
                    self.collect_hard_code_string("arg", arg.s, node.lineno)

            # Identify LLM-related functions
            if any(lib in called_function for lib in llm_libraries):
                self.llm_related_functions.append(func_search_name)

        self.generic_visit(node)

    def get_hardcoded_strings(self):
        # Convert the set back to a list for final use
        print("self.hardcoded_strings", self.hardcoded_strings)
        for item in self.hardcoded_strings:
            print("get_hardcoded_strings item", item)
        return [{'funcName': funcName, 'value': value, 'line': line, 'code': code} for funcName, itset in self.hardcoded_strings.items() for value, line, code in itset]

    def get_llm_related_functions(self):
        # Return a list of functions related to LLMs
        return self.llm_related_functions, self.class_list
def build_call_graph(python_files: List[str]):
    """Build a call graph from the list of Python files."""
    global ast_node_dict, multi_defined_func_dict
    ast_node_dict = {}
    call_graph = nx.DiGraph()
    llm_related_func = []
    total_class_list = []
    for file in tqdm(python_files, desc="Building call graph", unit="file"):
        module_name = os.path.splitext(os.path.basename(file))[0]
        with open(file, "r", encoding="utf-8") as f:
            #try:
            f_code = f.read()
            tree = ast.parse(f_code, filename=file)
            visitor = CallGraphVisitor(module_name, f_code)
            visitor.visit(tree)

            #hardcoded_strings = visitor.get_hardcoded_strings()
            #print("hardcoded_strings", hardcoded_strings)
            # Add nodes and edges to the graph
            for caller, callee in visitor.calls:
                call_graph.add_node(caller)
                call_graph.add_node(callee)
                call_graph.add_edge(caller, callee)

            tempt_func_list, class_list = visitor.get_llm_related_functions()
            if (tempt_func_list!=None):
                llm_related_func.extend(tempt_func_list)
            if (class_list):
                total_class_list.extend(class_list)
            #except Exception as e:
            #    print(f"Error parsing file {file}: {e}")
    save_dict_to_file(ast_node_dict, func2ast_path)
    save_dict_to_file(multi_defined_func_dict, multi_defined_func_dict_path)
    save_dict_to_file(defined_func_set, defined_func_set_path)
    save_call_graph(call_graph, call_graph_path)
    save_variable_to_file([llm_related_func, total_class_list], llm_funcs_path)
    return call_graph, llm_related_func

def call_graph_class_test():
    test_code = '''
from typing import List
def llm_com():
    openai.api_key = "xxx"
    talk = openai.Completion.create(var1, var2, var3)
    response = talk(prompt)
    return response

def preprocess(response):
    
rt = re.find("keyword", response)
    if (rt!=None):
        response = response[rt:]
    return rt
def useage():
    result = llm_com()
    parsed_r = preprocess(result)
    web_search = List(parsed_r)
    print("web_search", web_search)

useage()
    '''
    tree = ast.parse(test_code)
    visitor = CallGraphVisitor("test_module", test_code)
    visitor.visit(tree)
    print("visitor.calls", visitor.hardcoded_strings)