import pytest
import forge
import sys


# citation: https://www.patricksoftwareblog.com/testing-a-flask-application-using-pytest/


@pytest.fixture(scope='module')
def test_client():
    sys.argv = ["--nosaml"]
    app = forge.create_app('forge.config.BaseConfig')
    testing_client = app.test_client()
    # Establish an application context before running the tests.
    ctx = app.app_context()
    ctx.push()

    yield testing_client  # this is where the testing happens!

    ctx.pop()
    # app.run(threaded=True, debug=False, host='0.0.0.0', port=8000)


def test_api_root(test_client):
    """
        GIVEN the Forge Flask application
        WHEN the '/' page is requested (GET)
        THEN check the response is valid
        """
    response = test_client.get('http://localhost:8000/')
    assert response.status_code == 302
    return


def test_api_status(test_client):
    """
        GIVEN the Forge Flask application
        WHEN the '/status' page is requested (GET)
        THEN check the response is valid
        """
    response = test_client.get('http://localhost:8000/status')
    assert response.status_code == 200
    return


class TestApiStackInfo:
    def test_api_get_logs(self, test_client):
        return


class TestApiHelpers:
    def test_api_get_ebs_snapshots(self, test_client):
        return


if __name__ == '__main__':
    test_api_root(test_client)
    test_client.g
