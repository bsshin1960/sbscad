import numpy as np

missing_aliases = {
    'bool8': 'bool_', 'int0': 'intp', 'uint0': 'uintp', 'float0': 'float64',
    'complex0': 'complex128', 'float_': 'float64', 'complex_': 'complex128',
    'int_': 'int32', 'uint_': 'uint32', 'longfloat': 'longdouble',
    'longcomplex': 'clongdouble', 'singlecomplex': 'complex64',
    'cfloat': 'complex128', 'cdouble': 'complex128', 'clongfloat': 'clongdouble',
    'unicode_': 'str_', 'str0': 'str_', 'bytes0': 'bytes_', 'void0': 'void',
    'object0': 'object_', 'string_': 'bytes_', 'unicode_': 'str_'
}

for k, v in missing_aliases.items():
    if not hasattr(np, k):
        setattr(np, k, getattr(np, v, object))
