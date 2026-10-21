-- Runs once on first Postgres container init (docker-entrypoint-initdb.d).
-- The app's own test suite (see backend/conftest.py) expects a sibling
-- "<database>_test" database to already exist on the server.
CREATE DATABASE keel_test;
