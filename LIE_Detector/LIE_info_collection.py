from Config import api_key, base_url, projectPath
from data_flow import data_flow_analysis_init, LIE_propagation_analysis
#from LIE_Detector_Agent import ConstructAgent
def LIE_info_collection(projectPath):
    llm_funcs, llm_class = data_flow_analysis_init(projectPath)
    print("llm_funcs", llm_funcs)
    target_func_list = ["openai"]
    for each_func in target_func_list:
        result_code_snippets = LIE_propagation_analysis(each_func, llm_class)
        if (result_code_snippets!=[]):
            #t_path, t_code = result_code_snippets
            #print(f"Collected {len(t_path)} paths")
            '''for curi, each_path in enumerate(t_path):
                print("each_path", each_path)
                print("curi", curi)
                print("collected code", t_code[curi])'''
            '''LLM_code_snippets = result_code_snippets[0]
            API_code_snippets = result_code_snippets[1]
            check_process_code_snippets = result_code_snippets[2]
            a = input("hold on")
            c_t_agent = ConstructAgent(api_key=api_key, base_url=base_url)
            param_list = {"LLM_code_snippets": LLM_code_snippets, "API_code_snippets": API_code_snippets,
                          "check_process_code_snippets": check_process_code_snippets, "api_key": api_key, "base_url": base_url}
            result_test_case = c_t_agent.decision_module(param_list, stream=True)'''
            return result_code_snippets
        else:
            print("No result_code_snippets")
    return None

#LIE_info_collection(projectPath)