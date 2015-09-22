import os
import re
import json
from collections import defaultdict



class EvalHelper():
    def _evaluate_variable(self, variable, item=None):
        if isinstance(variable, str) or isinstance(variable, unicode):
            if variable.startswith("node["):
                tokens_unprocessed = re.findall('\[([^\[]*)\]', variable)
                tokens_processed = list()
                for token_un in tokens_unprocessed:
                    if token_un.startswith(":"):
                        token_un = token_un[1:]
                    if token_un.startswith("'"):
                        token_un = token_un[1:]
                    if token_un.endswith("'"):
                        token_un = token_un[:-1]
                    tokens_processed.append(token_un)
                try:
                    result_rec_get = self.getFromDict(item, tokens_processed)
                    variable = result_rec_get
                except: pass
        return variable

    def getFromDict(self, dataDict, mapList):
            return reduce(lambda d, k: d[k], mapList, dataDict)

    def setInDict(self, dataDict, mapList, value):
        self.getFromDict(dataDict, mapList[:-1])[mapList[-1]] = value

    def reevaluate(self, orig_collection, item=None):
        new = {}
        for key, value in orig_collection.items():
            if isinstance(value, dict):
                new[key] = self.reevaluate(value, item=item)
            elif isinstance(value, str) or isinstance(value, unicode):
                new[key] = self._evaluate_variable(value, item=item)
            else:
                new[key] = value
        return new

    def _merge_collection(self, a, b, path=None, evaluate=False, item=None):
        "merges b into a"
        if path is None:
            path = []
        for key in b:
            if key in a:
                if isinstance(a[key], dict) and isinstance(b[key], dict):
                    self._merge_collection(a[key], b[key], path + [str(key)], evaluate=evaluate, item=item)
                elif a[key] == b[key]:
                    pass
                else:
                    a[key] = b[key]
            else:
                if evaluate:
                    a[key] = self._evaluate_variable(b[key], item=item)
                else:
                    a[key] = b[key]
        if evaluate:
            a = self.reevaluate(a, item=item)
        return a


class ConfigurationImporter():
    def __init__(self):
        pass

    def get_attributes_from_folder(self, cookbooks_directory):
        rootdir = cookbooks_directory
        files_to_process = []
        for subdir, dirs, files in os.walk(rootdir):
            for file in files:
                if "/attributes" in subdir:
                        files_to_process.append(subdir + '/' + file)

        node_elements = []
        for file in files_to_process:
            with open(file, 'r') as f:
                for line in f:
                    result = re.findall('default(.*)', line)
                    for element in result:
                        node_elements.append(element)

        token_collection = []
        for node_element in node_elements:
            node_element_new = node_element[node_element.find('['):]
            tokens_part = node_element_new.split("=")[0]
            tokens = re.findall('\[([^\[]*)\]', tokens_part)
            values_match = re.findall('=.*', node_element_new)
            if len(values_match) > 0:
                value = values_match[0]
            else:
                continue
            if value.startswith(" "):
                value = value[1:]
            if value.startswith("="):
                value = value[1:]
            if value.startswith(" "):
                value = value[1:]
            if value.startswith("'"):
                value = value[1:]
            if value.endswith("'"):
                value = value[:-1]
            if len(tokens) > 0:
                token_collection.append({"tokens" : tokens, "value": value})

        elements_to_create = []
        for tokens_to_process in token_collection:
            list_tokens = ""
            first = True
            for token in tokens_to_process["tokens"]:
                key_str = token.replace("'", "")
                key_str = key_str.replace(":", "")
                if first:
                    list_tokens += key_str
                    first = False
                else:
                    list_tokens += "==>" + key_str
            elements_to_create.append({"path" : list_tokens, "value" : tokens_to_process["value"]})

        # Creating common structure
        common_structure = defaultdict(dict)
        for element in elements_to_create:
            new_structure = defaultdict(dict)
            reference_structure = new_structure
            tokens_list = element["path"].split("==>")
            for token in tokens_list:
                reference_structure[token] = {}
                reference_structure = reference_structure[token]
            common_structure = EvalHelper()._merge_collection(common_structure, new_structure, evaluate=False)

        # Populating common structure with default values
        for element in elements_to_create:
            new_structure = defaultdict(dict)
            reference_structure = new_structure
            tokens_list = element["path"].split("==>")
            EvalHelper().setInDict(common_structure,tokens_list,element["value"])
        return common_structure

    def enum_keys_from_template(self, template_lines):
        for line in template_lines:
            result = re.findall('\{\{getv \"([^{^\n]*)\"\}\}', line)
        return result

    def get_etcd_view(self, data):
        out_collection = []
        def myprint(d,path=None):
            for k, v in d.iteritems():
                if isinstance(v, dict):
                    if not path:
                        path=""
                    myprint(v, path=path+"/"+k)
                else:
                    if not path:
                        path=""
                    out_collection.append({"key": "{0}/{1}".format(path,k), "value": v, "dir" : False, "ttl" : None})
        myprint(data)
        return out_collection

    def merge_environment(self, initial_structure, environment_data):
        common_structure = EvalHelper()._merge_collection(initial_structure, environment_data, evaluate=False)
        common_structure = EvalHelper()._merge_collection(defaultdict(dict), common_structure, evaluate=True, item=common_structure)
        return common_structure
