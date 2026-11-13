# typer

## Module management commands

All of these work on a project folder containing `typeo.json` (and optionally `typeo_override.json`). Run `dependency -p <path>` afterwards to resolve the changes into the solution/csproj files.

| Command | Purpose |
| --- | --- |
| `modules [-r registry.json]` | JSON list of all modules in `modules.json` (`Author/Name` entries) with their GitHub tag versions |
| `moduleinfo -a author -n name -v version [-c cachePath]` | JSON product description (typeo.json) of a module version, from the module cache or GitHub |
| `dependencies -p <path>` | JSON list of the project's effective dependencies, flagging overrides |
| `adddependency` / `removedependency` | Add, replace or remove an entry in `typeo.json` |
| `update -p <path> [-n name] [-v version]` | Update TypeO dependencies to the latest release or a given version |
| `addoverride -p <path> -n name -l <localModulePath>` | Use a local module checkout instead, stored in `typeo_override.json` |
| `removeoverride -p <path> -n name` | Remove the override |
| `new` | Create a new module or exe project |

Dependency and override strings use the form `Author@Name-Version[;tag]`; local overrides use `Author@Name-<path>;local`.

When a project has `TypeO/cache/modules.json`, `dependency` uses its resolved `Modules`
(`Author`, `Name`, `Version`) as the selected module versions throughout the project graph.
Each module's csproj references use the same selected versions, while dependency tags
and NuGet versions remain unchanged. Solution entries are reconciled against the
resolved project references, repairing stale entries even if an earlier run updated a
csproj without updating its solution. Local selections use a `;local` version suffix.
Without that cache, module versions retain the manifest/override behavior.
Reconciliation also keeps or restores every project declared by the solution's
own `typeo.json`, including main, dev and test projects inside `ModulesCache`.

The cache context is passed to module generation and pre-build resolution using
`--resolvedModules <path>`, also accepted by `generate`. Those pre-build hooks invoke
the TypeR checkout performing the resolution, rather than a module's bundled TypeR,
so subsequent builds cannot restore that module's older manifest versions.
The cache must contain one selection per author/module; conflicting entries fail resolution.

After resolving the complete graph, TypeD builds with
`-p:TypeODependenciesResolved=true`. Generated dependency hooks honor this property
so parallel MSBuild projects do not resolve and rewrite each other's dependencies
during compilation. Other pre-build tasks still run. Ordinary command-line builds
without this property retain dependency resolution.

## Running tests

From the repository root:

    python -m unittest discover -s tests -t . -b