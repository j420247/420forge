from behave import given, when, then
from bs4 import BeautifulSoup
from pprint import pprint


@given(u'acforge is set up')
def flask_is_setup(context):
    assert context.client


@when("i browse to the acforge index")
def step_impl(context):
    context.page = context.client.get('/', follow_redirects=True)
    context.soup = BeautifulSoup(context.page.data, "html.parser")
    assert context.page


@then("i should receive a 200")
def step_impl(context):
    assert context.page.status_code == requests.codes.ok


@then('i see the "Atlassian Cloudformation Forge" title')
def step_impl(context):
    context.pagetitle = context.soup.title.string
    assert context.pagetitle == 'Atlassian Cloudformation Forge'


@then("i see an option to upgrade")
def step_impl(context):
    assert context.soup.find(id="upgrade-link")


@then("i see an option to clone")
def step_impl(context):
    assert context.soup.find(id="clone-link")


@then("i see an option to fullrestart")
def step_impl(context):
    context.soup.find(id="fullrestart-link")


@then("i see an option to rollingrestart")
def step_impl(context):
    context.soup.find(id="rollingrestart-link")


@then("i see an option of staging")
def step_impl(context):
    context.soup.find(id="staging-link")


@then("i see an option of production")
def step_impl(context):
    context.soup.find(id="production-link")


@then("i see an option to destroy")
def step_impl(context):
    assert context.soup.find(id="destroy-link")


@when("i select staging on acforge index")
def step_impl(context):
    context.page = context.client.get('/env/stg', follow_redirects=True)
    context.soup = BeautifulSoup(context.page.data, "html.parser")
    assert context.page


@given("environment has a value")
def step_impl(context):
    context.environment = 'stg'
    pass


@when("i select an action on acforge index")
def step_impl(context):
    context.action = 'upgrade'
    context.page = context.client.get('/show_stacks', follow_redirects=True)
    context.soup = BeautifulSoup(context.page.data, "html.parser")
    cpd = context.page
    mysoup = context.soup = BeautifulSoup(context.page.data, "html.parser")
    pprint(context.soup)
    assert context.page


@then("i see the stack_selection form")
def step_impl(context):
    assert context.soup.find(id="stackForm")


@given("action has a value")
def step_impl(context):
    """
    :type context: behave.runner.Context
    """
    pass


@when("i select an environment on acforge index")
def step_impl(context):
    """
    :type context: behave.runner.Context
    """
    pass
