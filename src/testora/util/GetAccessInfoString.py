import re
from testora.util.Logs import append_event, Event, CallGraphEvent


def prepare_call_info(pr):
    # 0: overall: from the perspective of forming the call graph info str
    call_graph_info_str = ""        
    info_public_and_private = ""
    offical_special_method_guidelines = {}

    # for special methods
    offical_special_methods_file = "src/testora/util/special_methods.txt"
    with open(offical_special_methods_file, "r") as f:
        offical_special_methods_tmp = f.readlines()
        offical_special_method_guidelines_tmp = [{methods.split(" ", 1)[0]: methods} for methods in offical_special_methods_tmp if methods.startswith("__")]
        offical_special_method_guidelines = {}
        for d in offical_special_method_guidelines_tmp:
            offical_special_method_guidelines.update(d)


    # 1: for public functions
    patterns = [r"To trigger changed method '([^']+)', which is a special method of the class", 
            r"To trigger entry function '([^']+)', which is a special method of the class"]
    import_lines_info = ""
    for label, import_lines in pr.public_func_imports.items():
        import_lines_info_sub = ""
        if import_lines:
            # add hints for special method entry functions.
            for idx, imline in enumerate(import_lines):
                if "is a special method of the class" in imline:
                    # Example: To trigger changed method '{fully_qulified_name}' ...
                    # From file PullRequest.py
                    special_method = ""
                    for pattern in patterns:
                        fully_qulaified_name_tmp = re.search(pattern, imline)
                        if fully_qulaified_name_tmp:
                            fully_qulaified_name = fully_qulaified_name_tmp.group(1)
                            special_method = fully_qulaified_name.rsplit(".", 1)[1]
                            break
                    try: # ideally should always exists, no errors
                        special_method_explaination = offical_special_method_guidelines[special_method]
                        # update imline
                        import_lines[idx] = f"{imline}\nHints: {special_method_explaination}.\n"
                    except:
                        append_event(Event(pr_nb=pr.number, message=f"Fail to get hints for private function: {fully_qulaified_name}"))

            info = "\n".join(import_lines)
            # here the old and new labeled info exists only when some functions/classes have been affected in only one version, there is no confusing info.
            if label == "common":
                import_lines_info_sub = f"The following information is available for both the old and the new versions of code:\n{info}"
            elif label == "old":
                import_lines_info_sub = f"The following information is available only for the old code version:\n{info}" 
            else:
                import_lines_info_sub = f"The following information is available only for the new code version:\n{info}"
            
            import_lines_info += f"{import_lines_info_sub}\n"
        
    if import_lines_info:
        info_public_and_private = (f"For each affected public function, the following lists the available ways to access it. "
            f"Refer to the class information below and the given changed function body above to check how to initialize the relevant classes and to check how to access the function, if any.\n"
        )
            
        info_public_and_private += f"\n{import_lines_info}\n"

    # 2: for private functions
    # form the info about call graph
    # each of them are a triple list: pr_level[function_level[path level]]
    call_graph_info_str_funcs = ""
    call_graph_info_str_prefix = (
        "For each affected non-public function, the following lists the available ways to access it, if any. "
        "Each way specifies which function to call, along with its signature and docstring (if available), to guide how it should be used. "
        "Refer to the class information below to check how to initialize the relevant classes, if any.\n\n"
    ) # to make sure provide only available info to the prompt

    for func_name, cg_path_func_level in pr.call_graph_paths_k.items(): # func_name is fully qualified 
        call_graph_info_str_function_level = ""
        if cg_path_func_level:
            for label, cg_paths in cg_path_func_level.items():
                call_graph_info_str_sub = ""
                if cg_paths:
                    for i, cg in enumerate(cg_paths):
                        sig_doc = pr.signatures_docstrings_k[func_name][label][i]
                        imports = pr.imports_k[func_name][label][i]
                        '''
                        two options:
                        * provide the entire call graph path to the prompt
                        * provide only the entry function (Prefer)
                        '''
                        if cg[0].startswith("__") and cg[0].endswith("__"):
                            try: # ideally should always exists
                                special_method_explaination = offical_special_method_guidelines[cg[0]]
                                call_graph_info_str_sub += f"Method #{i}: by triggering special method '{cg[0]}' of the following imported class\n"
                                call_graph_info_str_sub +=  f"Hints: {special_method_explaination}.\n"
                            except:
                                append_event(Event(pr_nb=pr.number, message=f"Fail to get hints for private function: {cg[0]}"))
                        else:
                            call_graph_info_str_sub += f"Method #{i}: by calling function '{cg[0]}'\n"
                        if imports:
                            call_graph_info_str_sub += f"{imports}" # import info endswith "\n", refer to PullRequest.py
                        if sig_doc:
                            call_graph_info_str_sub += f"{sig_doc}\n"
                    
                    if call_graph_info_str_sub:
                        if label == "common":
                            call_graph_info_str_sub = f"The following information is available for both the old and the new versions of code:\n{call_graph_info_str_sub}"
                            # if common info exists for a changed function, only provide it to avoid any confusion from the one-version-info
                            # option 1: get all the information, but only privide common to prompts
                            call_graph_info_str_function_level += call_graph_info_str_sub
                            break 
                            # option 2: get common_info and stop in PullRequest.py get_union_call_graph
                        elif label == "old":
                            call_graph_info_str_sub = f"The following information is available only for the old code version:\n{call_graph_info_str_sub}" 
                        else:
                            call_graph_info_str_sub = f"The following information is available only for the new code version:\n{call_graph_info_str_sub}"
                        
                        call_graph_info_str_function_level += call_graph_info_str_sub

            if call_graph_info_str_function_level:
                call_graph_info_str_function_level = f"To access the changed function {func_name}:\n\n{call_graph_info_str_function_level}"
                call_graph_info_str_funcs += call_graph_info_str_function_level
    
    if call_graph_info_str_funcs:
        call_graph_info_str = call_graph_info_str_prefix + call_graph_info_str_funcs 
        info_public_and_private += f"{call_graph_info_str}\n"

    # 3: all relevant classes
    if pr.class_hover_texts:
        info_public_and_private += f"The following shows the signatures and docstrings of the relevant classes, which can be used as a reference when initializing them.\n"
        info_public_and_private += f"Long docstrings are truncated, with an ellipsis (...) indicating omitted content.\n"
        # add the relevant class hover texts
        # for module_endswith_class, hover_text in pr.class_hover_texts.items():
        info_public_and_private += "\n".join(pr.class_hover_texts)

    append_event(CallGraphEvent(pr_nb=pr.number, message=f"Call graph ({len(info_public_and_private)})", content=info_public_and_private))        
    return info_public_and_private
    # exit()

