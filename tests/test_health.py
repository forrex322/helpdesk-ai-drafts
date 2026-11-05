def test_health_answers_ok(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.content == b"OK"
