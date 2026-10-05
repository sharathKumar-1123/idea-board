def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}
    assert client.get("/api/health").status_code == 200


def test_create_and_list_ideas(client):
    created = client.post("/api/ideas", json={"content": "  My new idea  "})
    assert created.status_code == 201
    body = created.json()
    assert body["content"] == "My new idea"
    assert {"id", "content", "created_at"} <= body.keys()

    ideas = client.get("/api/ideas").json()
    assert any(i["id"] == body["id"] for i in ideas)


def test_rejects_blank_content(client):
    assert client.post("/api/ideas", json={"content": "   "}).status_code == 422


def test_rejects_too_long_content(client):
    assert client.post("/api/ideas", json={"content": "x" * 501}).status_code == 422
