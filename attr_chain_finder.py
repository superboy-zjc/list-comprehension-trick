# import os

# def clear_builtin_function(bultins: dict):
#   input = bultins.copy()
#   for key in list(input.keys()):
#     if type(input[key]).__name__ == 'builtin_function_or_method':
#       del input[key]
#     elif "class" in str(type(input[key])) and type(input[key]).__module__ == 'builtins':
#       del input[key]
#     elif type(input[key]).__name__ == 'type' and input[key].__module__ == 'builtins':
#       del input[key]
#     elif type(input[key]).__name__ == 'str':
#       del input[key]
#   return input

#   a = clear_builtin_function(__builtins__)
#   b = __builtins__
#   print(a)

import sys
import types
import builtins
from collections import deque

walked_globals = set()


debug = False
def _print_debug(msg):
  if debug:
    print(msg)
def is_primitive_strict(obj):
    return isinstance(obj, (int, float, bool, str, bytes, type(None), complex))
def is_function_or_c_impl(obj):
  if (isinstance(obj, types.FunctionType) or isinstance(obj, types.BuiltinFunctionType) or \
    isinstance(obj, types.BuiltinMethodType) or isinstance(obj, types.MethodType) or \
    isinstance(obj, types.LambdaType) or isinstance(obj, types.WrapperDescriptorType) or \
    isinstance(obj, types.MethodWrapperType) or isinstance(obj, types.MethodDescriptorType) or \
    isinstance(obj, types.ClassMethodDescriptorType) or isinstance(obj, types.MappingProxyType) or \
    isinstance(obj, types.CodeType) or isinstance(obj, types.SimpleNamespace) or \
    isinstance(obj, types.CellType) or isinstance(obj, types.GeneratorType) or \
    isinstance(obj, types.AsyncGeneratorType) or isinstance(obj, types.FrameType) or \
    isinstance(obj, types.GetSetDescriptorType) or isinstance(obj, types.MemberDescriptorType)) and \
    not hasattr(obj, "__globals__"):
    return True
  return False

def sys_finder(to_check, id_to_match, walked=None, sys_matches=None):
  """
    To identify a chain of path towards target object, we have to enumerate each object to find the chain
    For every object, the chain can be from 
      1. the instance object
      2. the object class
  """
  def _extend(a, b):
    a_ = a.copy()
    a_.extend(b)
    return a_
  def _append(a, b):
    a_ = a.copy()
    a_.append(b)
    return a_
  def _check_attr(nodes):
    for attr_name in nodes:
      try:
        attr = getattr(to_check, attr_name)
        if isinstance(attr, (list, tuple, set, deque, frozenset, range, slice)):
          for id, item in enumerate(attr):
            sys_finder(item, id_to_match, walked, _extend(sys_matches, ["."+attr_name, "["+str(id)+"]"]))
        elif isinstance(attr, dict):
          for key, value in attr.items():
            sys_finder(value, id_to_match, walked, _extend(sys_matches, ["."+attr_name, "['"+str(key)+"']"]))
        else:
          sys_finder(attr, id_to_match, walked, _append(sys_matches, "."+attr_name))
      except Exception as e:
        _print_debug(e)
        continue
      
  def _check_item(nodes):
    for p_id, p_item in enumerate(nodes):
      try:
        if isinstance(p_item, (list, tuple, set, deque, frozenset, range, slice)):
          for id, item in enumerate(p_item):
            sys_finder(item, id_to_match, walked, _extend(sys_matches, ["["+str(p_id)+"]", "["+str(id)+"]"]))
        elif isinstance(p_item, dict):
          for key, value in p_item.items():
            sys_finder(value, id_to_match, walked, _extend(sys_matches, ["["+str(p_id)+"]", "['"+str(key)+"']"]))
        else:
          sys_finder(p_item, id_to_match, walked, _append(sys_matches, "["+str(p_id)+"]"))
      except Exception as e:
        _print_debug(e)
        continue
  
  def _check_dict(nodes):
    for p_key, p_value in nodes.items():
      try:
        if isinstance(p_value, (list, tuple, set, deque, frozenset, range, slice)):
          for id, item in enumerate(p_value):
            sys_finder(item, id_to_match, walked, _extend(sys_matches, ["['"+str(p_key)+"']", "["+str(id)+"]"]))
        elif isinstance(p_value, dict):
          for key, value in p_value.items():
            sys_finder(value, id_to_match, walked, _extend(sys_matches, ["['"+str(p_key)+"']", "['"+str(key)+"']"]))
        else:
          sys_finder(p_value, id_to_match, walked, _append(sys_matches, "['"+str(p_key)+"']"))
      except Exception as e:
        _print_debug(e)
        continue
  
  if id(to_check) == id_to_match:
    print(f"[{to_check}] -> access chain : '{''.join(sys_matches)}'")
    if not eval("__builtins__"+''.join(sys_matches)) is sys:
      exit("wrong!")
    
    return sys_matches[-1]
  if id(to_check) in walked:
    return

  walked.add(id(to_check))
  # pass primitive types and function types
  if is_primitive_strict(to_check) or is_function_or_c_impl(to_check) or to_check is object:
    return

  # instance object
  # primitive types: int, float, str, bool, NoneType, bytes, complex
  # C-implemented types (fixed layout): list, tuple, set, dict, deque, frozenset, range, slice
  # don't have __dict__
  if hasattr(to_check, '__globals__'):
    nodes = to_check.__globals__
    if nodes["__file__"] in walked_globals:
      return
    walked_globals.add(nodes["__file__"])
    sys_matches.append(".__globals__")
    _check_dict(nodes)
  elif not hasattr(to_check, '__dict__') and isinstance(to_check, (dict,)):
    nodes = to_check
    _check_dict(nodes)
  elif not hasattr(to_check, '__dict__') and isinstance(to_check, (list, tuple, set, deque, frozenset, range, slice)):
    nodes = to_check
    _check_item(nodes)
  elif not hasattr(to_check, '__dict__'):
    # some object's don't have __dict__
    return
  elif str(type(to_check)).startswith("<class '"):
    nodes = list(to_check.__dict__) + list(to_check.__class__.__dict__)
    _check_attr(nodes)
  else:
    nodes = list(to_check.__dict__)
    _check_attr(nodes)
  
import collections
# test={"__loader__":__builtins__["__loader__"]}
test={"help":__builtins__["help"]}
sys_finder(license, id(sys), set(), [])