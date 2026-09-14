import importlib
from fastapi.testclient import TestClient
from backend.auth import AuthenticatedUser


def test_studio_save_roundtrip_preserves_inputs_and_owner(monkeypatch, tmp_path):
    monkeypatch.setenv('AUTH_MODE', 'local')
    monkeypatch.setenv('MUSE_DATASET', 'synthetic')
    monkeypatch.setenv('CAMPAIGN_STORE', 'local')
    monkeypatch.setenv('LOCAL_CAMPAIGN_DB', str(tmp_path / 'campaigns.json'))
    monkeypatch.delenv('CAMPAIGN_SNAPSHOT_BUCKET', raising=False)
    from backend import main
    main = importlib.reload(main)
    with TestClient(main.app) as client:
        creator = client.get('/api/creators').json()['creators'][0]['id']
        inputs = dict(budget=139000, currentRoster=[creator], include=[creator], exclude=[], costs={creator:500},
                      planningContext=dict(brandDescription='', relevance={}, maxPerGroup={}, creatorCount=0))
        response = client.post('/api/campaigns', json=dict(name='Studio roundtrip', **inputs))
        assert response.status_code == 200, response.text
        record = response.json()['campaign']
        loaded = client.get('/api/campaigns/' + record['id']).json()
        assert all(loaded[k] == v for k, v in inputs.items())
        main.app.dependency_overrides[main.user_dependency] = lambda: AuthenticatedUser(email='other@example.test', subject='other')
        assert client.get('/api/campaigns').json()['campaigns'] == []
        assert client.get('/api/campaigns/' + record['id']).status_code == 404
        main.app.dependency_overrides.clear()


def test_requests_from_a_page_showing_another_dataset_get_a_reload_signal(monkeypatch, tmp_path):
    monkeypatch.setenv('AUTH_MODE', 'local')
    monkeypatch.setenv('MUSE_DATASET', 'synthetic')
    monkeypatch.setenv('CAMPAIGN_STORE', 'local')
    monkeypatch.setenv('LOCAL_CAMPAIGN_DB', str(tmp_path / 'campaigns.json'))
    from backend import main
    main = importlib.reload(main)
    with TestClient(main.app) as client:
        payload = client.get('/api/creators').json()
        body = dict(budget=139000, currentRoster=[payload['creators'][0]['id']])
        stale = client.post('/api/plan', json=body, headers={'X-Dataset-Version': 'previous-search'})
        assert stale.status_code == 409 and stale.json()['code'] == 'dataset_changed'
        fresh = client.post('/api/plan', json=body, headers={'X-Dataset-Version': payload['datasetVersion']})
        assert fresh.status_code == 200, fresh.text
