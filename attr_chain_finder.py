"""
  Gadget Chain Finder
    Given a target object, find the chain of attribute/item access to reach it
  Currently DFS algorithm. TODO: implement DP algorithm, record the shortest path to the target at each node if possible
  TODO: some function serves as factory function which will yield a new object, which might expose more attrs to finder. we can perform construction of each object to try to expose more
"""
import sys
import types
import builtins
from collections import deque
from collections.abc import Mapping, Sequence, Collection

walked_globals = set()
UNDERSCOPE = "_"
dp = {}

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

def sys_finder(to_check, to_match, walked=None, sys_matches=None, mode="id", underscope=True, key_mode="all"):
  """
    To identify a chain of path towards target object, we have to enumerate each object to find the chain
    For every object, the chain can be from 
      1. the instance object
      2. the object class
    Args:
      mode: 
        "id": in this mode, `to_match` is the `object id, e.x. id(TARGET)` that chained targets own as its attribute
        "attr_name": in this mode, `to_match` is `string` which is part of the attribute name that chained targets own
        TODO: "class-instance": in this mode, `to_match` is the class type that is the type of chained targets
      key_mode:
        "all": getattr / getitem
        "getattr": getattr only
        "getitem": getitem only
  """
  def _extend(a, b):
    a_ = a.copy()
    a_.extend(b)
    return a_
  def _append(a, b):
    a_ = a.copy()
    a_.append(b)
    return a_
  def _check_attr(nodes, key_mode="all"):
    for attr_name in nodes:
      # check underscope mode; pass the attribute that starts with UNDERSCOPE
      if underscope == False and attr_name.startswith(UNDERSCOPE):
        continue
      try:
        attr = getattr(to_check, attr_name)
        if isinstance(attr, (list, tuple, set, deque, frozenset, range, slice)) and key_mode != "getattr":
          for id, item in enumerate(attr):
            sys_finder(item, to_match, walked, _extend(sys_matches, ["."+attr_name, "["+str(id)+"]"]), mode, underscope, key_mode)
        elif isinstance(attr, dict) and key_mode != "getattr":
          for key, value in attr.items():
            sys_finder(value, to_match, walked, _extend(sys_matches, ["."+attr_name, "['"+str(key)+"']"]), mode, underscope, key_mode)
        else:
          sys_finder(attr, to_match, walked, _append(sys_matches, "."+attr_name), mode, underscope, key_mode)
      except Exception as e:
        _print_debug(e)
        continue
      
  def _check_item(nodes, key_mode="all"):
    if key_mode == "getattr":
      return
    for p_id, p_item in enumerate(nodes):
      try:
        if isinstance(p_item, (list, tuple, set, deque, frozenset, range, slice)):
          for id, item in enumerate(p_item):
            sys_finder(item, to_match, walked, _extend(sys_matches, ["["+str(p_id)+"]", "["+str(id)+"]"]), mode, underscope, key_mode)
        elif isinstance(p_item, dict):
          for key, value in p_item.items():
            # check underscope mode
            if underscope == False and str(key).startswith(UNDERSCOPE):
              continue
            sys_finder(value, to_match, walked, _extend(sys_matches, ["["+str(p_id)+"]", "['"+str(key)+"']"]), mode, underscope, key_mode)
        else:
          sys_finder(p_item, to_match, walked, _append(sys_matches, "["+str(p_id)+"]"), mode, underscope, key_mode)
      except Exception as e:
        _print_debug(e)
        continue
  
  def _check_dict(nodes, key_mode="all"):
    if key_mode == "getattr":
      return
    for p_key, p_value in nodes.items():
      # check underscope mode
      if underscope == False and str(p_key).startswith(UNDERSCOPE):
        continue
      try:
        if isinstance(p_value, (list, tuple, set, deque, frozenset, range, slice)):
          for id, item in enumerate(p_value):
            sys_finder(item, to_match, walked, _extend(sys_matches, ["['"+str(p_key)+"']", "["+str(id)+"]"]), mode, underscope, key_mode)
        elif isinstance(p_value, dict):
          for key, value in p_value.items():
            # check underscope mode
            if underscope == False and str(key).startswith(UNDERSCOPE):
              continue
            sys_finder(value, to_match, walked, _extend(sys_matches, ["['"+str(p_key)+"']", "['"+str(key)+"']"]), mode, underscope, key_mode)
        else:
          sys_finder(p_value, to_match, walked, _append(sys_matches, "['"+str(p_key)+"']"), mode, underscope, key_mode)
      except Exception as e:
        _print_debug(e)
        continue
      
  def _collect_attr_keys(obj):
    """Collect attribute keys from the object. From object, its type class or both"""
    res = []
    if hasattr(obj, '__dict__'):
      res.extend(list(obj.__dict__))
    # either slot or dict for maintaining the attrs in python-implemented objs
    elif hasattr(obj, '__slots__'):
      res.extend(list(obj.__slots__))
    else:
      # some pure C implemented object's don't have __dict__ and __slots__
      # and they typically do not have any referents
      import gc
      if len(gc.get_referents(obj)) != 0:
        _print_debug(f"Some special cases we need pay attention on: {obj}")
      # If not return here, the stack will overflow e.x. numpy
      return
    # if not instances of metaclass, counts in class attrs from its parent. TODO: here only consider the first parent, we can cover more
    if str(type(obj)).startswith("<class '") and str(type(obj)) != "<class 'type'>":
      res.extend(list(obj.__class__.__dict__))
    return list(set(res))
  
      
  if underscope == False:
    try:
      if to_check.__name__.startswith("_"):
        return
    except Exception as e:
      # of attribute doesn't have __name__
      pass

  if mode == "id":
    if id(to_check) == to_match:
      print(f"[{to_check}] -> access chain : '{''.join(sys_matches)}'")
      if not eval("__builtins__"+''.join(sys_matches)) is sys:
        exit("wrong!")
      return
  elif mode == "attr_name":
    try:
      if to_match in to_check.__name__:
        print(f"[{to_check.__name__}: {to_check}] -> access chain : '{''.join(sys_matches)}'")
    except Exception as e:
      # of attribute doesn't have __name__
      pass
    
  # avoid duplicated scan by object mem id
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
  # TODO: add __annotations__ check
  if hasattr(to_check, '__globals__'):
    nodes = to_check.__globals__
    try:
      if nodes["__file__"] in walked_globals or underscope == False:
        return
    except Exception as e:
      # some tricky global object doesn't have __file__ e.x. re.functools.update_wrapper.__globals__["_CacheInfo"].__new__.__globals__
      return
    walked_globals.add(nodes["__file__"])
    sys_matches.append(".__globals__")
    _check_dict(nodes, key_mode)
  # TODO: we can replace the following two elifs with isinstance(to_check, (Mapping, Sequence))
  # However, tradeoff is for those user defined Mapping, Sequences, the user defined attributes would be missed
  elif not hasattr(to_check, '__dict__') and isinstance(to_check, (dict,)):
    nodes = to_check
    _check_dict(nodes, key_mode)
  elif not hasattr(to_check, '__dict__') and isinstance(to_check, (list, tuple, set, deque, frozenset, range, slice)):
    nodes = to_check
    _check_item(nodes, key_mode)
  else:
    # Collect attribute keys from the object. From object, its type class or both.
    nodes = _collect_attr_keys(to_check)
    if not nodes:
      return
    _check_attr(nodes, key_mode)

