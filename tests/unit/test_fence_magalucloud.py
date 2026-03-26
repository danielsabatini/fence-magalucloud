import logging
import sys
from unittest.mock import MagicMock, patch

import pytest
import requests

# ---------------------------------------------------------------------------
# Stub mínimo da lib fencing para isolar os testes do módulo externo
# ---------------------------------------------------------------------------

EC_STATUS = 1
EC_LOGIN_DENIED = 2


def _fail_stub(code):
    raise SystemExit(code)


fencing_stub = MagicMock()
fencing_stub.EC_STATUS = EC_STATUS
fencing_stub.EC_LOGIN_DENIED = EC_LOGIN_DENIED
fencing_stub.all_opt = {}
fencing_stub.atexit_handler = MagicMock()
fencing_stub.check_input = MagicMock()
fencing_stub.fail = _fail_stub
fencing_stub.fence_action = MagicMock(return_value=0)
fencing_stub.process_input = MagicMock()
fencing_stub.run_delay = MagicMock()
fencing_stub.show_docs = MagicMock()

sys.modules['fencing'] = fencing_stub

import fence_magalucloud.fence_magalucloud as agent  # noqa: E402

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

BASE_URL = 'https://api.magalu.cloud/br-se1/compute/v1'


@pytest.fixture
def options():
    return {
        '--api-key': 'test-key',
        '--region': 'br-se1',
        '--plug': 'vm-abc-123',
        '--action': 'off',
        '--shell-timeout': '30',
    }


def _mock_response(status_code: int, json_data: dict | None = None, ok: bool | None = None):
    resp = MagicMock()
    resp.status_code = status_code
    resp.ok = ok if ok is not None else (200 <= status_code < 300)
    resp.json.return_value = json_data or {}
    return resp


# ---------------------------------------------------------------------------
# _base_url
# ---------------------------------------------------------------------------


class TestBaseUrl:
    def test_uses_configured_region(self, options):
        options['--region'] = 'br-ne1'
        assert agent._base_url(options) == 'https://api.magalu.cloud/br-ne1/compute/v1'

    def test_default_region(self):
        assert agent._base_url({}) == 'https://api.magalu.cloud/br-se1/compute/v1'


# ---------------------------------------------------------------------------
# _headers
# ---------------------------------------------------------------------------


class TestHeaders:
    def test_contains_api_key(self, options):
        headers = agent._headers(options)
        assert headers['x-api-key'] == 'test-key'

    def test_contains_accept_json(self, options):
        headers = agent._headers(options)
        assert headers['Accept'] == 'application/json'


# ---------------------------------------------------------------------------
# _request
# ---------------------------------------------------------------------------


class TestRequest:
    @patch('fence_magalucloud.fence_magalucloud.requests.request')
    def test_returns_response_on_success(self, mock_req, options):
        mock_req.return_value = _mock_response(200)
        resp = agent._request('GET', f'{BASE_URL}/instances', {}, options)
        assert resp.status_code == 200

    @patch('fence_magalucloud.fence_magalucloud.requests.request')
    def test_uses_shell_timeout(self, mock_req, options):
        options['--shell-timeout'] = '60'
        mock_req.return_value = _mock_response(200)
        agent._request('GET', f'{BASE_URL}/instances', {}, options)
        _, kwargs = mock_req.call_args
        assert kwargs['timeout'] == 60

    @patch('fence_magalucloud.fence_magalucloud.requests.request')
    def test_401_calls_fail_with_login_denied(self, mock_req, options):
        mock_req.return_value = _mock_response(401, ok=False)
        with pytest.raises(SystemExit) as exc_info:
            agent._request('GET', f'{BASE_URL}/instances', {}, options)
        assert exc_info.value.code == EC_LOGIN_DENIED

    @patch('fence_magalucloud.fence_magalucloud.requests.request')
    def test_connection_error_calls_fail_with_ec_status(self, mock_req, options):
        mock_req.side_effect = requests.exceptions.ConnectionError('timeout')
        with pytest.raises(SystemExit) as exc_info:
            agent._request('GET', f'{BASE_URL}/instances', {}, options)
        assert exc_info.value.code == EC_STATUS


