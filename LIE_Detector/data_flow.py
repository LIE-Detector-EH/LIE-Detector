import ast
from Config import func2ast_path, call_graph_path, multi_defined_func_dict_path, llm_funcs_path, defined_func_set_path
from storage_utils import load_dict_from_file, load_call_graph, load_variable_from_file
from code_analyzer import bcg_init
from tools import has_intersection
import astor

analysised_set = None
total_class_list = None

class VariablePropagationVisitor(ast.NodeVisitor):#Trace func in a single function
    def __init__(self):
        self.traced_var_set = set()
        self.traced_arg = None#If the function is traced by arg, this is a index
        self.trace_flag = False#whether to trace the return value of the current function
        self.other_func = []#Other function need to trace
        self.traced_code_snippets = []#related code snippets
        self.traced_func_name = None
        #self.traced_search_name = None
        self.func_def_snippets = None
        self.cur_lineno = None
        self.entire_func = None#save the __init__
        self.try_start = None
        self.try_end = None
        self.try_need_save = False#If this is true, the try catch block need to be saved
        self.visited_call_set = set()#to collect third party function call

    def init_target(self, traced_func_name, traced_arg, func_def_snippets, cur_lineno, trace_flag):
        self.traced_func_name = traced_func_name
        self.traced_arg = traced_arg
        #self.traced_search_name = traced_func_name.split(".")[-1]
        self.func_def_snippets = func_def_snippets
        self.cur_lineno = cur_lineno
        self.trace_flag = trace_flag

    def output_traced_code_snippets(self):
        ans = []
        if (self.entire_func):
            ans.append(self.entire_func)
        self.traced_code_snippets.sort()
        for code_line in self.traced_code_snippets:
            ans.append(self.func_def_snippets[code_line-self.cur_lineno+1])
            #self.cur_lineno started with 1,code line started with 0
        return ans

    def visit_Try(self, node):
        self.try_start = node.lineno
        self.try_end = node.end_lineno

        print("visit_Try", self.try_start, self.try_start)
        self.generic_visit(node)
        if (self.try_need_save):
            print("Try Catch Saved")
            for eachline in range(self.try_start, self.try_end+1):
                self.add_to_traced_code_snippets(eachline)
        self.try_need_save = None
        self.try_start = None
        self.try_end = None

    def visit_FunctionDef(self, node):
        global total_class_list
        #print("visit_FunctionDef")
        #self.debug_output_line(node.lineno)
        if (node.name == "__init__"):
            self.entire_func = astor.to_source(node)

        arg_num = len(node.args.args)
        if (self.traced_arg!=None):
            offset = 0
            if (node.args and arg_num>=1):
                print("node.args.args[0]", node.args.args[0].arg)
                first_arg = self.get_target_variables(node.args.args[0])
                print("first_arg", first_arg)
                if (len(first_arg) == 1 and first_arg[0] == "self"):
                    #self.traced_arg+=1
                    offset = 1
            else:
                print("Error! arg index is not exisit")
            for each_index in self.traced_arg:
                each_index+=offset
                if (each_index>=arg_num):
                    print("Error! arg index is exceed limit")
                else:
                    arg_list = self.get_target_variables(node.args.args[each_index])
                    print("target arg_list", arg_list)
                    arg_set = set(arg_list)
                    self.traced_var_set = self.traced_var_set | arg_set
                    #self.traced_var_set.add(node.args.args[each_index])
                    print("Trace args:", arg_list)

        self.generic_visit(node)
    def add_to_traced_code_snippets(self, lineno):
        self.try_need_save = True
        if ((lineno - 1) not in self.traced_code_snippets):
            self.traced_code_snippets.append(lineno - 1)
            #print("save code snippets", self.func_def_snippets[lineno - self.cur_lineno])

    def visit_For(self, node):
        for_iter_set = set(self.get_target_variables(node.iter))
        if (not for_iter_set.isdisjoint(self.traced_var_set)):#isdisjoint means intersection is empty
            for_target_list = self.get_target_variables(node.target)
            print("Add for_target_list", for_target_list)
            for_target_set = set(for_target_list)
            self.traced_var_set = self.traced_var_set | for_target_set
            self.add_to_traced_code_snippets(node.lineno)
        self.generic_visit(node)

    def visit_If(self, node):
        print("Visit_If")
        if_var_list = self.get_target_variables(node.test)
        self.debug_output_line(node.lineno)
        print("if_var_list", if_var_list)
        if_var_set = set(if_var_list)
        if (not self.traced_var_set.isdisjoint(if_var_set)):
            self.add_to_traced_code_snippets(node.lineno)
            print("Added the If branch code")
        self.generic_visit(node)

    def process_assign_node(self, node, type):
        # Only care about assignment with function calls on the right side
        add_flag = False
        only_add_code_flag = False
        if isinstance(node.value, ast.Call):
            # Get the function being called (targetfun)
            called_func = self.get_called_function(node.value)
            # print("In assign funcall", called_func, self.traced_func_name)
            if (called_func and self.is_target_func(called_func)):
                add_flag = True

            for arg_index, arg in enumerate(node.value.args):
                print("Assign 调用参数是：", arg_index, arg)
                self.debug_output_line(node.lineno)
                # self.arg_trace(arg, node.lineno)
                call_arg = self.get_target_variables(arg)
                call_arg_set = set(call_arg)

                if (not call_arg_set.isdisjoint(self.traced_var_set)):
                    add_flag = True
                    print("visit_Assign debug_output_line")
                    self.debug_output_line(node.lineno)
            else:
                right_name_set = set()
                arg_set = None
                for args in node.value.args:
                    arg_set = set(self.get_target_variables(args))
                    right_name_set = right_name_set | arg_set
                if (not right_name_set.isdisjoint(self.traced_var_set)):
                    add_flag = True
                    # print("add_flag argset", arg_set)
                    # print("add_flag right_name_set", right_name_set)
        else:
            right_name_set = set(self.get_target_variables(node.value))
            if (not right_name_set.isdisjoint(self.traced_var_set)):
                add_flag = True

            if (type == "Assign"):
                if (node.targets):
                    for target in node.targets:
                        left_name_set = set(self.get_target_variables(target))
                        if (not left_name_set.isdisjoint(self.traced_var_set)):
                            only_add_code_flag = True
                            print("Assign add_flag assign match self.traced_var_set", self.traced_var_set)
                            break
            else:
                left_name_set = set(self.get_target_variables(node.target))
                if (not left_name_set.isdisjoint(self.traced_var_set)):
                    print("AnnAssign add_flag assign match self.traced_var_set", self.traced_var_set)
                    only_add_code_flag = True
                # print("add_flag assign match self.traced_var_set", self.traced_var_set)
                # print("add_flag assign match right_name_set", right_name_set)

        if (add_flag):
            print("Assign added")
            self.debug_output_line(node.lineno)
            left_list = []
            if (type == "Assign"):
                for target in node.targets:
                    left_list.extend(self.get_target_variables(target))
                print("left_list", left_list)
            else:
                left_list.extend(self.get_target_variables(node.target))
            left_name_set = set(left_list)
            self.traced_var_set = self.traced_var_set | left_name_set  # adding new variables to trace
            self.add_to_traced_code_snippets(node.lineno)
            print("self.traced_var_set", self.traced_var_set)

        if (only_add_code_flag):
            print("Only add code flag")
            self.debug_output_line(node.lineno)
            self.add_to_traced_code_snippets(node.lineno)

    def visit_Assign(self, node):
        print("visit_Assign")
        self.debug_output_line(node.lineno)

        self.process_assign_node(node, "Assign")

        self.generic_visit(node)

    def visit_AnnAssign(self, node):
        print("visit_AnnAssign")
        self.debug_output_line(node.lineno)

        self.process_assign_node(node, "AnnAssign")

        self.generic_visit(node)

    def visit_Call(self, node):
        print("visit_Call")
        self.debug_output_line(node.lineno)
        called_func = self.get_called_function(node)

        #print("visit_Call func", called_func)
        #print("self.traced_func_name", self.traced_func_name)
        if (called_func and self.is_target_func(called_func)):
            self.add_to_traced_code_snippets(node.lineno)
            search_name = called_func.split(".")[-1]
            self.visited_call_set.add(search_name)

        tar_arg_index = []

        for arg_index, arg in enumerate(node.args):
            #self.arg_trace(arg, node.lineno)
            call_arg = self.get_target_variables(arg)
            call_arg_set = set(call_arg)

            if (not call_arg_set.isdisjoint(self.traced_var_set)):
                self.add_to_traced_code_snippets(node.lineno)
                print("Traced Call arg:", call_arg)
                tar_arg_index.append(arg_index)

                search_name = called_func.split(".")[-1]
                self.visited_call_set.add(search_name)

        if (tar_arg_index!=[]):
            print("visit_Call add other func", called_func, tar_arg_index)
            self.other_func.append([called_func, tar_arg_index])

            search_name = called_func.split(".")[-1]
            self.visited_call_set.add(search_name)

        self.generic_visit(node)

    def debug_output_line(self, lineno):
        print(self.func_def_snippets[lineno - self.cur_lineno])

    def visit_Return(self, node):
        print("Visit Return")
        print("self.traced_var_set", self.traced_var_set)
        #print("visit_Return var", self.traced_var_set)
        #print("visit_Return func", self.traced_func_name)
        return_values = []
        #print("visit_Return node")
        self.debug_output_line(node.lineno)
        #print("visit_Return node.value", node.value)
        if isinstance(node.value, ast.Call):
            called_func = self.get_called_function(node.value)
            #print("visit_Return func Call", called_func)
            if (called_func and self.is_target_func(called_func)):
                #print("Return yes")
                self.set_trace_flag(node.lineno)

                print("visit_Return Saved", called_func)
        else:
            print("Return analysis")
            if isinstance(node.value, ast.Tuple):
                print("Tuple")

                for elt in node.value.elts:
                    #print("elt", elt)
                    return_values.extend(self.get_target_variables(elt))
            else:

                print("Single")
                return_values = self.get_target_variables(node.value)
            print("return_values", return_values)
            return_set = set(return_values)
            if (not return_set.isdisjoint(self.traced_var_set)):
                print("visit_Return Saved")
                self.set_trace_flag(node.lineno)
                #print("visit_Return Saved", called_func)

        '''if isinstance(node.value, ast.Name) and node.value.id == self.variable_name:
            self.trace_flag = True
            if ((node.lineno - 1) not in self.traced_code_snippets):
                self.traced_code_snippets.append(node.lineno - 1)
        '''
        self.generic_visit(node)

    def arg_trace(self, node, lineno):
        tv_list = self.get_target_variables(node)
        tvset = set(tv_list)
        if (not self.traced_var_set.isdisjoint(tvset)):
            self.add_to_traced_code_snippets(lineno)
            print("var_trace", tv_list)
    def set_trace_flag(self, lineno):
        self.trace_flag = True
        self.add_to_traced_code_snippets(lineno)

    def get_called_function(self, call_node):
        if isinstance(call_node.func, ast.Name):
            return call_node.func.id  # Direct function call like targetfun()
        elif isinstance(call_node.func, ast.Attribute):
            # Handle calls like module.targetfun() or self.targetfun()
            return call_node.func.attr
        return None

    def is_target_func(self, func_name):
        ast_name_list = get_ast_name_list(func_name)
        if self.traced_func_name == None:
            return False
        if self.traced_func_name in ast_name_list:
            return True
        return False

    def get_target_variables(self, target):#analysis complex variables like a, a.b, a[b]
        variables = []
        if isinstance(target, str):
            variables.append(target)
        if isinstance(target, ast.Name):
            # Simple variable assignment (e.g., var = targetfun())
            variables.append(target.id)

        elif isinstance(target, ast.Attribute):
            # Attribute assignment (e.g., a.b = targetfun())
            #print("target.attr", type(target.attr))
            variables.append(f"{" ".join(self.get_target_variables(target.value))}.{" ".join(self.get_target_variables(target.attr))}")

        elif isinstance(target, ast.Subscript):
            # Subscript assignment (e.g., a[b] = targetfun())
            #variables.append(f"{target.value.id}[{ast.dump(target.slice)}]")
            variables.extend(self.get_target_variables(target.value))

        elif isinstance(target, ast.BinOp):
            # Handle binary operations (e.g., a + b)
            variables.extend(self.get_target_variables(target.left))  # Process left operand
            variables.extend(self.get_target_variables(target.right))  # Process right operand

        elif isinstance(target, ast.UnaryOp):
            # Handle unary operations (e.g., -a)
            variables.extend(self.get_target_variables(target.operand))  # Process operand

        elif isinstance(target, ast.Tuple):
            for element in target.elts:
                variables.extend(self.get_target_variables(element))

        elif isinstance(target, ast.Compare):
            variables.extend(self.get_target_variables(target.left))
            for comp in target.comparators:
                variables.extend(self.get_target_variables(comp))

        elif isinstance(target, ast.arg):
            variables.append(target.arg)
        elif isinstance(target, ast.arguments):
            for arg in target.args:
                variables.append(arg.arg)

        return variables

