projectPath = ""

API_Path = ""

call_graph_path = ""  # Path to save the call graph

func2ast_path = ""  # Path to save the data flow graph

multi_defined_func_dict_path = ""  # Path to save the multi-defined functions

defined_func_set_path = ""

llm_funcs_path = ""  # Path to save the list of LLM functions

supported_logging_modules = []  # Add more logging libraries if needed

llm_libraries = []

function_details_path = ""  # Path to save function details

model_selection = ""

api_key = ""

base_url = ""

max_retries = None
max_retrival = None

class Debug:
    def __init__(self):
        self.callgraph = False
        
    def enable_all(self):
        for attr in vars(self):
            if isinstance(getattr(self, attr), bool):
                setattr(self, attr, True)
                
    def disable_all(self):
        for attr in vars(self):
            if isinstance(getattr(self, attr), bool):
                setattr(self, attr, False)


debug_flag = Debug()
debug_flag.call_graph = True

Fixed_LLM_function = f'''
def LLM_function(input_text: str) -> str:
    url = ""
    apikey = ""
    try:
        response = openai.ChatCompletion.create(
                model="deepseek-v3",
                messages=[
                    {"role": "system", "content": "You are a helpful assistant."},
                    {"role": "user", "content": input_text}
                ],
                max_tokens=150,
                temperature=0.7,
            )
        return response['choices'][0]['message']['content'].strip()
    except Exception as e:
        print("Error", e)
        return ""
'''