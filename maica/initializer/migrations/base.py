from packaging.version import parse

_migrations = []

def register_migration(upper_version: str, migrate_func):
    _migrations.append((parse(upper_version), migrate_func))

def get_migrations():
    return sorted(_migrations, key=lambda x: x[0])