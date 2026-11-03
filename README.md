# typer

## Module management commands

All of these work on a project folder containing `typeo.json` (and optionally `typeo_override.json`). Run `dependency -p <path>` afterwards to resolve the changes into the solution/csproj files.

| Command | Purpose |
| --- | --- |
| `modules [-r registry.json]` | JSON list of all modules in `modules.json` (`Author/Name` entries) with their GitHub tag versions |
| `dependencies -p <path>` | JSON list of the project's effective dependencies, flagging overrides |
| `adddependency` / `removedependency` | Add, replace or remove an entry in `typeo.json` |
| `update -p <path> [-n name] [-v version]` | Update TypeO dependencies to the latest release or a given version |
| `addoverride -p <path> -n name -l <localModulePath>` | Use a local module checkout instead, stored in `typeo_override.json` |
| `removeoverride -p <path> -n name` | Remove the override |
| `new` | Create a new module or exe project |

Dependency and override strings use the form `Author@Name-Version[;tag]`; local overrides use `Author@Name-<path>;local`.

## Running tests

From the repository root:

    python -m unittest discover -s tests -t . -b