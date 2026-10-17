#!/usr/bin/env python3
"""Redis proof of concept: a key-value database, step by step.

Run it with a Redis server on localhost:6379 (see README.md):

    python3 redis_poc.py

Every key created here starts with "poc:" so the script can be run again and
never touches other data stored in the same Redis.
"""
import time

import redis

HOST = "localhost"
PORT = 6379
PREFIX = "poc:"

r = redis.Redis(host=HOST, port=PORT, decode_responses=True)


def title(text):
    """Print a section header."""
    print("\n" + "=" * 64)
    print(text)
    print("=" * 64)


def show(label, value):
    """Print one line of output in a fixed layout."""
    print("  {:<38} -> {}".format(label, value))


def clean_up():
    """Delete every key this script may have created in a previous run."""
    for key in r.scan_iter(PREFIX + "*"):
        r.delete(key)


# ---------------------------------------------------------------------------
# 1. Connect
# ---------------------------------------------------------------------------
def step_connect():
    title("1. Connect to the server")
    show("PING", r.ping())
    show("Redis version", r.info("server")["redis_version"])


# ---------------------------------------------------------------------------
# 2. Basic CRUD on a plain key and value
# ---------------------------------------------------------------------------
def step_crud():
    title("2. Create, read, update, delete (CRUD)")
    key = PREFIX + "user:1"

    r.set(key, "Alice")
    show("CREATE  set user:1 'Alice'", "done")
    show("READ    get user:1", r.get(key))

    r.set(key, "Alice Johnson")
    show("UPDATE  set user:1 'Alice Johnson'", r.get(key))
    print("          (an update replaces the WHOLE value; there is no "
          "partial edit)")

    show("DELETE  delete user:1 (1 = key removed)", r.delete(key))
    show("READ    get user:1 after delete", r.get(key))
    show("EXISTS  user:1 (0 = no such key)", r.exists(key))


# ---------------------------------------------------------------------------
# 3. Data structures beyond a plain string
# ---------------------------------------------------------------------------
def step_structures():
    title("3. Data structures: list, hash, set, sorted set")

    queue = PREFIX + "queue"
    r.rpush(queue, "task1", "task2", "task3")
    show("LIST   queue after 3 pushes", r.lrange(queue, 0, -1))
    show("LIST   first out (lpop)", r.lpop(queue))
    show("LIST   second out (lpop)", r.lpop(queue))
    show("LIST   still waiting", r.lrange(queue, 0, -1))
    print("          (first in, first out: a simple queue)")

    profile = PREFIX + "user:2"
    r.hset(profile, mapping={"name": "Bob", "age": 30, "city": "Riyadh"})
    show("HASH   whole profile", r.hgetall(profile))
    show("HASH   one field (name)", r.hget(profile, "name"))
    r.hset(profile, "age", 31)
    show("HASH   age after changing one field", r.hget(profile, "age"))
    print("          (values come back as text: '31', not the number 31)")

    tags = PREFIX + "tags"
    r.sadd(tags, "python", "redis", "python")
    show("SET    members (python added twice)", sorted(r.smembers(tags)))
    show("SET    is 'redis' a member?", bool(r.sismember(tags, "redis")))

    board = PREFIX + "leaderboard"
    r.zadd(board, {"Alice": 120, "Bob": 95, "Carla": 150})
    show("ZSET   leaderboard, best first",
         r.zrevrange(board, 0, -1, withscores=True))
    show("ZSET   rank of Bob (0 = best)", r.zrevrank(board, "Bob"))


# ---------------------------------------------------------------------------
# 4. Expiration (TTL)
# ---------------------------------------------------------------------------
def step_ttl():
    title("4. Expiration: a key that deletes itself (TTL)")
    key = PREFIX + "session:abc"
    r.set(key, "logged-in-as-alice", ex=3)
    show("set with a 3 second life", r.get(key))
    show("TTL (seconds left)", r.ttl(key))
    time.sleep(1.2)
    show("after 1.2 s, TTL", r.ttl(key))
    time.sleep(2.2)
    show("after 3.4 s, get", r.get(key))
    show("after 3.4 s, TTL (-2 = key is gone)", r.ttl(key))


# ---------------------------------------------------------------------------
# 5. Atomic counter and a small rate limiter
# ---------------------------------------------------------------------------
def visit_allowed(user, limit, window_seconds):
    """Count a visit and say whether the user is still under the limit.

    INCR adds 1 in one atomic step. The first visit also starts a timer
    (EXPIRE) so the counter resets by itself when the window is over.
    """
    key = PREFIX + "visits:" + user
    count = r.incr(key)
    if count == 1:
        r.expire(key, window_seconds)
    return count <= limit, count


def step_counter_and_rate_limiter():
    title("5. Atomic counter and rate limiter (INCR + TTL)")
    page = PREFIX + "page:home:views"
    for _ in range(3):
        r.incr(page)
    show("page views after 3 INCR", r.get(page))

    limit, window = 5, 4
    print("\n  Rate limiter: at most {} visits per {} seconds".format(
        limit, window))
    for number in range(1, 8):
        allowed, count = visit_allowed("alice", limit, window)
        print("    visit {}: count={} -> {}".format(
            number, count, "ALLOWED" if allowed else "BLOCKED"))
    print("    ...waiting {} seconds for the window to reset...".format(
        window + 0.5))
    time.sleep(window + 0.5)
    allowed, count = visit_allowed("alice", limit, window)
    print("    visit 8: count={} -> {}".format(
        count, "ALLOWED" if allowed else "BLOCKED"))


# ---------------------------------------------------------------------------
# 6. Cache in front of a slow database
# ---------------------------------------------------------------------------
def slow_database_lookup(user_id):
    """Pretend to ask a slow relational database (takes half a second)."""
    time.sleep(0.5)
    return "user {} profile".format(user_id)


def get_profile(user_id):
    """Return the profile, using Redis as a cache that expires after 30 s."""
    key = PREFIX + "cache:profile:" + str(user_id)
    cached = r.get(key)
    if cached is not None:
        return cached, "cache hit"
    value = slow_database_lookup(user_id)
    r.set(key, value, ex=30)
    return value, "cache miss"


def step_cache():
    title("6. Use case: a cache in front of a slow database")
    for attempt in (1, 2, 3):
        start = time.perf_counter()
        value, outcome = get_profile(42)
        elapsed_ms = (time.perf_counter() - start) * 1000
        print("    request {}: {:<10} {:>7.1f} ms   {}".format(
            attempt, outcome, elapsed_ms, value))


# ---------------------------------------------------------------------------
# 7. The limit of the model: you must know the key
# ---------------------------------------------------------------------------
def step_limits():
    title("7. The limit: you can only look up by key, not by value")
    r.set(PREFIX + "user:10", "Dana")
    r.set(PREFIX + "user:11", "Evan")
    show("get by key  user:10", r.get(PREFIX + "user:10"))
    show("find keys by name pattern (user:*)",
         sorted(k[len(PREFIX):] for k in r.scan_iter(PREFIX + "user:1*")))
    print("          There is no command that means 'find the key whose "
          "value is Dana'.")
    print("          To search by value you must read every key yourself, "
          "or keep a second key as an index.")
    r.set(PREFIX + "index:name:Dana", "user:10")
    show("manual index  index:name:Dana", r.get(PREFIX + "index:name:Dana"))


def main():
    clean_up()
    step_connect()
    step_crud()
    step_structures()
    step_ttl()
    step_counter_and_rate_limiter()
    step_cache()
    step_limits()
    clean_up()
    title("Done: every poc: key was removed")


if __name__ == "__main__":
    main()