def data_flow_analysis_init(projeat_path):
    global func_dict, call_graph, multi_defined_func_dict, defined_func_set
    bcg_init(projeat_path)#save call_graph and func_dict
    func_dict = load_dict_from_file(func2ast_path)
    call_graph = load_call_graph(call_graph_path)
    multi_defined_func_dict = load_dict_from_file(multi_defined_func_dict_path)
    defined_func_set = load_dict_from_file(defined_func_set_path)
    llm_funcs, llm_class = load_variable_from_file(llm_funcs_path)
    return llm_funcs, llm_class


def LIE_propagation_analysis(cur_func, llm_class):
    global func_dict, call_graph, multi_defined_func_dict, analysised_set
    global total_class_list

    total_class_list = llm_class
    analysised_set = set()
    print("Starter Func", cur_func)
    LIE_result = analysis_callers(cur_func)
    LIE_Info_Str_List = []
    if (LIE_result):
        path_list, code_list, called_func = LIE_result
        pnum = len(path_list)
        if (pnum != len(code_list)):
            print("Error: LIE_propagation_analysis: path_list and code_list length mismatch")
            return None
        for i in range(pnum):
            tp_list = third_party_func_detection(called_func[i])
            print("tp_list", tp_list)
            if (tp_list==[]):
                print("tp_list empty", path_list[i])
                continue
            LIE_Info_Str = format_traced_info(path_list[i], code_list[i], tp_list[i])
            #a = input("Wait")
            print("LIE_propagation_analysis", i, path_list[i])
            print("LIE_Info_Str\n", LIE_Info_Str)
            if (LIE_Info_Str!=None):
                LIE_Info_Str_List.append(LIE_Info_Str)
        '''for id, item in enumerate(path_list):
            print("LIE_propagation_analysis Path", id)
            for jd, sigf in enumerate(item):
                print("sigfunc", jd, ":", sigf)
                print("------------------------------------Code------------------------------------")
                for each_code in code_list[id][jd]:
                    print(each_code)
                print("------------------------------------Code End------------------------------------")'''
        return LIE_Info_Str_List
    return None

