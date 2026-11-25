import threading

from conftest import ANNA, BOB


def test_opposite_requests_at_the_same_time_only_one_wins(app, make_user, as_user, relation_rows):
    make_user(ANNA, username="anna")
    make_user(BOB, username="bob")
    for attempt in range(5):
        barrier = threading.Barrier(2)
        statuses = []

        def send(caller, other):
            client = app.test_client()  # one client per thread
            headers = as_user(caller)
            barrier.wait()
            statuses.append(client.put(f"/api/v1/users/me/relations/{other}", headers=headers).status_code)

        threads = [
            threading.Thread(target=send, args=(ANNA, BOB)),
            threading.Thread(target=send, args=(BOB, ANNA)),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert sorted(statuses) == [201, 409], f"attempt {attempt}: {statuses}"
        assert len(relation_rows()) == 1

        # reset for the next round
        client = app.test_client()
        client.delete(f"/api/v1/users/me/relations/{BOB}", headers=as_user(ANNA))
        assert relation_rows() == []
