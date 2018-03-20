from stack import Stack
from pprint import pprint
stack_name="bamj"
stack_env="stg"
app_type='jira'
mystack = Stack(stack_name, stack_env, app_type)

#status = mystack.print_action_log()
# mystack.debug_forgestate()
outcome = mystack.rolling_restart()
# try:
#     outcome = mystack.destroy()
# except:
#     pass
# outcome = mystack.clone('snap-0f1b5498862ee87dc','dr-lab-master-snap-201803090026', 'ChangeMe', 'cHANGEmE', 'confluence')
#outcome = mystack.clone('snap-0f1b5498862ee87dc','dr-lab-master-snap-201803090026', 'ChangeMe', 'cHANGEmE', 'confluence', 'eac-stg','stg')

pprint(outcome)