def single_find(module, name):
    try:
      sys_finder(module, to_match=name, walked=set(), sys_matches=[module.__name__], mode="attr_name", underscope=False, key_mode="all")
    except AttributeError as e:
      print(e)
      pass

def single_find_sensitive_id(module):
    try:
      import sys, os
      from os import system
      import traceback
      to_find = [sys, os, system, traceback]
      for item in to_find:
        sys_finder(module, to_match=id(item), walked=set(), sys_matches=[], mode="id", underscope=False, key_mode="all")
    except AttributeError as e:
      print(e)
      pass
  
import collections
# test={"__loader__":__builtins__["__loader__"]}
# test={"help":__builtins__["help"]}
_safe_exceptions = [
    'ArithmeticError',
    'AssertionError',
    'AttributeError',
    'BaseException',
    'BufferError',
    'BytesWarning',
    'DeprecationWarning',
    'EOFError',
    'EnvironmentError',
    'Exception',
    'FloatingPointError',
    'FutureWarning',
    'GeneratorExit',
    'IOError',
    'ImportError',
    'ImportWarning',
    'IndentationError',
    'IndexError',
    'KeyError',
    'KeyboardInterrupt',
    'LookupError',
    'MemoryError',
    'NameError',
    'NotImplementedError',
    'OSError',
    'OverflowError',
    'PendingDeprecationWarning',
    'ReferenceError',
    'RuntimeError',
    'RuntimeWarning',
    'StopIteration',
    'SyntaxError',
    'SyntaxWarning',
    'SystemError',
    'SystemExit',
    'TabError',
    'TypeError',
    'UnboundLocalError',
    'UnicodeDecodeError',
    'UnicodeEncodeError',
    'UnicodeError',
    'UnicodeTranslateError',
    'UnicodeWarning',
    'UserWarning',
    'ValueError',
    'Warning',
    'ZeroDivisionError',
]

