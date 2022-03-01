import json
import pdb

from mitmproxy.net.http.request import Request as MitmproxyRequest
from requests import Response
from typing import List, Union

from stoobly_agent.lib.api.stoobly_api import StooblyApi
from stoobly_agent.lib.settings import IProjectModeSettings

from .hashed_request_decorator import HashedRequestDecorator
from ..mitmproxy.request_adapter import MitmproxyRequestAdapter
from ..settings import get_project_key, get_scenario_key

###
#
# @param settings [Settings.mode.mock | Settings.mode.record]
#
def eval_request(
    request: MitmproxyRequest,
    api: StooblyApi,
    settings: IProjectModeSettings,
    ignored_components_list: List[Union[list, str, None]] = None
) -> Response:
    ignored_components = __build_ignored_components(ignored_components_list)

    query_params = __build_query_params(request, ignored_components)
    query_params['scenario_key'] = get_scenario_key(request.headers, settings)

    return api.request_response(
        get_project_key(request.headers, settings), query_params
    )

def __build_ignored_components(ignored_components_list):
    ignored_components = []
    for el in ignored_components_list:
        if isinstance(el, str): 
            try:
                ignored_components += json.loads(el)
            except:
                pass
        elif isinstance(el, list):
            ignored_components += el
    return ignored_components

###
#
# Formats request into parameters expected by stoobly api
#
# @param request [lib.mitmproxy_request_adapter.MitmproxyRequestAdapter]
# @param ignored_components [Array<Hash>]
#
# @return [Hash] query parameters to pass to stoobly api
#
def __build_query_params(request: MitmproxyRequest, ignored_components = []) -> dict:
    request = MitmproxyRequestAdapter(request)
    hashed_request = HashedRequestDecorator(request).with_ignored_components(ignored_components)

    headers_hash = hashed_request.headers_hash()
    query_params_hash = hashed_request.query_params_hash()
    body_params_hash = hashed_request.body_params_hash()
    body_text_hash = hashed_request.body_text_hash()

    query_params = {}
    query_params['host'] = request.host
    query_params['path'] = request.path
    query_params['port'] = request.port
    query_params['method'] = request.method

    if len(headers_hash) > 0:
        query_params['headers_hash'] = headers_hash

    if len(query_params_hash) > 0:
        query_params['query_params_hash'] = query_params_hash

    # The problem here is that if a body_param_hash is not passed, then body_text_hash is checked
    # However, if body_params are ignored, then there may not be a body_param_hash
    #
    # If there are ignored body_params, this means there are body_params
    # Then we should use body_params_hash over body_text_hash
    if len(body_params_hash) > 0 or len(hashed_request.ignored_body_params) > 0:
        query_params['body_params_hash'] = body_params_hash

    if len(body_text_hash) > 0:
        query_params['body_text_hash'] = body_text_hash

    if len(ignored_components) > 0:
        query_params['retry'] = 1

    return query_params
