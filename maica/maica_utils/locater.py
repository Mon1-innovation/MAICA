"""Import layer 0"""
import sys
import os
import inspect

def locater():
    """
    Gets the project/container path.
    """
    try:
        is_frozen = sys.frozen
    except Exception:
        try:
            is_frozen = locater.__compiled__
        except Exception:
            is_frozen = None
    
    if is_frozen:
        absolute_path = os.path.abspath(sys.executable)
    else:
        absolute_path = os.path.abspath(inspect.getfile(locater))

    dirname = os.path.dirname(absolute_path)
    if not is_frozen:
        for i in range(2):
            dirname = os.path.dirname(dirname)
    
    return is_frozen, dirname

def get_inner_path(filename):
    frozen, base_path = locater()
    if frozen:
        filepath = os.path.join(base_path, filename)
    else:
        filepath = os.path.join(base_path, 'maica', filename)
    return filepath

def get_outer_path(filename):
    frozen, base_path = locater()
    return os.path.join(base_path, filename)

if __name__ == "__main__":
    is_frozen, self_path = locater()
    print(f"是否已被打包: {is_frozen}")
    print(f"函数所在文件绝对路径: {self_path}")