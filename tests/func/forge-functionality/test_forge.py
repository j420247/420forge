from forge import acforge as acforge
from flask import Flask

# Configure app
app = Flask(__name__)
app.config['CLONE_DEFAULTS'] = {
    'all': {'ClusterNodeCount': '1', 'CustomDnsName': '', 'DBMultiAZ': 'false', 'DeployEnvironment': 'stg', 'MailEnabled': 'false', 'Monitoring': 'false', 'TomcatScheme': 'http'},
    'stg-stack': {'ClusterNodeCount': '4', 'CustomDnsName': 'mystack.mycompany.com'},
}


# Tests for functionality that is only in acforge.py and does not call out to boto
class TestForge:
    def test_get_clone_defaults(self):
        with app.app_context():
            get_clone_defaults = acforge.GetCloneDefaults()
            all_defaults = get_clone_defaults.get('test-stack')
            assert all_defaults['CustomDnsName'] == ''
            stg_stack_defaults = get_clone_defaults.get('stg-stack')
            assert stg_stack_defaults['CustomDnsName'] == 'mystack.mycompany.com'
            # Ensure the bug where we overrode the defaults with stg info is fixed
            all_defaults_2 = get_clone_defaults.get('test_stack')
            assert all_defaults_2['CustomDnsName'] == ''
