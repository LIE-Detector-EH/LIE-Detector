# function_detail_extractor.py

import ast
import os
from typing import List, Dict, Set, Optional
from tqdm import tqdm
from Config import supported_logging_modules

class FunctionDetail:
    def __init__(self, name: str, filename: str):
        self.name = name
        self.filename = filename
        self.exceptions: Set[str] = set()
        self.logs: List[str] = []
        self.exception_code_snippets: Dict[str, List[Dict]] = {}

    def to_dict(self) -> Dict:
        return {
            "name": self.name,
            "filename": self.filename,
            "exceptions": list(self.exceptions),
            "logs": self.logs,
            "exception_code_snippets": self.exception_code_snippets
        }

def get_exception_aliases(tree: ast.AST, exception_modules: List[str]) -> Dict[str, str]:
    """Identify all aliases for exception modules and return a mapping from alias to real module."""
    alias_map = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name in exception_modules:
                    asname = alias.asname if alias.asname else alias.name
                    alias_map[asname] = alias.name
        elif isinstance(node, ast.ImportFrom):
            if node.module in exception_modules:
                for alias in node.names:
                    asname = alias.asname if alias.asname else alias.name
                    alias_map[asname] = f"{node.module}.{alias.name}"
    #print(f"[DEBUG] Exception aliases: {alias_map}")  # Debug print
    return alias_map

class FunctionDetailAnalyzer(ast.NodeVisitor):
    def __init__(self, logging_aliases: Set[str], exception_aliases: Dict[str, str], code_lines: List[str],
                 parent_map: Dict[ast.AST, ast.AST], filename: str):
        self.exceptions: Set[str] = set()
        self.logs: List[str] = []
        self.exception_code_snippets: Dict[str, List[Dict]] = {}
        self.logging_aliases = logging_aliases
        self.exception_aliases = exception_aliases
        self.code_lines = code_lines
        self.parent_map = parent_map
        self.filename = filename
        #self.data_flow = ErrorHandlingDataFlow()
        self.current_try_block = None
        self.variable_defs = {}

    def visit_Call(self, node: ast.Call):
        """Check for logging calls."""
        if isinstance(node.func, ast.Attribute):
            value = node.func.value
            attr = node.func.attr
            if isinstance(value, ast.Name) and value.id in self.logging_aliases:
                log_level = attr.upper()
                log_message = self._get_log_message(node)
                if log_message:
                    self.logs.append(f"{log_level}: {log_message}")
                    #print(f"[DEBUG] Found log in {self.filename} at line {node.lineno}: {log_level}: {log_message}")  # Debug print
        self.generic_visit(node)

    def visit_Raise(self, node: ast.Raise):
        """Collect exception types and their corresponding code snippets."""
        exception = self._get_exception_name(node)
        if exception:
            #print(f"[DEBUG] Found exception '{exception}' in file '{self.filename}' at line {node.lineno}")  # Debug print
            self.exceptions.add(exception)
            try_block = self._get_enclosing_try_except(node)
            if try_block:
                code_snippet = self._get_code_snippet(try_block)
                #print("try_block code_snippet", code_snippet)
            else:
                code_snippet = self._get_code_snippet(node)
                #print("Not try_block", code_snippet)
            if code_snippet:
                snippet_info = {
                    "filename": self.filename,
                    "lineno": node.lineno,
                    "code": code_snippet
                }
                if snippet_info not in self.exception_code_snippets.get(exception, []):
                    if exception not in self.exception_code_snippets:
                        self.exception_code_snippets[exception] = []
                    self.exception_code_snippets[exception].append(snippet_info)
                    #print(f"[DEBUG] Added snippet for exception '{exception}' in file '{self.filename}' at line {node.lineno}")  # Debug print
        self.generic_visit(node)

    def _get_log_message(self, node: ast.Call) -> Optional[str]:
        """Extract log message from the logging call."""
        if node.args:
            arg = node.args[0]
            if isinstance(arg, ast.Str):
                return arg.s
            elif isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                return arg.value
            elif isinstance(arg, ast.JoinedStr):  # For f-strings
                return ''.join([value.s if isinstance(value, ast.Str) else '{...}' for value in arg.values])
            # Extend to handle more complex log messages if needed
        return None

    def _get_exception_name(self, node: ast.Raise) -> str:
        """Extract the exception name from the raise statement."""
        name = ""
        if node.exc:
            if isinstance(node.exc, ast.Call):
                if isinstance(node.exc.func, ast.Name):#function name in the form of : function_name
                    name = node.exc.func.id
                elif isinstance(node.exc.func, ast.Attribute):#function name in the form of : module_name.function_name
                    if isinstance(node.exc.func.value, ast.Name):
                        alias = node.exc.func.value.id
                        attr = node.exc.func.attr
                        if alias in self.exception_aliases:
                            name = f"{self.exception_aliases[alias]}.{attr}"
                        else:
                            name = f"{alias}.{attr}"
            elif isinstance(node.exc, ast.Name):
                name = node.exc.id
            elif isinstance(node.exc, ast.Attribute):
                if isinstance(node.exc.value, ast.Name):
                    alias = node.exc.value.id
                    attr = node.exc.attr
                    if alias in self.exception_aliases:
                        name = f"{self.exception_aliases[alias]}.{attr}"
                    else:
                        name = f"{alias}.{attr}"
        if name.endswith('Error') or name.endswith('Exception'):
            return name
        return ""

    def _get_code_snippet(self, node: ast.AST) -> str:
        """Retrieve the code snippet corresponding to the AST node."""
        if hasattr(node, 'lineno') and hasattr(node, 'end_lineno'):
            lineno = node.lineno
            end_lineno = node.end_lineno
            if 1 <= lineno <= len(self.code_lines) and 1 <= end_lineno <= len(self.code_lines):
                return "\n".join(self.code_lines[lineno - 1:end_lineno])
        elif hasattr(node, 'lineno'):
            lineno = node.lineno
            if 1 <= lineno <= len(self.code_lines):
                return self.code_lines[lineno - 1]
        return ""

    def _get_enclosing_try_except(self, node: ast.Raise) -> Optional[ast.Try]:
        """Find the nearest enclosing Try node containing the raise statement."""
        parent = self.parent_map.get(node, None)
        if (parent == None):
            return node
        while parent:
            if isinstance(parent, ast.Try):
                return parent
            tmpPatent = self.parent_map.get(parent, None)
            if (tmpPatent==None):
                return parent
            parent = tmpPatent
        return None

    def analyze(self, node: ast.FunctionDef) -> FunctionDetail:
        """Analyze the function and return its details."""
        function_name = node.name
        #print("analyze", function_name)
        filename = getattr(node, 'filename', 'Unknown')
        detail = FunctionDetail(function_name, filename)
        #print("before self.exceptions", self.exceptions, self.exception_code_snippets)
        self.visit(node)
        #print("after self.exceptions", self.exceptions, self.exception_code_snippets)
        detail.exceptions = self.exceptions
        detail.logs = self.logs
        detail.exception_code_snippets = self.exception_code_snippets
        #detail.error_data_flow = self.build_error_data_flow(node)
        return detail


