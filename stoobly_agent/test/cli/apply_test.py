import pdb
import pytest

from click.testing import CliRunner
from typing import List

from stoobly_agent.test.test_helper import assert_orm_request_equivalent, DETERMINISTIC_GET_REQUEST_URL, NON_DETERMINISTIC_GET_REQUEST_URL, reset

from stoobly_agent.app.models.factories.resource.local_db.helpers.log import Log
from stoobly_agent.app.models.factories.resource.local_db.helpers.log_event import DELETE_ACTION, LogEvent
from stoobly_agent.cli import record, request, scenario, snapshot
from stoobly_agent.lib.orm.request import Request
from stoobly_agent.lib.orm.scenario import Scenario

@pytest.fixture(scope='module')
def runner():
    return CliRunner()

class TestApply():
    @pytest.fixture(scope='class', autouse=True)
    def settings(self):
      return reset()

    class TestWhenDeletingRequest():

      @pytest.fixture(scope='class')
      def recorded_request(self, runner: CliRunner):
        record_result = runner.invoke(record, [DETERMINISTIC_GET_REQUEST_URL])
        assert record_result.exit_code == 0
        return Request.last()

      @pytest.fixture(autouse=True, scope='class')
      def delete_event(self, runner: CliRunner, recorded_request: Request):
        snapshot_result = runner.invoke(request, ['snapshot', '--action', DELETE_ACTION, recorded_request.key()])
        assert snapshot_result.exit_code == 0

        log = Log()
        events = log.events
        return events[len(events) - 1]

      def test_it_sets_is_deleted(self, runner: CliRunner, recorded_request: Request):
        apply_result = runner.invoke(snapshot, ['apply'])
        assert apply_result.exit_code == 0

        _request = Request.find(recorded_request.id)
        assert _request.is_deleted

      def test_it_deletes(self, runner: CliRunner, recorded_request: Request, delete_event: LogEvent):
        apply_result = runner.invoke(snapshot, ['apply', delete_event.uuid])
        assert apply_result.exit_code == 0

        _request = Request.find(recorded_request.id)
        assert _request == None

    class TestWhenCreatingRequest():

      @pytest.fixture(scope='function')
      def recorded_request(self, runner: CliRunner):
        record_result = runner.invoke(record, [DETERMINISTIC_GET_REQUEST_URL])
        assert record_result.exit_code == 0
        return Request.last()

      @pytest.fixture(autouse=True, scope='function')
      def put_event(self, runner: CliRunner, recorded_request: Request):
        snapshot_result = runner.invoke(request, ['snapshot', recorded_request.key()])
        assert snapshot_result.exit_code == 0

        log = Log()
        events = log.events
        return events[len(events) - 1]

      def test_it_creates_request(self, runner: CliRunner, recorded_request: Request):
        recorded_request.delete()
        assert Request.find(recorded_request.id) == None

        apply_result = runner.invoke(snapshot, ['apply'])
        assert apply_result.exit_code == 0

        _request = Request.find_by(uuid=recorded_request.uuid)
        assert _request != None
        assert_orm_request_equivalent(_request, recorded_request)

      def test_idempotent(self, runner: CliRunner, recorded_request: Request, put_event: LogEvent):
        apply_result = runner.invoke(snapshot, ['apply', put_event.uuid])
        assert apply_result.exit_code == 0

        _request = Request.find_by(uuid=recorded_request.uuid)
        assert_orm_request_equivalent(_request, recorded_request)

    class TestWhenDeletingScenario():

      @pytest.fixture(scope='class')
      def created_scenario(self, runner: CliRunner):
          create_result = runner.invoke(scenario, ['create', 'test'])
          assert create_result.exit_code == 0
          return Scenario.last()

      @pytest.fixture(autouse=True, scope='class')
      def delete_event(self, runner: CliRunner, created_scenario: Scenario):
        snapshot_result = runner.invoke(scenario, ['snapshot', '--action', DELETE_ACTION, created_scenario.key()])
        assert snapshot_result.exit_code == 0

        log = Log()
        events = log.events
        return events[len(events) - 1]

      def test_it_sets_is_deleted(self, runner: CliRunner, created_scenario: Scenario):
        snapshot_result = runner.invoke(snapshot, ['apply'])
        assert snapshot_result.exit_code == 0

        scenario = Scenario.find(created_scenario.id)

        assert scenario.is_deleted

      def test_it_deletes(self, runner: CliRunner, created_scenario: Scenario, delete_event: LogEvent):
        snapshot_result = runner.invoke(snapshot, ['apply', delete_event.uuid])
        assert snapshot_result.exit_code == 0

        scenario = Scenario.find(created_scenario.id)

        assert scenario == None

    class TestWhenCreatingScenario():

      @pytest.fixture(scope='class')
      def created_scenario(self, runner: CliRunner):
          create_result = runner.invoke(scenario, ['create', 'test'])
          assert create_result.exit_code == 0
          return Scenario.last()

      @pytest.fixture(scope='class', autouse=True)
      def created_scenario_requests(self, runner: CliRunner, created_scenario: Scenario):
          record_result = runner.invoke(record, ['--scenario-key', created_scenario.key(), DETERMINISTIC_GET_REQUEST_URL])
          assert record_result.exit_code == 0

          record_result = runner.invoke(record, ['--scenario-key', created_scenario.key(), NON_DETERMINISTIC_GET_REQUEST_URL])
          assert record_result.exit_code == 0

          return created_scenario.requests

      @pytest.fixture(scope='class', autouse=True)
      def put_event(self, runner: CliRunner, created_scenario: Scenario):
        snapshot_result = runner.invoke(scenario, ['snapshot', created_scenario.key()])
        assert snapshot_result.exit_code == 0

        log = Log()
        events = log.events
        return events[len(events) - 1]

      @pytest.fixture(scope='class', autouse=True)
      def recreated_scenario(self, runner: CliRunner, created_scenario: Scenario):
        requests = created_scenario.requests

        created_scenario.delete()
        assert Scenario.find(created_scenario.id) == None

        for request in requests:
          request.delete()
          assert Request.find(request.id) == None

        apply_result = runner.invoke(snapshot, ['apply'])
        assert apply_result.exit_code == 0

        _scenario = Scenario.find_by(uuid=created_scenario.uuid)
        assert _scenario != None

        return _scenario

      def test_it_creates_scenario(self, created_scenario: Scenario, recreated_scenario: Scenario):
        assert recreated_scenario.requests_count == 2
        assert recreated_scenario.name == created_scenario.name
        assert recreated_scenario.description == created_scenario.description

      def test_it_creates_requests(self, created_scenario_requests: List[Request], recreated_scenario: Scenario):
        requests = recreated_scenario.requests
        assert len(requests) == 2

        assert_orm_request_equivalent(requests[0], created_scenario_requests[0])
        assert_orm_request_equivalent(requests[1], created_scenario_requests[1])

    class TestWhenMergingScenario():

      @pytest.fixture(scope='class')
      def created_scenario(self, runner: CliRunner):
        create_result = runner.invoke(scenario, ['create', 'test'])
        assert create_result.exit_code == 0
        return Scenario.last()

      @pytest.fixture(scope='class', autouse=True)
      def created_scenario_requests(self, runner: CliRunner, created_scenario: Scenario):
        record_result = runner.invoke(record, ['--scenario-key', created_scenario.key(), DETERMINISTIC_GET_REQUEST_URL])
        assert record_result.exit_code == 0

        record_result = runner.invoke(record, ['--scenario-key', created_scenario.key(), NON_DETERMINISTIC_GET_REQUEST_URL])
        assert record_result.exit_code == 0

        return created_scenario.requests

      @pytest.fixture(scope='class', autouse=True)
      def put_event(self, runner: CliRunner, created_scenario: Scenario):
        snapshot_result = runner.invoke(scenario, ['snapshot', created_scenario.key()])
        assert snapshot_result.exit_code == 0

        log = Log()
        events = log.events
        return events[len(events) - 1]

      # This request was created after the snapshot
      # Later when we apply changes, we expect this request to not exist
      @pytest.fixture(scope='class', autouse=True)
      def new_scenario_request(self, runner: CliRunner, created_scenario: Scenario, put_event: LogEvent):
        assert created_scenario.uuid == put_event.resource_uuid
        assert created_scenario.requests.count() == 2

        record_result = runner.invoke(record, ['--scenario-key', created_scenario.key(), DETERMINISTIC_GET_REQUEST_URL])
        assert record_result.exit_code == 0

        return created_scenario.requests.last()

      @pytest.fixture(scope='class')
      def apply_result(self, runner: CliRunner, created_scenario: Scenario):
        created_scenario = Scenario.find(created_scenario.id)
        assert created_scenario.requests_count == 3
        apply_result = runner.invoke(snapshot, ['apply'])

        return apply_result

      def test_it_merges_scenario(self, created_scenario: Scenario, apply_result):
        assert apply_result.exit_code == 0

        created_scenario = Scenario.find(created_scenario.id)
        assert created_scenario.requests_count == 2

      def test_it_maintains_requests(self, created_scenario: Scenario, created_scenario_requests: List[Request]):
        created_scenario = Scenario.find(created_scenario.id)
        assert len(created_scenario.requests) == 2

        requests = created_scenario.requests

        assert_orm_request_equivalent(requests[0], created_scenario_requests[0])
        assert_orm_request_equivalent(requests[1], created_scenario_requests[1])