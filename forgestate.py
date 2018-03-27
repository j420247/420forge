from collections import defaultdict
from datetime import datetime
import json
import pprint

class Forgestate:
    """An object containing the forge configuration information and state of actions conducted by Forge:

    Attributes:
        forgestate: A dict of dicts containing all state information.
        stack_name: The name of the stack we are keeping state for
    """

    def __init__(self, stack_name):
        self.forgestate = defaultdict(dict)
        self.stack_name = stack_name

    def write_log(self):
        with open(self.stack_name + '.json', 'w') as outfile:
            json.dump(self.forgestate, outfile)
        outfile.close()
        return (self)

    def load_state(self):
        stack_name=self.stack_name
        try:
            with open(stack_name + '.json', 'r') as infile:
                self.forgestate = json.load(infile)
                return self.forgestate
        except FileNotFoundError:
            self.forgestate = {'action_log': []}
            pass
        except Exception as e:
            print('type is:', e.__class__.__name__)
            print(e.strerror)
            template = "An exception of type {0} occurred. Arguments:\n{1!r}"
            message = template.format(type(e).__name__, e.args)
            return ('failed')
        return (self)

    def update(self, update_key, update_value):
        if not "stack_name" in self.forgestate:
            self.load_state()
        self.forgestate[update_key] = update_value
        self.write_log()
        return (self)

    def clear(self):
        self.forgestate = defaultdict(dict)
        self.write_log()
        return (self)

    def print(self):
        pprint.pprint(self.forgestate)
        return (self)

    def archive(self):
        # at the end of an action, archive will take the current forgestate and write it out to a datestamped file
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        with open(self.stack_name + '_' + self.forgestate['action'] + '_' + timestamp +'.json', 'w') as outfile:
            json.dump(self.forgestate, outfile)
        outfile.close()
        return (self)

    def logaction(self, level, message):
        print(f'{datetime.now()} {level} {message}')
        if not "action_log" in self.forgestate:
            # if no action_log list exists in forgestate, initialise it
            action_log = []
            self.update('action_log', action_log)
        action_log = self.forgestate['action_log']
        action_log.insert(0, f'{datetime.now()} {level} {message}')
        self.update('action_log', action_log)
        return (self)