def format_traced_info(traced_path, traced_codes, third_party_funcs):
    output_lines = []
    for func_name, codes in zip(traced_path, traced_codes):
        print()
        output_lines.append(f"Function: {func_name}")
        output_lines.append("Collected Code segments:")
        print("format_traced_info traced_path", func_name)
        print("format_traced_info traced_codes", codes)
        for code in codes:
            output_lines.append(code)
        output_lines.append("----")
    output_lines.append(f"Subsequent API function are more likely in following function: {third_party_funcs}.")
    format_result = "\n".join(output_lines)
    print("format_result", format_result)
    return format_result

def get_ast_name_list(func_name):
    global multi_defined_func_dict, call_graph
    print("get_ast_name_list", func_name)
    func_name = func_name.split(".")[-1]
    ast_name_list = []#transform into ast name
    if (func_name not in multi_defined_func_dict):
        print("LIE_propagation_analysis", func_name, "None in multi_defined_func_dict")
    else:
        ast_name_list = multi_defined_func_dict[func_name]
    if (ast_name_list == []):
        ast_name_list = [func_name]
    print("ast_name_list", ast_name_list)
    return ast_name_list


def third_party_func_detection(called_func_set):
    global defined_func_set
    '''result = []
    for each_func in traced_path:
        search_name = each_func.split(".")[-1]
        if search_name not in defined_func_set:
            result.append(each_func)'''
    print("called_func_set", called_func_set)
    result = list(called_func_set.difference(defined_func_set))
    print("third_party_func_detection", result)
    return result