def prepare_selected_call_info(pr, uncovered_changed_ful_qua_funcs_old, uncovered_changed_ful_qua_funcs_new): # for feedback rounds
    # get common funcs and uiques
    uncovered_funcs_common = list(set(uncovered_changed_ful_qua_funcs_old).intersection(uncovered_changed_ful_qua_funcs_new))
    uncovered_funcs_only_for_old = [func for func in uncovered_changed_ful_qua_funcs_old if func not in uncovered_changed_ful_qua_funcs_new]
    uncovered_funcs_only_for_new = [func for func in uncovered_changed_ful_qua_funcs_new if func not in uncovered_changed_ful_qua_funcs_old]

    call_graph_info_str = ""        
    info_public_and_private = ""
    offical_special_method_guidelines = {}

    # for special methods
    offical_special_methods_file = "src/testora/util/special_methods.txt"
    with open(offical_special_methods_file, "r") as f:
        offical_special_methods_tmp = f.readlines()
        offical_special_method_guidelines_tmp = [{methods.split(" ", 1)[0]: methods} for methods in offical_special_methods_tmp if methods.startswith("__")]
        offical_special_method_guidelines = {}
        for d in offical_special_method_guidelines_tmp:
            offical_special_method_guidelines.update(d)

    # 1: for public functions
    common_info = ""
    info_only_for_old = ""
    info_only_for_new = ""

    patterns = [r"To trigger changed method '([^']+)', which is a special method of the class", 
            r"To trigger entry function '([^']+)', which is a special method of the class",
            r"To access changed function '([^']+)':"]
    
    uncovered_import_lines = []
    import_lines_info = ""
    for __, import_lines in pr.public_func_imports.items():
        if import_lines:
            # add hints for special method entry functions.
            for idx, imline in enumerate(import_lines):
                label = ""
                special_method = ""
                for pattern in patterns:
                    fully_qulaified_name_tmp = re.search(pattern, imline)
                    if fully_qulaified_name_tmp:
                        fully_qulaified_name = fully_qulaified_name_tmp.group(1)
                        if fully_qulaified_name in uncovered_funcs_common:
                            label = "common"
                        elif fully_qulaified_name in uncovered_funcs_only_for_old:
                            label = "old"
                        elif fully_qulaified_name in uncovered_funcs_only_for_new:
                            label = "new"

                        special_method = fully_qulaified_name.rsplit(".", 1)[1]
                        break
                try: # ideally should always exists, no errors
                    if special_method.startswith("__"): 
                        special_method_explaination = offical_special_method_guidelines[special_method]
                        # update imline
                        import_lines[idx] = f"{imline}\nHints: {special_method_explaination}.\n"
                except:
                    append_event(Event(pr_nb=pr.number, message=f"Fail to get hints for private function: {fully_qulaified_name}"))

                if label:
                    uncovered_import_lines.append(imline) # to indicate all related classes for later collocting class hover text
                
                if label == "common":
                    if not common_info:
                        common_info = f"The following information is available for both the old and the new versions of code:\n"
                    common_info += f"{imline}\n"
                elif label == "old":
                    if not info_only_for_old:
                        info_only_for_old = f"The following information is available only for the old code version:\n"
                    info_only_for_old += f"{imline}\n"
                elif label == "new":
                    if not info_only_for_new:
                        info_only_for_new = f"The following information is available only for the new code version:\n"
                    info_only_for_new += f"{imline}\n"   
    
    to_connnect_tmp = [common_info, info_only_for_old, info_only_for_new]
    to_connnect = [s for s in to_connnect_tmp if s]
    import_lines_info = "\n".join(to_connnect)
    if import_lines_info:
        info_public_and_private = (f"For each uncovered affected public function, the following lists the available ways to access it. "
            f"Refer to the class information below and the given changed function body above to check how to initialize the relevant classes and to check how to access the function, if any.\n"
        )
            
        info_public_and_private += f"\n{import_lines_info}\n"

    # 2: for private functions
    # form the info about call graph
    # each of them are a triple list: pr_level[function_level[path level]]

    call_graph_info_str_funcs = ""

    for func_name, cg_path_func_level in pr.call_graph_paths_k.items(): # func_name is fully qualified 
        # mark the uncovered funcs
        uncovered_label = ""
        if func_name in uncovered_funcs_common:
            uncovered_label = "common"
        elif func_name in uncovered_changed_ful_qua_funcs_old:
            uncovered_label = "old"
        elif func_name in uncovered_changed_ful_qua_funcs_new:
            uncovered_label = "new"

        if uncovered_label:
            call_graph_info_str_function_level = ""
            if cg_path_func_level:
                for label, cg_paths in cg_path_func_level.items():
                    call_graph_info_str_sub = ""
                    if cg_paths:
                        for i, cg in enumerate(cg_paths):
                            sig_doc = pr.signatures_docstrings_k[func_name][label][i]
                            imports = pr.imports_k[func_name][label][i]
                            uncovered_import_lines.append(imports.strip())

                            if cg[0].startswith("__") and cg[0].endswith("__"):
                                try: # ideally should always exists
                                    special_method_explaination = offical_special_method_guidelines[cg[0]]
                                    call_graph_info_str_sub += f"Method #{i}: by triggering special method '{cg[0]}' of the following imported class\n"
                                    call_graph_info_str_sub +=  f"Hints: {special_method_explaination}.\n"
                                except:
                                    append_event(Event(pr_nb=pr.number, message=f"Fail to get hints for private function: {cg[0]}"))
                            else:
                                call_graph_info_str_sub += f"Method #{i}: by calling function '{cg[0]}'\n"
                            if imports:
                                call_graph_info_str_sub += f"{imports}" # import info endswith "\n", refer to PullRequest.py
                            if sig_doc:
                                call_graph_info_str_sub += f"{sig_doc}\n"
                
                        if call_graph_info_str_sub:
                            if uncovered_label == "common":
                                call_graph_info_str_sub = f"The following information is available for both the old and the new versions of code:\n{call_graph_info_str_sub}"
                                # if common info exists for a changed function, only provide it to avoid any confusion from the one-version-info
                                # option 1: get all the information, but only privide common to prompts
                                call_graph_info_str_function_level += call_graph_info_str_sub
                                break 
                                # option 2: get common_info and stop in PullRequest.py get_union_call_graph
                            elif uncovered_label == "old":
                                call_graph_info_str_sub = f"The following information is available only for the old code version:\n{call_graph_info_str_sub}" 
                            elif uncovered_label == "new":
                                call_graph_info_str_sub = f"The following information is available only for the new code version:\n{call_graph_info_str_sub}"
                            
                            call_graph_info_str_function_level += call_graph_info_str_sub

                if call_graph_info_str_function_level:
                    call_graph_info_str_function_level = f"To access the changed function {func_name}:\n\n{call_graph_info_str_function_level}"
                    call_graph_info_str_funcs += call_graph_info_str_function_level
        
    if call_graph_info_str_funcs:
        call_graph_info_str_prefix = (
            "For each uncovered affected non-public function, the following lists the available ways to access it, if any. "
            "Each way specifies which function to call, along with its signature and docstring (if available), to guide how it should be used. "
            "Refer to the class information below to check how to initialize the relevant classes, if any.\n\n"
        ) # to make sure provide only available info to the prompt

        call_graph_info_str = call_graph_info_str_prefix + call_graph_info_str_funcs 
        info_public_and_private += f"{call_graph_info_str}\n"

    # 3: all relevant classes
    if uncovered_import_lines:
        classes_str = ""
        # add the relevant class hover texts
        uncover_related_classes = set([im.split(" import ")[0].split("from ")[1] for im in uncovered_import_lines])

        for c in uncover_related_classes:
            try:
                classes_str += f"\n{pr.class_hover_texts_dict[c]}"
            except:
                pass
        
        if classes_str:
            info_public_and_private += f"The following shows the signatures and docstrings of the relevant classes, which can be used as a reference when initializing them.\n"
            info_public_and_private += f"Long docstrings are truncated, with an ellipsis (...) indicating omitted content.\n"
            info_public_and_private += f"{classes_str}"

    append_event(CallGraphEvent(pr_nb=pr.number, message=f"Selected call graph ({len(info_public_and_private)})", content=info_public_and_private))        
    return info_public_and_private
    # exit()