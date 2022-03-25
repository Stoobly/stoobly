import click
import os
import pdb

from stoobly_agent.config.constants import env_vars
from stoobly_agent.lib.utils.conditional_decorator import ConditionalDecorator

from .app.api import run as run_api
from .app.cli import ca_cert, config, feature, request
from .app.cli.utils.migrate_service import migrate as migrate_database
from .app.proxy import INTERCEPT_MODES, run as run_proxy
from .app.settings import Settings

settings = Settings.instance()
is_remote = settings.features.get('remote')

CONTEXT_SETTINGS = dict(help_option_names=['-h', '--help'])

@click.version_option()
@click.group(
    epilog="Run 'stoobly-agent COMMAND --help' for more information on a command.",
    context_settings=CONTEXT_SETTINGS,
)
@click.pass_context
def main(ctx):
    pass

# Attach subcommands to main
main.add_command(ca_cert)
main.add_command(config)
main.add_command(feature)
main.add_command(request)

if settings.features.get('dev_tools'):
    from .app.cli import dev_tools
    main.add_command(dev_tools)

if settings.features.get('exec'):
    from .app.cli.decorators.exec import ExecDecorator
    ExecDecorator(main).decorate()

if settings.features.get('remote'):
    from .app.cli import report, scenario
    main.add_command(report)
    main.add_command(scenario)

@main.command(
    help="Run proxy and/or UI",
)
@ConditionalDecorator(lambda f: click.option('--api-url', help='API URL.')(f), is_remote)
@ConditionalDecorator(lambda f: click.option('--headless', is_flag=True, default=False, help='Disable starting UI.')(f), is_remote)
@click.option('--intercept-mode', help=', '.join(INTERCEPT_MODES))
@click.option('--log-level', default='info', help='''
    Log levels can be "debug", "info", "warning", or "error"
''')
@click.option('--proxy-host', default='0.0.0.0', help='Address to bind proxy to.')
@click.option('--proxy-mode', default="regular", help='''
    Proxy mode can be "regular", "transparent", "socks5",
    "reverse:SPEC", or "upstream:SPEC". For reverse and
    upstream proxy modes, SPEC is host specification in
    the form of "http[s]://host[:port]".
''')
@click.option('--proxy-port', default=8080, help='Proxy service port.')
@click.option('--ssl-insecure', is_flag=True, default=False, help='Do not verify upstream server SSL/TLS certificates.')
@click.option('--test-script', help='Provide a custom script for testing.')
@ConditionalDecorator(lambda f: click.option('--ui-host', default='0.0.0.0', help='Address to bind UI to.')(f), is_remote)
@ConditionalDecorator(lambda f: click.option('--ui-port', default=4200, help='UI service port.')(f), is_remote)
def run(**kwargs):
    os.environ[env_vars.AGENT_PROXY_URL] = f"http://{kwargs['proxy_host']}:{kwargs['proxy_port']}"

    if not os.getenv(env_vars.LOG_LEVEL):
        os.environ[env_vars.LOG_LEVEL] = kwargs['log_level']

    if 'api_url' in kwargs and kwargs['api_url']:
        os.environ[env_vars.API_URL] = kwargs['api_url']

    if 'headless' in kwargs and not kwargs['headless']:
        run_api(**kwargs)

    if kwargs['test_script']:
        os.environ[env_vars.TEST_SCRIPT] = kwargs['test_script']

    migrate_database()

    run_proxy(**kwargs)