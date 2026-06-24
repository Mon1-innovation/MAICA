import re
from pathlib import Path

env = Path(__file__).parent / "env_basis"

pattern = re.compile(
    r"^MAICA_CURR_VERSION\s*=\s*'(.*)'"
)

for line in env.read_text(
    encoding="utf-8"
).splitlines():

    m = pattern.match(line)

    if m:
        __version__ = m.group(1)
        break
else:
    raise RuntimeError(
        "version not found"
    )