def analysis_callers(func_name):
    global call_graph, defined_func_set
    print("analysis_callers start", func_name)
    total_traced_path = []
    total_traced_code = []
    total_called_func = []
    #total_tp_list = []#record the list of third party function to guide the selection of subequent API
    ast_name_list = get_ast_name_list(func_name)
    for each_ast_name in ast_name_list:
        if each_ast_name in call_graph:
            caller_list = call_graph.predecessors(each_ast_name)
            print("caller_list of :", each_ast_name)
            #print("Is:", list(caller_list))
            for each_caller in caller_list:
                print("analysis_callers", each_caller, "is caller of", each_ast_name)
                caller_result = analysis_code(each_caller, each_ast_name, None)
                if caller_result:
                    t_path, t_code, c_set = caller_result
                    #t_path, t_code, third_p_list = third_party_func_detection(t_path, t_code)
                    if (len(t_path)!=len(t_code) or len(t_code)!=len(c_set)):
                        print("Error: analysis_callers result doesnt match")
                    if (len(t_path)):
                        total_traced_path.extend(t_path)
                        total_traced_code.extend(t_code)
                        total_called_func.extend(c_set)
                        #total_tp_list.extend(third_p_list)
        else:
            print("Skip", each_ast_name, "since it not in call graph")
    print("analysis_callers total_traced_path", len(total_traced_path), total_traced_path)
    print("total_traced_code", len(total_traced_code), total_traced_code)
    return total_traced_path, total_traced_code, total_called_func

