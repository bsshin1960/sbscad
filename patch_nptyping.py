import os

path = r"C:\Users\SBS\AppData\Roaming\Python\Python314\site-packages\nptyping\typing_.py"
if os.path.exists(path):
    with open(path, "r", encoding="utf-8") as f:
        code = f.read()

    patch_code = """
import numpy as np
if not hasattr(np, 'bool8'): np.bool8 = np.bool_
if not hasattr(np, 'object0'): np.object0 = getattr(np, 'object_', object)
if not hasattr(np, 'int0'): np.int0 = getattr(np, 'intp', int)
if not hasattr(np, 'uint0'): np.uint0 = getattr(np, 'uintp', int)
if not hasattr(np, 'float0'): np.float0 = getattr(np, 'float64', float)
if not hasattr(np, 'complex0'): np.complex0 = getattr(np, 'complex128', complex)
if not hasattr(np, 'float_'): np.float_ = getattr(np, 'float64', float)
if not hasattr(np, 'complex_'): np.complex_ = getattr(np, 'complex128', complex)
if not hasattr(np, 'int_'): np.int_ = getattr(np, 'int32', int)
if not hasattr(np, 'uint_'): np.uint_ = getattr(np, 'uint32', int)
if not hasattr(np, 'longfloat'): np.longfloat = getattr(np, 'longdouble', float)
if not hasattr(np, 'longcomplex'): np.longcomplex = getattr(np, 'clongdouble', complex)

"""
    if "if not hasattr(np, 'bool8')" not in code:
        code = patch_code + code

    with open(path, "w", encoding="utf-8") as f:
        f.write(code)
    print("Patched nptyping safely.")