# ---------------------------------------------------------------------------
# get_power_status
# ---------------------------------------------------------------------------


class TestGetPowerStatus:
    @patch('fence_magalucloud.fence_magalucloud._request')
    def test_running_returns_on(self, mock_req, options):
        mock_req.return_value = _mock_response(200, {'state': 'running'})
        assert agent.get_power_status(None, options) == 'on'

    @patch('fence_magalucloud.fence_magalucloud._request')
    def test_stopped_returns_off(self, mock_req, options):
        mock_req.return_value = _mock_response(200, {'state': 'stopped'})
        assert agent.get_power_status(None, options) == 'off'

    @patch('fence_magalucloud.fence_magalucloud._request')
    def test_suspended_returns_off(self, mock_req, options):
        mock_req.return_value = _mock_response(200, {'state': 'suspended'})
        assert agent.get_power_status(None, options) == 'off'

    @patch('fence_magalucloud.fence_magalucloud._request')
    def test_404_calls_fail(self, mock_req, options):
        mock_req.return_value = _mock_response(404, ok=False)
        with pytest.raises(SystemExit) as exc_info:
            agent.get_power_status(None, options)
        assert exc_info.value.code == EC_STATUS

    @patch('fence_magalucloud.fence_magalucloud._request')
    def test_non_ok_response_calls_fail(self, mock_req, options):
        mock_req.return_value = _mock_response(500, ok=False)
        with pytest.raises(SystemExit) as exc_info:
            agent.get_power_status(None, options)
        assert exc_info.value.code == EC_STATUS

    @patch('fence_magalucloud.fence_magalucloud._request')
    def test_unknown_state_calls_fail(self, mock_req, options):
        mock_req.return_value = _mock_response(200, {'state': 'migrating'})
        with pytest.raises(SystemExit) as exc_info:
            agent.get_power_status(None, options)
        assert exc_info.value.code == EC_STATUS

    @patch('fence_magalucloud.fence_magalucloud._request')
    def test_calls_correct_url(self, mock_req, options):
        mock_req.return_value = _mock_response(200, {'state': 'running'})
        agent.get_power_status(None, options)
        url_arg = mock_req.call_args[0][1]
        assert url_arg == f'{BASE_URL}/instances/vm-abc-123'

    @patch('fence_magalucloud.fence_magalucloud._request')
    def test_logs_debug_on_success(self, mock_req, options, caplog):
        mock_req.return_value = _mock_response(200, {'state': 'running'})
        with caplog.at_level(logging.DEBUG):
            agent.get_power_status(None, options)
        assert 'vm-abc-123' in caplog.text


# ---------------------------------------------------------------------------
# set_power_status
# ---------------------------------------------------------------------------


class TestSetPowerStatus:
    @patch('fence_magalucloud.fence_magalucloud._request')
    def test_action_off_calls_stop_endpoint(self, mock_req, options):
        options['--action'] = 'off'
        mock_req.return_value = _mock_response(200)
        agent.set_power_status(None, options)
        url_arg = mock_req.call_args[0][1]
        assert url_arg.endswith('/stop')

    @patch('fence_magalucloud.fence_magalucloud._request')
    def test_action_on_calls_start_endpoint(self, mock_req, options):
        options['--action'] = 'on'
        mock_req.return_value = _mock_response(200)
        agent.set_power_status(None, options)
        url_arg = mock_req.call_args[0][1]
        assert url_arg.endswith('/start')

    @patch('fence_magalucloud.fence_magalucloud._request')
    def test_404_calls_fail(self, mock_req, options):
        mock_req.return_value = _mock_response(404, ok=False)
        with pytest.raises(SystemExit) as exc_info:
            agent.set_power_status(None, options)
        assert exc_info.value.code == EC_STATUS

    @patch('fence_magalucloud.fence_magalucloud._request')
    def test_non_ok_response_calls_fail(self, mock_req, options):
        mock_req.return_value = _mock_response(503, ok=False)
        with pytest.raises(SystemExit) as exc_info:
            agent.set_power_status(None, options)
        assert exc_info.value.code == EC_STATUS

    @patch('fence_magalucloud.fence_magalucloud._request')
    def test_success_does_not_raise(self, mock_req, options):
        mock_req.return_value = _mock_response(200)
        agent.set_power_status(None, options)  # must not raise


