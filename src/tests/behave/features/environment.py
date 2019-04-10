import os
import sys

## add module to syspath
# get the current working directory
cwd = os.path.abspath(os.path.dirname(__file__))
# isolate the last folder (the folder we are currently in)
project = os.path.basename(cwd)
# remove the last folder from the cwd
new_path = cwd.strip(project)
# create a new path pointing to where our Flask object is defined
full_path = os.path.join(new_path, 'acforge')
try:
    from src.forge.acforge import acforge
except ImportError:
    sys.path.append(full_path)
    from src.forge.acforge import app


def before_feature(context, feature):
    context.client = app.test_client()
