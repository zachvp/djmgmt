from djmgmt import constants

def create_log_path(module_name: str) -> str:
    relative_path = f"src/djmgmt/{module_name}.py"
    return str(constants.PROJECT_ROOT.joinpath(relative_path))