# ---------------------------------------------------------------------------
# get_list
# ---------------------------------------------------------------------------


class TestGetList:
    @patch('fence_magalucloud.fence_magalucloud._request')
    def test_returns_dict_with_instances(self, mock_req, options):
        mock_req.return_value = _mock_response(
            200,
            {
                'instances': [
                    {'id': 'vm-1', 'name': 'web-01', 'state': 'running'},
                    {'id': 'vm-2', 'name': 'db-01', 'state': 'stopped'},
                ]
            },
        )
        result = agent.get_list(None, options)
        assert result['vm-1'] == ('web-01', 'on')
        assert result['vm-2'] == ('db-01', 'off')

    @patch('fence_magalucloud.fence_magalucloud._request')
    def test_empty_instances_returns_empty_dict(self, mock_req, options):
        mock_req.return_value = _mock_response(200, {'instances': []})
        assert agent.get_list(None, options) == {}

    @patch('fence_magalucloud.fence_magalucloud._request')
    def test_unknown_state_maps_to_unknown(self, mock_req, options):
        mock_req.return_value = _mock_response(
            200, {'instances': [{'id': 'vm-3', 'name': 'test', 'state': 'migrating'}]}
        )
        result = agent.get_list(None, options)
        assert result['vm-3'] == ('test', 'unknown')

    @patch('fence_magalucloud.fence_magalucloud._request')
    def test_non_ok_response_calls_fail(self, mock_req, options):
        mock_req.return_value = _mock_response(500, ok=False)
        with pytest.raises(SystemExit) as exc_info:
            agent.get_list(None, options)
        assert exc_info.value.code == EC_STATUS

    @patch('fence_magalucloud.fence_magalucloud._request')
    def test_calls_instances_endpoint(self, mock_req, options):
        mock_req.return_value = _mock_response(200, {'instances': []})
        agent.get_list(None, options)
        url_arg = mock_req.call_args[0][1]
        assert url_arg == f'{BASE_URL}/instances'

    @patch('fence_magalucloud.fence_magalucloud._request')
    def test_missing_id_uses_empty_string_as_key(self, mock_req, options):
        mock_req.return_value = _mock_response(
            200, {'instances': [{'name': 'no-id', 'state': 'running'}]}
        )
        result = agent.get_list(None, options)
        assert '' in result
        assert result[''] == ('no-id', 'on')

    @patch('fence_magalucloud.fence_magalucloud._request')
    def test_missing_name_falls_back_to_id(self, mock_req, options):
        mock_req.return_value = _mock_response(
            200, {'instances': [{'id': 'vm-4', 'state': 'running'}]}
        )
        result = agent.get_list(None, options)
        assert result['vm-4'] == ('vm-4', 'on')


# ---------------------------------------------------------------------------
# define_new_opts
# ---------------------------------------------------------------------------


class TestDefineNewOpts:
    def test_registers_api_key(self):
        with patch.object(agent, 'all_opt', {}) as mock_opt:
            agent.define_new_opts()
            assert 'api_key' in mock_opt
            assert mock_opt['api_key']['required'] == '1'

    def test_registers_region_with_default(self):
        with patch.object(agent, 'all_opt', {}) as mock_opt:
            agent.define_new_opts()
            assert 'region' in mock_opt
            assert mock_opt['region']['default'] == 'br-se1'
            assert mock_opt['region']['required'] == '0'
