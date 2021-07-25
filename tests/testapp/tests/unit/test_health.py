def test_health_endpoint(app):
    result = app.get('/api/v1/health')
    assert result.status_code == 200
    assert result.json['status'] is True
