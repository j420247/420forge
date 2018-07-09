from stack import Stack
from pprint import pprint
stack_region='us-east-1'
app_type='confluence'
stack_name='extlab'
mystack = Stack(stack_name, stack_region, app_type)

#status = mystack.print_action_log()
outcome = mystack.get_current_state()
outcome = mystack.debug_forgestate()
#outcome = mystack.rolling_restart()
#outcome = mystack.full_restart()
#outcome = mystack.destroy()
#outcome = mystack.upgrade('7.8.0')
# try:
#     outcome = mystack.destroy()
# except:
#     pass
# outcome = mystack.clone('snap-0f1b5498862ee87dc','dr-lab-master-snap-201803090026', 'ChangeMe', 'cHANGEmE', 'confluence')
#outcome = mystack.clone('snap-0f1b5498862ee87dc','dr-lab-master-snap-201803090026', 'ChangeMe', 'cHANGEmE', 'confluence', 'eac-stg','us-east-1')

pprint(outcome)

