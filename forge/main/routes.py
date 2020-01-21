from datetime import timedelta
from os import getenv, path


from flask import Blueprint, current_app, flash, redirect, render_template, request, session, url_for
from forge.acforge import get_cfn_stacks_for_region, get_forge_settings, get_nice_action_name


main = Blueprint('main', __name__, template_folder='templates')


# This checks for SAML auth and sets a session timeout
@main.before_request
def check_loggedin():
    session.permanent = True
    current_app.permanent_session_lifetime = timedelta(minutes=60)
    if getenv('NO_SAML') or current_app.config.get('NO_SAML'):
        return
    if not request.path.startswith("/saml") and not request.path.startswith("/status") and not session.get('saml'):
        login_url = url_for('login', next=request.url)
        return redirect(login_url)


# This checks for Cloudtoken credentials
@main.before_request
def check_cloudtoken():
    if 'credentials' in session and session['credentials'] is False:
        flash('No credentials - please authenticate with Cloudtoken', 'error')
        return
    return


# Helper functions
def set_action(action):
    get_forge_settings()
    session['nice_action_name'] = get_nice_action_name(action)
    session['stacks'] = sorted(get_cfn_stacks_for_region(session['region']))


# Action UI pages
@main.route('/upgrade', methods=['GET'])
def upgrade():
    set_action('upgrade')
    return render_template('upgrade.html')


@main.route('/clone', methods=['GET'])
def clone():
    set_action('clone')
    return render_template('clone.html')


@main.route('/fullrestart', methods=['GET'])
def fullrestart():
    set_action('fullrestart')
    return render_template('fullrestart.html')


@main.route('/rollingrestart', methods=['GET'])
def rollingrestart():
    set_action('rollingrestart')
    return render_template('rollingrestart.html')


@main.route('/rollingrebuild', methods=['GET'])
def rollingrebuild():
    set_action('rollingrebuild')
    return render_template('rollingrebuild.html')


@main.route('/create', methods=['GET'])
def create():
    set_action('create')
    return render_template('create.html')


@main.route('/destroy', methods=['GET'])
def destroy():
    set_action('destroy')
    return render_template('destroy.html')


@main.route('/update', methods=['GET'])
def update():
    set_action('update')
    return render_template('update.html')


@main.route('/tag', methods=['GET'])
def tag():
    set_action('tag')
    return render_template('tag.html')


@main.route('/viewlog', methods=['GET'])
def viewlog():
    set_action('viewlog')
    return render_template('viewlog.html')


@main.route('/syslog', methods=['GET'])
def syslog():
    set_action('syslog')
    return render_template('syslog.html')


@main.route('/diagnostics', methods=['GET'])
def diagnostics():
    set_action('diagnostics')
    return render_template('diagnostics.html')


@main.route('/runsql', methods=['GET'])
def runsql():
    set_action('runsql')
    return render_template('runsql.html')


@main.route('/admin', methods=['GET'])
def admin():
    set_action('admin')
    return render_template('admin.html')


@main.route('/admin/<stack_name>', methods=['GET'])
def admin_stack(stack_name):
    set_action('admin')
    return render_template('admin.html', stackToAdmin=stack_name)


@main.route('/error/<error>')
def error(error):
    return render_template('error.html', code=error), error


@main.route('/')
def index():
    get_forge_settings()
    session['nice_action_name'] = ''
    return render_template('index.html')


@main.route('/upgrade')
def upgradeSetParams():
    return render_template('upgrade.html')


@main.route('/actionreadytostart')
def actionreadytostart():
    return render_template('actionreadytostart.html')


@main.route('/actionprogress/<action>')
def actionprogress(action):
    flash(f"Action '{action}' on {request.args.get('stack')} has begun", 'success')
    return render_template('actionprogress.html')


@main.route('/setregion/<region>')
def setregion(region):
    session['region'] = region
    session['stacks'] = sorted(get_cfn_stacks_for_region(region))
    flash(f'Region selected: {region}', 'success')
    return redirect(request.referrer)


# function to get last modified time of JS files to automatically invalidate them when updated
@main.context_processor
def utility_processor():
    def get_filename_with_last_update_time(file_with_path):
        mtime = str(path.getmtime(path.join(current_app.root_path, file_with_path)))
        return f"/{file_with_path}?v={mtime}"

    return dict(get_filename_with_last_update_time=get_filename_with_last_update_time)
