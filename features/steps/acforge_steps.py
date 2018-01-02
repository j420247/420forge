from behave import given, when, then
from acforge import app
from bs4 import BeautifulSoup

@given(u'acforge is set up')
def flask_is_setup(context):
    assert context.client

@when("i browse to the acforge index")
def step_impl(context):
    context.page = context.client.get('/', follow_redirects=True)
    context.soup = BeautifulSoup(context.page.data, "html.parser")

    rblist = context.soup.find_all(type="radio")
    assert context.page

@then("i should receive a 200")
def step_impl(context):
    assert (context.page.status_code == 200)

@then('i see the "Atlassian Cloudformation Forge" title')
def step_impl(context):
    context.pagetitle = context.soup.title.string
    assert (context.pagetitle == 'Atlassian Cloudformation Forge')

@then("i see an option to upgrade")
def step_impl(context):
    assert context.soup.find(value="upgrade")

@then("i see an option to clone")
def step_impl(context):
    assert context.soup.find(value="clone")


@then("i see an option to restart")
def step_impl(context):
    context.soup.find(value="restart")