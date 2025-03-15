# subsequent_api_analysis.py
from Config import call_graph_path, function_details_path
from code_analyzer import preprocess_project, load_preprocessed_data, analyze_function, get_exception_code_snippets

def test():
    # 2. Define target function and exception to query
    #target_function = "session.object_session"  # Fully qualified name: module_name.function_name
    #target_function = "module_a.callerA"
    target_function = "session.object_session"
    #exception_to_query = "sqlalchemy.exc.InvalidRequestError"  # Exception name to query
    exception_to_query = "InvalidRequestError"
    subsequent_Path_List = ["D:\\LLM_Usage_Survey\\tools\\sqlalchemy-main"]
    subsequent_API_List = [[target_function]]
    for id, each_lib in enumerate(subsequent_Path_List):
        subsequentAPI_analysis_init(each_lib)
        for each_api in subsequent_API_List[id]:
            collected_code_snippets = subsequentAPI_analysis(each_api)
    print("Finished")
    print("collected_code_snippets", collected_code_snippets)
    #query_exception_code_blocks(exception_to_query)

def subsequentAPI_analysis_init(projectPath):
    global call_graph, function_details
    preprocess_project(projectPath)

    # Load preprocessed data
    print("\nLoading preprocessed data...")
    call_graph, function_details = load_preprocessed_data(call_graph_path, function_details_path)

    print(f"Functions found: {len(list(function_details.keys()))}")  # Debug print

def subsequentAPI_analysis(target_function):
    global call_graph, function_details
    # Analyze target function
    print(f"\nAnalyzing target function '{target_function}'...")
    print("function_details", function_details)
    aggregated_details = analyze_function(target_function, call_graph, function_details)

    print(f"Aggregated details: {aggregated_details}")  # Debug print
    results = []
    if aggregated_details:
        print(f"\nAggregated details for '{target_function}':")
        print(f"Number of involved functions: {len(aggregated_details['functions'])} functions")
        print(f"Functions involved: {', '.join(aggregated_details['functions'])}")
        print(
            f"Exceptions ({len(aggregated_details['exceptions'])}): {', '.join(aggregated_details['exceptions']) if aggregated_details['exceptions'] else 'None'}")
        print(f"Logs ({len(aggregated_details['logs'])}):")
        for log in aggregated_details['logs']:
            print(f"  {log}")
        print("\nException Code Snippets:")
        for exc, snippets in aggregated_details.get('exception_code_snippets', {}).items():
            print(f"  Exception: {exc} ({len(snippets)} occurrences)")
            for snippet in snippets:
                results.append(f"    File: {snippet['filename']}, Line: {snippet['lineno']}"+f"    Code:\n{snippet['code']}\n")
                print(f"    File: {snippet['filename']}, Line: {snippet['lineno']}")
                print(f"    Code:\n{snippet['code']}\n")
    else:
        print(f"\nNo details found for function '{target_function}'.")
    return results

def query_exception_code_blocks(exception_to_query):
    # 6. Query specific exception's code blocks
    print(f"\nQuerying try-except blocks for exception '{exception_to_query}'...")
    call_graph, function_details = load_preprocessed_data(call_graph_path, function_details_path)
    snippets = get_exception_code_snippets(exception_to_query, function_details)

    if snippets:
        print(f"\nTry-except blocks handling '{exception_to_query}' ({len(snippets)} occurrences):")
        for snippet in snippets:
            print(f"  File: {snippet['filename']}, Line: {snippet['lineno']}")
            print(f"  Code:\n{snippet['code']}\n")
    else:
        print(f"No try-except blocks found handling exception '{exception_to_query}'.")

call_graph = None
function_details = None