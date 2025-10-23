from djmgmt import constants

def create_file_path(module_name: str) -> str:
    relative_path = f"src/djmgmt/{module_name}.py"
    return str(constants.PROJECT_ROOT / relative_path)