def get_logging_aliases(tree: ast.AST) -> Set[str]:
    """Identify all aliases for logging modules."""
    logging_aliases = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name in supported_logging_modules:
                    if alias.asname:
                        logging_aliases.add(alias.asname)
                    else:
                        logging_aliases.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module in supported_logging_modules:
                for alias in node.names:
                    if alias.asname:
                        logging_aliases.add(alias.asname)
                    else:
                        logging_aliases.add(alias.name)
    #print(f"[DEBUG] Logging aliases: {logging_aliases}")  # Debug print
    return logging_aliases


def build_parent_map(tree: ast.AST) -> Dict[ast.AST, ast.AST]:
    """Build a mapping from child nodes to their parent nodes."""
    parent_map = {}
    for parent in ast.walk(tree):
        for child in ast.iter_child_nodes(parent):
            parent_map[child] = parent
    return parent_map


def get_parent(child: ast.AST, tree: ast.AST) -> Optional[ast.AST]:
    """Get the parent node of a given AST node."""
    return getattr(tree, 'parent_map', {}).get(child, None)


def get_qualified_name(node: ast.AST, tree: ast.AST, file_path: str) -> str:
    """Get the fully qualified name of a function, including module and class names if any."""
    names = []
    parent = get_parent(node, tree)
    while parent:
        if isinstance(parent, ast.ClassDef):
            names.insert(0, parent.name)
        parent = get_parent(parent, tree)
    # Include module name derived from file path
    module_name = os.path.splitext(os.path.basename(file_path))[0]
    names.insert(0, module_name)
    names.append(node.name)
    qualified_name = ".".join(names)
    #print(f"[DEBUG] Qualified name: {qualified_name}")  # Debug print
    return qualified_name


def extract_all_functions_exceptions_logs(files: List[str]) -> Dict[str, Dict]:
    """
    Traverse all Python files, extract exceptions and logs for each function.
    """
    function_details = {}
    exception_modules = ['sqlalchemy.exc']  # Define the exception modules you want to handle

    for file in tqdm(files, desc="Analyzing functions", unit="file"):
        #try:
        with open(file, "r", encoding="utf-8") as f:
            code = f.read()
            code_lines = code.splitlines()
            tree = ast.parse(code, filename=file)
            parent_map = build_parent_map(tree)
            tree.parent_map = parent_map  # Dynamically add parent_map attribute
            logging_aliases = get_logging_aliases(tree)
            exception_aliases = get_exception_aliases(tree, exception_modules)

            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    qualified_name = get_qualified_name(node, tree, file)
                    node.filename = file  # Dynamically add filename attribute
                    try:
                        # Create a new analyzer instance per function to avoid data contamination
                        analyzer = FunctionDetailAnalyzer(logging_aliases, exception_aliases, code_lines,
                                                          parent_map, file)
                        detail = analyzer.analyze(node)
                        function_details[qualified_name] = detail.to_dict()
                        #print(f"[DEBUG] Function '{qualified_name}' analyzed: Exceptions={detail.exceptions}, Logs={detail.logs}")  # Debug print
                    except Exception as e:
                        print(f"Error analyzing function {qualified_name} in {file}: {e}")
        #except Exception as e:
        #    print(f"Error parsing file {file}: {e}")
    return function_details
