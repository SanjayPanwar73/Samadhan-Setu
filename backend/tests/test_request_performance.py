from sqlalchemy import event

from app.ai.providers import get_providers
from app.core.database import engine
from app.models.issue import Issue


def test_model_inference_releases_the_request_connection(db, world, students, auth, client, monkeypatch):
    student = students()
    headers = auth(student)
    body = {"title": "Broken water cooler", "description": "Water cooler stopped working",
            "location_id": world.c3.id, "category_id": world.cooler_cat.id}
    db.rollback()
    checked_out = []
    providers = get_providers()

    def observe(fn):
        def call(*args):
            checked_out.append(engine.pool.checkedout())
            return fn(*args)
        return call

    for name in ("classify", "embed", "sentiment"):
        monkeypatch.setattr(providers, name, observe(getattr(providers, name)))
    assert client.post("/complaints", json=body, headers=headers).status_code == 201
    assert checked_out == [0, 0, 0]


def test_queue_query_counts_do_not_grow_with_page_size(db, world, students, submit, client, auth):
    student = students()
    for cooler in (world.cooler1, world.cooler2):
        submit(student, world, category=world.cooler_cat, asset=cooler)
    for issue in db.query(Issue).all():
        r = client.post(f"/issues/{issue.id}/assignments", headers=auth(world.wat_admin),
                        json={"staff_ids": [world.wat_staff.id]})
        assert r.status_code == 201, r.text

    for url, actor in (("/complaints/me", student), ("/issues", world.wat_admin), ("/tasks", world.wat_staff)):
        headers = auth(actor)
        counts = []
        for limit in (1, 2):
            statements = []
            def record(conn, cursor, statement, parameters, context, executemany):
                statements.append(statement)
            event.listen(engine, "before_cursor_execute", record)
            try:
                r = client.get(url, params={"limit": limit}, headers=headers)
            finally:
                event.remove(engine, "before_cursor_execute", record)
            assert r.status_code == 200
            rows = r.json()["items"] if url == "/issues" else r.json()
            assert len(rows) == limit
            counts.append(len(statements))
        assert counts[0] == counts[1], (url, counts)