_safe_names = [
    '__build_class__',
    'None',
    'False',
    'True',
    'abs',
    'bool',
    'bytes',
    'callable',
    'chr',
    'complex',
    'divmod',
    'float',
    'hash',
    'hex',
    'id',
    'int',
    'isinstance',
    'issubclass',
    'len',
    'oct',
    'ord',
    'pow',
    'range',
    'repr',
    'round',
    'slice',
    'sorted',
    'str',
    'tuple',
    'zip'
]
# for n in _safe_names:
agenta = [
    "math",
    "random",
    "datetime",
    "json",
    "requests",
    "numpy",
    "typing",
]
blutinsss = ['type', 'async_generator', 'int', 'bytearray_iterator', 'bytearray', 'bytes_iterator', 'bytes', 'builtin_function_or_method', 'callable_iterator', 'PyCapsule', 'cell', 'classmethod_descriptor', 'classmethod', 'code', 'complex', 'coroutine', 'dict_items', 'dict_itemiterator', 'dict_keyiterator', 'dict_valueiterator', 'dict_keys', 'mappingproxy', 'dict_reverseitemiterator', 'dict_reversekeyiterator', 'dict_reversevalueiterator', 'dict_values', 'dict', 'ellipsis', 'enumerate', 'float', 'frame', 'frozenset', 'function', 'generator', 'getset_descriptor', 'instancemethod', 'list_iterator', 'list_reverseiterator', 'list', 'longrange_iterator', 'member_descriptor', 'memoryview', 'method_descriptor', 'method', 'moduledef', 'module', 'odict_iterator', 'PickleBuffer', 'property', 'range_iterator', 'range', 'reversed', 'symtable entry', 'iterator', 'set_iterator', 'set', 'slice', 'staticmethod', 'stderrprinter', 'super', 'traceback', 'tuple_iterator', 'tuple', 'str_iterator', 'str', 'wrapper_descriptor', 'GenericAlias', 'anext_awaitable', 'async_generator_asend', 'async_generator_athrow', 'async_generator_wrapped_value', 'coroutine_wrapper', 'InterpreterID', 'managedbuffer', 'method-wrapper', 'SimpleNamespace', 'NoneType', 'NotImplementedType', 'CallableProxyType', 'ProxyType', 'ReferenceType', 'UnionType', 'EncodingMap', 'fieldnameiterator', 'formatteriterator', 'BaseException', 'hamt', 'hamt_array_node', 'hamt_bitmap_node', 'hamt_collision_node', 'keys', 'values', 'items', 'Context', 'ContextVar', 'Token', 'MISSING', 'filter', 'map', 'zip', '_ModuleLock', '_DummyModuleLock', '_ModuleLockManager', 'ModuleSpec', 'BuiltinImporter', 'FrozenImporter', '_ImportLockContext', 'lock', 'RLock', '_localdummy', '_local', '_IOBase', '_BytesIOBuffer', 'IncrementalNewlineDecoder', 'ScandirIterator', 'DirEntry', 'WindowsRegistryFinder', '_LoaderBasics', 'FileLoader', '_NamespacePath', '_NamespaceLoader', 'PathFinder', 'FileFinder', 'Codec', 'IncrementalEncoder', 'IncrementalDecoder', 'StreamReaderWriter', 'StreamRecoder', '_abc_data', 'ABC', 'Hashable', 'Awaitable', 'AsyncIterable', 'Iterable', 'Sized', 'Container', 'Callable', '_wrap_close', 'Quitter', '_Printer', '_Helper', '_TrivialRe', 'DistutilsMetaFinder', 'shim', 'DynamicClassAttribute', '_GeneratorWrapper', 'WarningMessage', 'catch_warnings', 'Loader', 'accumulate', 'combinations', 'combinations_with_replacement', 'cycle', 'dropwhile', 'takewhile', 'islice', 'starmap', 'chain', 'compress', 'filterfalse', 'count', 'zip_longest', 'pairwise', 'permutations', 'product', 'repeat', 'groupby', '_grouper', '_tee', '_tee_dataobject', 'attrgetter', 'itemgetter', 'methodcaller', 'attrgetter', 'itemgetter', 'methodcaller', 'Repr', 'deque', '_deque_iterator', '_deque_reverse_iterator', '_tuplegetter', '_Link', 'partial', '_lru_cache_wrapper', 'KeyWrapper', '_lru_list_elem', 'partialmethod', 'singledispatchmethod', 'cached_property', 'ContextDecorator', 'AsyncContextDecorator', '_GeneratorContextManagerBase', '_BaseExitStack', 'AST', 'auto', 'Enum', 'NodeVisitor', 'Bytecode', 'Pattern', 'Match', 'SRE_Scanner', 'State', 'SubPattern', 'Tokenizer', 'Scanner', 'Untokenizer', 'BlockFinder', '_void', '_empty', 'Parameter', 'BoundArguments', 'Signature', 'Completer']
# allowed_imports = ['False', 'True', 'None', 'abs', 'all', 'any', 'ascii', 'bin', 'bool', 'bytearray', 'bytes', 'callable', 'chr', 'classmethod', 'complex', 'dict', 'divmod', 'enumerate', 'filter', 'float', 'format', 'frozenset', 'hash', 'hex', 'int', 'isinstance', 'issubclass', 'iter', 'len', 'list', 'map', 'max', 'min', 'next', 'object', 'oct', 'ord', 'pow', 'property', 'range', 'repr', 'reversed', 'round', 'set', 'slice', 'sorted', 'staticmethod', 'str', 'sum', 'super', 'tuple', 'zip', '__build_class__', '__name__']
allowed_imports = _safe_exceptions + _safe_names + blutinsss
def find_in_batch():
  import types
  import importlib
  for n in allowed_imports:
    try:
      module = importlib.import_module(n)
    except:
      try:
        module = eval(n)
      except:
        pass
      pass
    # sys_finder(module, id_to_match=id(sys), walked=set(), sys_matches=[module.__name__])
    try:
      sys_finder(module, to_match=id(sys), walked=set(), sys_matches=[module.__name__], mode="id", underscope=True)
      # sys_finder(module, to_match="sys", walked=set(), sys_matches=[module.__name__], mode="attr_name", underscope=False)
    except AttributeError as e:
      print(e)
      pass
find_in_batch()