import git
from pathlib import Path
from os.path import dirname
from flask import current_app

repo = git.Repo(Path(dirname(dirname(current_app.root_path))))

__version__ = f'{repo.active_branch.name}'
