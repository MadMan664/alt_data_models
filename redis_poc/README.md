# Redis proof of concept (key-value model)

A small script that shows how a key-value database works, using Redis.
It connects, creates, reads, updates and deletes data, and demonstrates the
features that make the model different from a relational database.

## Run it

1. Start Redis (needs Docker):

        docker run --name redis -p 6379:6379 -d redis:latest

2. Install the Python client:

        pip install redis

3. Run the script:

        python3 redis_poc.py

To look at the data yourself while it runs, open the Redis shell:

        docker exec -it redis redis-cli

Every key the script creates starts with "poc:" and is removed at the end, so
it can be run again and never touches other data. The run takes about 10
seconds because some steps wait for a key to expire.

## What each step shows

| Step | Idea | Commands |
|------|------|----------|
| 1 | Connect to the server | PING, INFO |
| 2 | Create, read, update, delete (an update replaces the whole value) | SET, GET, DEL, EXISTS |
| 3 | Structures beyond a plain value: list (queue), hash (profile), set (tags), sorted set (leaderboard) | RPUSH, LPOP, HSET, HGETALL, SADD, ZADD |
| 4 | Time to live: a key that deletes itself | SET with EX, TTL |
| 5 | Atomic counter and a rate limiter (5 visits per 4 seconds) | INCR, EXPIRE |
| 6 | Cache in front of a slow database (about 500 ms the first time, about 0.2 ms afterwards) | GET, SET with EX |
| 7 | The limit of the model: you look data up by key, not by value | SCAN, GET |

## Notes

- Redis keeps data in memory. With no persistence configured, data is lost
  when the container is removed.
- Values are stored and returned as text. A hash field set to 31 comes back
  as the text '31'.
- The expiry times are short on purpose so the demo is quick (the task text
  suggests 10 seconds for a key's life; change the number in step 4 if you
  want that).