def analysis_code(cur_func, target_func, target_arg_index_list):#TO BFS
    global func_dict, call_graph, analysised_set
    global total_class_list
    """
    Analysis the given function and recursively analyze other functions that call it based on the call graph.
    """
    if (cur_func not in analysised_set):#avoid dupilcate analysis
        analysised_set.add(cur_func)
    else:
        return None
    print("analysis_code start", cur_func)

    current_path = []
    founded_code_snippets = []
    cur_visit_set = set()


    traced_path = []
    traced_code_snippets = []
    visit_set_list = []


    #Load the function AST
    if cur_func not in func_dict:
        print(f"Function {cur_func} not found in the function dictionary.")
        return None

    # Create a visitor to track the variable propagation
    visitor = VariablePropagationVisitor()
    #print("total_class_list", total_class_list)
    for func_ast, func_body, cur_lineno in func_dict[cur_func]:
        print("Analyzing function:", cur_func, "and", target_func)
        t_flag = False
        if (cur_func in total_class_list):
            t_flag = True
            #print("target_func is class method")
        visitor.init_target(target_func, target_arg_index_list, func_body, cur_lineno, t_flag)
        visitor.visit(func_ast)
        sig_func_captured_code = visitor.output_traced_code_snippets()#code List
        founded_code_snippets.append(sig_func_captured_code)
        cur_visit_set = cur_visit_set | visitor.visited_call_set

        current_path.append(cur_func)
        print("Add traced_path", current_path)

    traced_path.append(current_path)
    traced_code_snippets.append(founded_code_snippets)
    visit_set_list.append(cur_visit_set)

    caller_result = None
    extended_path = []
    extended_code_list = []
    extended_set_list = []
    if visitor.trace_flag:
        print("trace_flag is true", cur_func)
        caller_result = analysis_callers(cur_func)

    if (caller_result):
        extended_path, extended_code_list, extended_set_list = caller_result

    if (visitor.other_func != None and visitor.other_func !=[]):
        print("Other func need to analysis")
        for each_func, arg_index in visitor.other_func:
            print("Other func", each_func, arg_index)
            ast_name_list = get_ast_name_list(each_func)
            for each_ast_name in ast_name_list:
                print("each_ast_name", each_ast_name, arg_index)
                other_result = analysis_code(each_ast_name, None, arg_index)
                if (other_result):
                    other_traced_path, other_collected_code_list, other_set_list = other_result
                    extended_path.extend(other_traced_path)
                    extended_code_list.extend(other_collected_code_list)
                    extended_set_list.extend(other_set_list)


    if (extended_code_list!=[]):
        traced_path = full_connect(traced_path, extended_path)
        traced_code_snippets = full_connect(traced_code_snippets, extended_code_list)
        visit_set_list = set_full_connect(visit_set_list, extended_set_list)
    '''if (caller_result):
        caller_traced_path, caller_collected_code_list = caller_result
        traced_path = full_connect(traced_path, caller_traced_path)
        traced_code_snippets = full_connect(traced_code_snippets, caller_collected_code_list)'''
    '''print("Code snippets:", visitor.code_snippets)
    #If found_flag is True, continue analyzing functions that call cur_func
    if visitor.found_flag:
        print(f"Variable found in function '{cur_func}'!")
        #iterate through the call graph to find functions that call cur_func
        for successor in call_graph.successors(cur_func):
            print(f"Analyzing function '{successor}' that calls '{cur_func}'...")
            result = analysis_code(successor, cur_func)
            if result:
                founded_code_snippets.extend(result)'''
    print("traced_path  final", traced_path)
    return traced_path, traced_code_snippets, visit_set_list

def full_connect(list1, list2):
    result = []
    for sublist1 in list1:
        for sublist2 in list2:
            result.append(sublist1 + sublist2)
    return result

def set_full_connect(list1, list2):
    result = []
    for subset1 in list1:
        for subset2 in list2:
            result.append(subset1 | subset2)
    return result


func_dict = None
call_graph = None
multi_defined_func_dict = None
defined_func_set = None

def test():
    test_func = 'foo'
    #analysis_code(test_func)