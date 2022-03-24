import os
import pdb

from mitmdump import DumpMaster, Options
from mitmproxy.optmanager import _Option
from typing import Union

from stoobly_agent.app.settings import Settings
from stoobly_agent.app.settings.writer import SettingsWriter

from ...config.constants import mode

INTERCEPT_HANDLER_FILENAME = 'intercept_handler.py'
INTERCEPT_MODES = [mode.MOCK, mode.RECORD, mode.TEST]

'''
Pass in options from run CLI
'''
def run(**kwargs):
    options = kwargs.copy()
    __commit_options(options)
    __filter_options(options)
    
    fixed_options = {
        'flow_detail': 1,
        'scripts': __get_intercept_handler_path(),
        'upstream_cert': False,
    }

    opts = Options(**{**options, **fixed_options})
    __set_connection_strategy(opts, 'lazy')

    m = DumpMaster(opts)
    m.run()

def __filter_options(options):
    # Filter out non-mitmproxy options
    options['listen_host'] = options['proxy_host']
    options['listen_port'] = options['proxy_port']
    options['mode'] = options['proxy_mode']

    del options['headless']
    del options['intercept_mode']
    del options['log_level']
    del options['proxy_host']
    del options['proxy_mode']
    del options['proxy_port']
    del options['ui_host']
    del options['ui_port']
    del options['api_url']
    del options['test_script']

def __commit_options(options):
    # proxy_url
    writer = SettingsWriter(Settings.instance())
    url = f"http://{options.get('proxy_host')}:{options.get('proxy_port')}"
    writer.write_proxy_url(url)

    # intercept_mode
    intercept_mode = options.get('intercept_mode')
    writer.write_active_mode(intercept_mode)

    # remote_enabled
    remote_enabled = options.get('remote_enabled')
    writer.write_remote_enabled(remote_enabled)

def __get_intercept_handler_path():
    cwd = os.path.dirname(os.path.realpath(__file__))
    script = os.path.join(cwd, INTERCEPT_HANDLER_FILENAME)
    return script

'''
 Equivalent of:
 mitmdump connection_strategy={strategy}
'''
def __set_connection_strategy(opts, strategy):
    extra_options = {
        'dumper_filter': f"connection_strategy={strategy}",
        'readfile_filter': f"connection_strategy={strategy}",
        'save_stream_filter': f"connection_strategy={strategy}",
    }
    for k, v in extra_options.items():
        opts._options[k] = _Option(k, str, v, '', None)
    opts.update(**extra_options)
