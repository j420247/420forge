from collections import defaultdict
from datetime import datetime
import json
import pprint
from pathlib import Path
import os

class Stackstate:
    """An object containing the forge configuration information and state of actions conducted by Forge:

    Attributes:
        stackstate: A dict of dicts containing all state information.
        stack_name: The name of the stack we are keeping state for
    """

    def __init__(self, stack_name):
        self.stackstate = defaultdict(dict)
        self.stack_name = stack_name

    def write_state(self):
        if not Path(f'stacks/{self.stack_name}').exists():
            os.makedirs(f'stacks/{self.stack_name}')
        with open(f'stacks/{self.stack_name}/{self.stack_name}.json', 'w') as outfile:
            json.dump(self.stackstate, outfile)
        outfile.close()
        return (self)

    def load_state(self):
        try:
            with open(f'stacks/{self.stack_name}/{self.stack_name}.json', 'r') as infile:
                self.stackstate = json.load(infile)
                return self.stackstate
        except FileNotFoundError:
            self.stackstate = {'action_log': []}
            pass
        except Exception as e:
            print('type is:', e.__class__.__name__)
            print(e.args[0])
            template = "An exception of type {0} occurred. Arguments:\n{1!r}"
            message = template.format(type(e).__name__, e.args)
            return ('failed')
        return (self)

    def update(self, update_key, update_value):
        self.stackstate[update_key] = update_value
        self.write_state()
        return (self)

    def clear(self):
        self.stackstate = defaultdict(dict)
        self.write_state()
        return (self)

    def print(self):
        pprint.pprint(self.stackstate)
        return (self)

    def archive(self):
        # at the end of an action, archive will take the current stackstate and write it out to a datestamped file
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        action = self.stackstate['action'] if 'action' in self.stackstate else 'no-action'
        with open(f'stacks/{self.stack_name}/{self.stack_name}_{action}_{timestamp}.json', 'w') as outfile:
            json.dump(self.stackstate, outfile)
        outfile.close()
        return (self)

    def logaction(self, level, message):
        print(f'{datetime.now()} {level} {message}')
        if not "action_log" in self.stackstate:
            # if no action_log list exists in stackstate, initialise it
            action_log = []
            self.update('action_log', action_log)
        action_log = self.stackstate['action_log']
        action_log.insert(0, f'{datetime.now()} {level} {message}')
        self.update('action_log', action_log)
        return (self)
