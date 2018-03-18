from stack import Stack
from pprint import pprint
stack_name="lab"
stack_env="stg"
mystack = Stack(stack_name, stack_env)

#status = mystack.print_action_log()
#mystack.debug_forgestate()
try:
    outcome = mystack.destroy()
except:
    pass
outcome = mystack.clone('snap-0f1b5498862ee87dc','dr-lab-master-snap-201803090026', 'ChangeMe', 'cHANGEmE', 'confluence')
#outcome = mystack.clone('snap-0f1b5498862ee87dc','dr-lab-master-snap-201803090026', 'ChangeMe', 'cHANGEmE', 'confluence', 'eac-stg','stg')

pprint(outcome)

